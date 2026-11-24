"""Torrent searching and candidate construction."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import pick
from .net import HttpError
from .seanime import Seanime, SeanimeError


def gather(
    clients: list[Seanime],
    media: dict[str, Any],
    queries: list[str],
    *,
    batch: bool | None,
    episode: int | None,
    titles: list[str],
    hint: int | None,
    found: dict[str, dict[str, Any]],
    hints: dict[str, int] | None = None,
    verbose: bool = False,
    retries: int = 1,
    any_codec: bool = False,
) -> None:
    pairs = [(client, query) for client in clients for query in queries]
    failures = 0

    def search(client: Seanime, query: str):
        try:
            return client.search_torrents(
                media, query, batch=batch, episode=episode, retries=retries
            ), None
        except (SeanimeError, HttpError) as exc:
            return [], exc

    # Each query is an independent HTTP call; run them concurrently so one
    # slow or unavailable feed does not serialise the whole batch.
    if len(pairs) == 1:
        outcomes = [search(*pairs[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
            outcomes = list(pool.map(lambda pair: search(*pair), pairs))

    for (_client, query), (results, exc) in zip(pairs, outcomes):
        if exc is not None:
            # One provider/query can fail (e.g. feed_unavailable) without
            # invalidating the others; skip it instead of aborting the run.
            failures += 1
            if verbose:
                print(f"  ! search failed for {query!r}: {exc}", file=sys.stderr)
            continue
        for torrent in results:
            name = torrent.get("name") or ""
            if not pick.acceptable_release(name, any_codec=any_codec):
                continue
            if not pick.mentions_title(name, titles):
                continue
            if not pick.matches_season(name, hint):
                continue
            key = (torrent.get("infoHash") or name).lower()
            found.setdefault(key, torrent)
            if hints is not None and episode is not None:
                # Seanime has already mapped the entry's local episode to the
                # release's absolute number (cour sequels continue S01E14...).
                # Remember it so build_candidates does not re-derive the number
                # from the filename and throw the result away.
                hints.setdefault(key, episode)
    if pairs and failures == len(pairs):
        raise SeanimeError("all torrent searches failed")


def build_candidates(
    client: Seanime,
    torrents: list[dict[str, Any]],
    total: int,
    *,
    max_probes: int,
    verbose: bool,
    hints: dict[str, int] | None = None,
) -> list[pick.Candidate]:
    """Attach episode coverage to every torrent (probing batches via get-files)."""
    singles: list[pick.Candidate] = []
    batches: list[pick.Candidate] = []
    requested = hints or {}
    for torrent in torrents:
        name = torrent.get("name") or ""
        codec = pick.codec_of(name, any_codec=True) or ""
        if pick.is_batch(torrent):
            batches.append(pick.Candidate(torrent=torrent, codec=codec))
        else:
            key = (torrent.get("infoHash") or name).lower()
            number = requested.get(key) or pick.episode_of(name) or (1 if total == 1 else None)
            if number is None or not 1 <= number <= total:
                continue
            singles.append(pick.Candidate(torrent=torrent, episodes={number}, codec=codec))

    batches.sort(key=lambda c: c.sort_key())
    probed = 0
    for cand in batches:
        if probed >= max_probes:
            break
        probed += 1
        try:
            files = client.torrent_files(cand.torrent)
        except SeanimeError as exc:
            if verbose:
                print(f"  ! could not inspect {cand.torrent.get('name')}: {exc}", file=sys.stderr)
            continue
        cand.files = len(files)
        cand.episodes = pick.coverage_from_files(files, total)
        if verbose:
            print(f"  · {cand.group}: {sorted(cand.episodes)} from {cand.files} files")
    return [c for c in batches if c.episodes] + singles
