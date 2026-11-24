"""Build and commit a release plan for one series (no writes until commit)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import pick
from .config import EXIT_ERROR, EXIT_OK, EXIT_SKIP
from .media import base_title, is_ongoing, series_destination, titles_of
from .net import HttpError
from .search import build_candidates, gather
from .seanime import Seanime, SeanimeError


def ensure_planning(
    client: Seanime,
    media: dict[str, Any],
    entry: dict[str, Any] | None,
    *,
    dry_run: bool,
) -> None:
    status = ((entry or {}).get("listData") or {}).get("status")
    if status == "PLANNING":
        print("AniList  : already on Planning")
        return
    if status:
        print(f"AniList  : left as {status} (not downgraded to Planning)")
        return
    if dry_run:
        print("AniList  : would be added to Planning (dry run)")
        return
    client.set_planning(media["id"])
    print("AniList  : added to Planning")


@dataclass
class PlanResult:
    """Resolved releases for one series; building one performs no writes."""

    media: dict[str, Any]
    entry: dict[str, Any] | None
    plan: pick.Plan | None
    destination: Path
    wanted: set[int]
    episodes: list[int]
    code: int
    message: str = ""


def build_plan(
    clients: list[Seanime],
    media: dict[str, Any],
    entry: dict[str, Any] | None,
    args: argparse.Namespace,
    *,
    total: int,
    wanted: set[int],
    query: str = "",
    echo: bool = True,
) -> PlanResult:
    """Select releases covering ``wanted``; never download or touch AniList.

    ``total`` is the upper bound used when inspecting batch files and ``query``
    is an extra search term (the user's title in single-title mode).
    """
    destination = series_destination(media, args.lib, query)
    ongoing = is_ongoing(media)
    names = media.get("title") or {}
    romaji = names.get("romaji") or names.get("english") or query or "Show"
    titles = titles_of(media)[:3] or ([query] if query else [romaji])

    hint = pick.season_hint(titles[0]) if titles else None
    terms = [base_title(t) for t in titles] + titles + ([query] if query else [])
    quoted = [t for t in terms if t and len(t) > 2]
    queries = list(dict.fromkeys(quoted))[:4]

    found: dict[str, dict[str, Any]] = {}
    hints: dict[str, int] = {}
    try:
        if ongoing:
            # An airing series has no finished season pack yet; go straight to
            # per-episode searches instead of probing batches that cannot exist.
            for number in sorted(wanted):
                gather(clients, media, queries[:2], batch=False, episode=number,
                       titles=titles, hint=hint, found=found, hints=hints, verbose=args.verbose)
        else:
            gather(clients, media, queries, batch=True, episode=None,
                   titles=titles, hint=hint, found=found, hints=hints, verbose=args.verbose)
            if len(found) <= 1 or total == 1:
                gather(clients, media, queries, batch=None, episode=1,
                       titles=titles, hint=hint, found=found, hints=hints, verbose=args.verbose)
    except (SeanimeError, HttpError) as exc:
        return PlanResult(media, entry, None, destination, wanted, [], EXIT_ERROR, f"error: {exc}")

    if echo:
        print(f"Search   : {len(found)} candidate release(s) with HEVC/AV1")
    candidates = build_candidates(clients[0], list(found.values()), total,
                                  max_probes=args.max_batch_probes, verbose=args.verbose,
                                  hints=hints)

    plan = pick.choose(candidates, total, wanted=wanted)
    if plan is None and not ongoing:
        # Batch search was incomplete: look for one release per missing episode.
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if missing and echo:
            print(f"Search   : per-episode fallback for {len(missing)} episode(s)")
        extra: dict[str, dict[str, Any]] = {}
        try:
            for episode in missing:
                gather(clients, media, queries[:2], batch=False, episode=episode,
                       titles=titles, hint=hint, found=extra, hints=hints, verbose=args.verbose)
        except (SeanimeError, HttpError) as exc:
            return PlanResult(media, entry, None, destination, wanted, [], EXIT_ERROR, f"error: {exc}")
        new_items = [t for k, t in extra.items() if k not in found]
        if new_items:
            candidates += build_candidates(clients[0], new_items, total,
                                           max_probes=args.max_batch_probes, verbose=args.verbose,
                                           hints=hints)
        plan = pick.choose(candidates, total, wanted=wanted)

    if plan is None:
        # Final fallback: no HEVC/AV1 release set covers the season, so complete
        # it with any 1080p release. H.264 candidates rank below HEVC/AV1, so a
        # mixed plan keeps the good encodes and fills only the uncovered gaps.
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if echo:
            print(f"Search   : any-codec fallback for {len(missing)} episode(s)")
        loose: dict[str, dict[str, Any]] = {}
        try:
            if not ongoing:
                gather(clients, media, queries, batch=True, episode=None,
                       titles=titles, hint=hint, found=loose, hints=hints,
                       any_codec=True, verbose=args.verbose)
            for episode in missing:
                gather(clients, media, queries[:2], batch=False, episode=episode,
                       titles=titles, hint=hint, found=loose, hints=hints,
                       any_codec=True, verbose=args.verbose)
        except (SeanimeError, HttpError) as exc:
            return PlanResult(media, entry, None, destination, wanted, [], EXIT_ERROR, f"error: {exc}")
        new_items = [t for k, t in loose.items() if k not in found]
        if new_items:
            candidates += build_candidates(clients[0], new_items, total,
                                           max_probes=args.max_batch_probes, verbose=args.verbose,
                                           hints=hints)
        plan = pick.choose(candidates, total, wanted=wanted)

    if plan is None:
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if missing:
            message = (f"Skip     : no 1080p HEVC/AV1/H.264 release covers episode(s) {missing}; "
                       "nothing downloaded")
        else:
            message = "Skip     : no 1080p release found; nothing downloaded"
        if echo:
            print(message)
        return PlanResult(media, entry, None, destination, wanted, [], EXIT_SKIP, message)

    episodes = sorted(set(plan.episodes) & wanted)
    if echo and any(cand.codec == "h264" for cand in plan.torrents):
        print("Note     : plan includes H.264 episodes (no HEVC/AV1 release covers them)")
    return PlanResult(media, entry, plan, destination, wanted, episodes, EXIT_OK)


def commit_plan(
    client: Seanime,
    result: PlanResult,
    args: argparse.Namespace,
    *,
    do_planning: bool = True,
) -> int:
    """Write a planned download. The caller handles printing and confirmation."""
    plan = result.plan
    assert plan is not None
    try:
        result.destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create destination folder {result.destination}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        client.download([c.torrent for c in plan.torrents], str(result.destination),
                        result.media, result.episodes)
    except (SeanimeError, HttpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Download : queued {len(plan.torrents)} torrent(s) to {result.destination}")

    if do_planning and not args.no_planning:
        try:
            ensure_planning(client, result.media, result.entry, dry_run=False)
        except (SeanimeError, HttpError) as exc:
            print(f"warning: download queued but AniList update failed: {exc}", file=sys.stderr)
            return EXIT_ERROR
    return EXIT_OK
