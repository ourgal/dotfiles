"""anime-fetch: check the Seanime library, then download a HEVC/AV1 release.

Standard workflow (matches the user's rules):
  1. resolve the title on AniList through Seanime;
  2. if the library already has files, stop;
  3. search torrents (batch first, then per episode);
  4. accept only HEVC/x265 or AV1 1080p releases, preferring a complete
     Judas-style batch, then DKB/EMBER/ASW-style x265 groups, then AV1;
  5. if any episode has no acceptable release, download nothing;
  6. otherwise add the torrents and put the title on the AniList Planning list.

Releasing series have no final AniList episode count. When AniList marks the
title as ongoing, the aired count is taken from nextAiringEpisode.episode - 1
(or from --episodes N) and used as the target. Airing series have no finished
season pack, so they are searched per episode. On a re-run, only the episodes
still missing from the library folder are downloaded, so new episodes can be
picked up without re-fetching the ones already on disk.

With `--all` no title is needed: every series on the AniList Watching list that
is still Releasing is processed in one batch, even ones Seanime has no files
for. For each series the target is aired episodes that are neither watched
(past AniList progress) nor already downloaded (present in the library folder
or Seanime's shared path). All plans are shown first and a single confirmation
covers the whole batch; those series already have a list status, so their
AniList entry is never changed.

With no title argument (and without `--all`) the query is read from the system
clipboard. The match and the selected releases are printed first; nothing is
downloaded or added to AniList until the user confirms.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import pick
from .net import HttpError
from .seanime import DEFAULT_BASE, DEFAULT_PROVIDER, Seanime, SeanimeError

DEFAULT_LIB = str(Path.home() / "Videos" / "Seanime")

# AniList statuses that still have episodes left to air.
ONGOING_STATUSES = {"RELEASING", "NOT_YET_RELEASED", "HIATUS"}

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_AMBIGUOUS = 2
EXIT_SKIP = 3


# --------------------------------------------------------------------------- utils
def human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{num} B"


def safe_folder(name: str) -> str:
    # "Mushoku Tensei III: Isekai Ittara Honki Dasu" -> "Mushoku Tensei III"
    # (a one-word prefix such as "Re:Zero" keeps its colon part).
    prefix, sep, _rest = name.partition(":")
    if sep and len(prefix.split()) >= 2:
        name = prefix
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    return cleaned or "Untitled"


def series_destination(media: dict[str, Any], lib_root: str, query: str = "") -> Path:
    """The library folder a series is downloaded into."""
    names = media.get("title") or {}
    romaji = names.get("romaji") or names.get("english") or query or "Show"
    return Path(lib_root) / safe_folder(romaji)


def count_videos(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    total = 0
    for root, _dirs, files in os.walk(folder):
        total += sum(1 for f in files if Path(f).suffix.lower() in pick.VIDEO_EXTS)
    return total


def aired_episode_count(media: dict[str, Any]) -> int | None:
    """Episodes already aired, from AniList's nextAiringEpisode (the next one)."""
    nxt = media.get("nextAiringEpisode") or {}
    episode = nxt.get("episode") if isinstance(nxt, dict) else None
    if isinstance(episode, int) and episode > 1:
        return episode - 1
    return None


def episode_files(folder: Path, *, titles: list[str] | None = None) -> set[int]:
    """Episode numbers of the video files present in a library folder.

    ``titles`` can restrict the scan to one series, which matters when Seanime
    reports a shared library root rather than a per-title folder.
    """
    found: set[int] = set()
    if not folder.is_dir():
        return found
    for _root, _dirs, files in os.walk(folder):
        for name in files:
            if Path(name).suffix.lower() not in pick.VIDEO_EXTS:
                continue
            if titles and not pick.mentions_title(name, titles):
                continue
            number = pick.episode_of(name)
            if number is not None:
                found.add(number)
    return found


def library_episodes(
    destination: Path, entry: dict[str, Any] | None, titles: list[str]
) -> set[int]:
    """Episodes on disk for one series, from its folder and Seanime's shared path."""
    existing = episode_files(destination)
    shared = ((entry or {}).get("libraryData") or {}).get("sharedPath")
    if isinstance(shared, str) and shared:
        existing |= episode_files(Path(shared), titles=titles)
    return existing


def titles_of(media: dict[str, Any]) -> list[str]:
    title = media.get("title") or {}
    ordered = [title.get("romaji"), title.get("english"), title.get("native")]
    ordered += list(media.get("synonyms") or [])
    return [t for t in ordered if isinstance(t, str) and t.strip()]


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


_PART_SUFFIX = re.compile(
    r"(?i)[\s:\u2013\u2014-]*(?:part|season|cour)\s*\d+(?:st|nd|rd|th)?\s*(?:cour)?[\s:\u2013\u2014-]*$"
)
_ORDINAL_COUR = re.compile(r"(?i)[\s:\u2013\u2014-]*\d+(?:st|nd|rd|th)?\s*cour[\s:\u2013\u2014-]*$")
_JP_COUR = re.compile(r"[\s:\u2013\u2014-]*\d+\s*クール[\s:\u2013\u2014-]*$")


def base_title(title: str) -> str:
    """Drop a cour/part marker for torrent searches.

    Releases of a second cour use the base series title plus absolute episode
    numbers ("Show - 14"), so searching "Show Part 2" finds nothing useful.
    """
    cleaned = _PART_SUFFIX.sub("", title)
    cleaned = _ORDINAL_COUR.sub("", cleaned)
    cleaned = _JP_COUR.sub("", cleaned)
    return cleaned.strip(" :\u2013\u2014-") or title


# ---------------------------------------------------------------------- clipboard
_URL = re.compile(r"https?://[^\s<>\"']+")


def clipboard_text() -> str | None:
    """Read the system clipboard with the first available native utility."""
    if sys.platform == "win32":
        commands = [["powershell", "-NoProfile", "-Command",
                     "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"]]
    elif sys.platform == "darwin":
        commands = [["pbpaste"]]
    else:
        commands = [["termux-clipboard-get"]] if os.environ.get("TERMUX_VERSION") else []
        commands += [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(command, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        text = result.stdout.decode("utf-8", "replace").strip()
        if result.returncode == 0 and text:
            return text
    return None


def query_from_text(text: str) -> str:
    """Turn clipboard contents into a query: the first text line, or a URL slug."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    match = _URL.search(first)
    if match is None:
        return first
    before = first[: match.start()].strip(" \t-|·:")
    if re.search(r"[A-Za-z0-9]", before):
        return before
    path = urllib.parse.urlparse(match.group(0)).path
    segments = [urllib.parse.unquote(seg) for seg in path.split("/") if seg]
    # AniList/MAL URLs look like /anime/<id>/<slug>; a bare trailing ID is not
    # searchable, so refuse it instead of searching for "anime".
    if not segments or segments[-1].isdigit():
        return ""
    return re.sub(r"[-_]+", " ", segments[-1]).strip()


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        print("Confirm  : no interactive terminal; re-run with --yes to skip the prompt",
              file=sys.stderr)
        return False
    try:
        answer = input(f"{question} [y/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}


def describe_media(media: dict[str, Any]) -> str:
    bits = [f"id {media['id']}", str(media.get("format") or "?")]
    if media.get("seasonYear"):
        bits.append(str(media["seasonYear"]))
    if media.get("meanScore"):
        bits.append(f"score {media['meanScore']}")
    bits += [g for g in (media.get("genres") or []) if isinstance(g, str)][:3]
    return ", ".join(bits)


# ---------------------------------------------------------------------- title pick
def resolve_media(client: Seanime, query: str, pick_index: int | None) -> dict[str, Any]:
    results = client.search_anime(query, per_page=10)
    results = [m for m in results if (m.get("format") or "") != "MUSIC" and not m.get("isAdult")]
    if not results:
        raise SeanimeError(f"AniList has no result for {query!r}")

    if pick_index is not None:
        if not 1 <= pick_index <= len(results):
            raise SeanimeError(f"--pick must be between 1 and {len(results)}")
        return results[pick_index - 1]

    wanted = normalize(query)
    scored: list[tuple[int, float, dict[str, Any]]] = []
    for media in results:
        best = 0
        qwords = wanted.split()
        for title in titles_of(media):
            candidate = normalize(title)
            if not candidate:
                continue
            cwords = candidate.split()
            if candidate == wanted:
                best = max(best, 100)
            elif cwords[: len(qwords)] == qwords or qwords[: len(cwords)] == cwords:
                # word-boundary prefix only: "yani" must not match "YaniSuu"
                ratio = min(len(cwords), len(qwords)) / max(len(cwords), len(qwords))
                best = max(best, 80 + int(10 * ratio))
            else:
                # Loose word overlap is only trusted for longer queries;
                # a one-word query would match unrelated titles ("yani").
                if len(qwords) >= 3:
                    overlap = len(set(qwords) & set(cwords)) / len(qwords)
                    if overlap >= 0.6:
                        best = max(best, int(60 * overlap))
        scored.append((best, float(media.get("meanScore") or 0), media))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    top_score, _, top = scored[0]
    if top_score < 60:
        listing = "\n".join(
            f"  {i + 1}. {m['title'].get('romaji')} (id {m['id']}, {m.get('format')}, {m.get('episodes') or '?'} eps)"
            for i, (_s, _ms, m) in enumerate(scored)
        )
        raise Ambiguous(f"no confident match for {query!r}; use --pick N:\n{listing}")
    if len(scored) > 1 and scored[1][0] == top_score:
        listing = "\n".join(
            f"  {i + 1}. {m['title'].get('romaji')} (id {m['id']}, {m.get('format')}, {m.get('episodes') or '?'} eps)"
            for i, (_s, _ms, m) in enumerate(scored)
        )
        raise Ambiguous(f"several equally good matches for {query!r}; use --pick N:\n{listing}")
    return top


class Ambiguous(RuntimeError):
    pass


# ------------------------------------------------------------------- torrent find
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
) -> None:
    calls = 0
    failures = 0
    for client in clients:
        for query in queries:
            calls += 1
            try:
                results = client.search_torrents(media, query, batch=batch, episode=episode)
            except (SeanimeError, HttpError) as exc:
                # One provider/query can fail (e.g. feed_unavailable) without
                # invalidating the others; skip it instead of aborting the run.
                failures += 1
                if verbose:
                    print(f"  ! search failed for {query!r}: {exc}", file=sys.stderr)
                continue
            for torrent in results:
                name = torrent.get("name") or ""
                if not pick.acceptable_release(name):
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
    if calls and failures == calls:
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
        codec = pick.codec_of(name) or ""
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


# ------------------------------------------------------------------------ reporting
def print_plan(plan: pick.Plan, destination: Path, *, wanted: set[int]) -> None:
    episodes = sorted(set(plan.episodes) & wanted)
    print(
        f"Selected : {plan.strategy} ({len(plan.torrents)} torrent(s), "
        f"{len(episodes)}/{len(wanted)} episodes)"
    )
    for cand in plan.torrents:
        covered = sorted(cand.episodes & wanted)
        shows = covered if len(covered) <= 12 else f"{min(covered)}-{max(covered)}"
        print(f"  [{cand.group}] {cand.torrent.get('name')}")
        print(f"      {human_size(cand.size)}, {cand.seeders} seeds, episodes {shows}")
    print(f"Destination: {destination}")
    print(f"Total size : {human_size(plan.size)}")


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


# ------------------------------------------------------------------ plan/commit
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
    ongoing = (media.get("status") or "") in ONGOING_STATUSES
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
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if missing:
            message = (f"Skip     : no HEVC/AV1 release covers episode(s) {missing}; "
                       "nothing downloaded")
        else:
            message = "Skip     : no HEVC/AV1 release found; nothing downloaded"
        if echo:
            print(message)
        return PlanResult(media, entry, None, destination, wanted, [], EXIT_SKIP, message)

    episodes = sorted(set(plan.episodes) & wanted)
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


# ---------------------------------------------------------------------- batch
def _as_int(value: Any) -> int:
    """Coerce an AniList progress-like value to a non-negative int."""
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value.strip()))
        except ValueError:
            return 0
    return 0


def entry_progress(entry: dict[str, Any]) -> int:
    """Watched count from either collection shape (AniList or library)."""
    list_data = entry.get("listData")
    if isinstance(list_data, dict) and "progress" in list_data:
        return _as_int(list_data.get("progress"))
    return _as_int(entry.get("progress"))


def entry_media_id(entry: dict[str, Any]) -> Any:
    """AniList media id from either collection shape."""
    media = entry.get("media") or {}
    return entry.get("mediaId") or (media.get("id") if isinstance(media, dict) else None)


def select_watching_releasing(collection: dict[str, Any]) -> list[dict[str, Any]]:
    """Entries on a Watching list whose AniList media is still Releasing."""
    selected: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for lst in collection.get("lists") or []:
        if str(((lst or {}).get("status")) or "").upper() not in {"CURRENT", "WATCHING"}:
            continue
        for entry in lst.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            media = entry.get("media") or {}
            if not isinstance(media, dict):
                continue
            if str(media.get("status") or "").upper() != "RELEASING":
                continue
            key = entry_media_id(entry)
            if key is None or key in seen:
                continue
            seen.add(key)
            selected.append(entry)
    return selected


def batch_targets(
    entry: dict[str, Any], *, episodes_override: int | None = None
) -> tuple[int, set[int]] | None:
    """Return ``(aired total, wanted)`` for one Watching/Releasing entry."""
    media = entry.get("media") or {}
    total = aired_episode_count(media)
    if total is None:
        return None
    progress = entry_progress(entry)
    cap = total
    if isinstance(episodes_override, int) and episodes_override > 0:
        cap = min(cap, episodes_override)
    wanted = set(range(progress + 1, cap + 1))
    return (total, wanted) if wanted else None


def run_all(args: argparse.Namespace, clients: list[Seanime]) -> int:
    """Process every Watching + Releasing series as one confirmed batch."""
    client = clients[0]
    try:
        anilist = client.anilist_collection()
    except (SeanimeError, HttpError) as exc:
        print(f"error: could not read the AniList collection: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # The library collection only indexes what is already downloaded; the
    # Watching list comes from AniList and can be much larger. Use it solely to
    # find Seanime's shared path for a series when scanning files on disk.
    library: dict[str, Any] = {}
    try:
        library = client.collection()
    except (SeanimeError, HttpError) as exc:
        if args.verbose:
            print(f"warning: could not read the library collection: {exc}", file=sys.stderr)
    library_entries: dict[Any, dict[str, Any]] = {}
    for lst in library.get("lists") or []:
        for lib_entry in lst.get("entries") or []:
            if isinstance(lib_entry, dict) and entry_media_id(lib_entry) is not None:
                library_entries.setdefault(entry_media_id(lib_entry), lib_entry)

    entries = select_watching_releasing(anilist)
    if not entries:
        print("Batch    : no Watching + Releasing series found; nothing to do")
        return EXIT_SKIP
    print(f"Batch    : {len(entries)} Watching + Releasing series")

    results: list[PlanResult] = []
    for index, entry in enumerate(entries, 1):
        media = entry.get("media") or {}
        names = media.get("title") or {}
        title = (names.get("romaji") or names.get("english")
                 or names.get("userPreferred")
                 or f"id {entry_media_id(entry)}")
        titles = titles_of(media)[:3] or [title]
        destination = series_destination(media, args.lib)
        lib_entry = library_entries.get(entry_media_id(entry))
        targets = batch_targets(entry, episodes_override=args.episodes)
        if targets is None:
            message = "skip     : no aired/unwatched episodes"
            print(f"  [{index}/{len(entries)}] {title}: {message}")
            results.append(PlanResult(media, entry, None, destination, set(), [],
                                      EXIT_SKIP, message))
            continue
        total, wanted = targets
        unwatched = set(wanted)
        wanted -= {number for number in library_episodes(destination, lib_entry, titles)
                   if number <= total}
        if not wanted:
            message = (f"skip     : all {len(unwatched)} unwatched episode(s) "
                       "are already on disk")
            print(f"  [{index}/{len(entries)}] {title}: {message}")
            results.append(PlanResult(media, entry, None, destination, set(), [],
                                      EXIT_SKIP, message))
            continue
        span = f"{min(wanted)}-{max(wanted)}" if len(wanted) > 1 else str(min(wanted))
        on_disk = len(unwatched) - len(wanted)
        note = f", {on_disk} already on disk" if on_disk else ""
        print(f"  [{index}/{len(entries)}] {title}: {len(wanted)} episode(s) "
              f"after progress ({span}){note}")
        results.append(build_plan(clients, media, entry, args, total=total, wanted=wanted,
                                  echo=False))

    queued = [r for r in results if r.code == EXIT_OK and r.plan is not None]
    failed_plans = [r for r in results if r.code == EXIT_ERROR]
    skipped = [r for r in results if r.code == EXIT_SKIP]
    for result in queued:
        print_plan(result.plan, result.destination, wanted=result.wanted)
    torrent_count = sum(len(r.plan.torrents) for r in queued)  # type: ignore[union-attr]
    print(f"Batch summary: {len(queued)} series queued ({torrent_count} torrent(s)), "
          f"{len(skipped)} skipped, {len(failed_plans)} error(s)")

    if args.dry_run:
        print("Dry run  : no torrent added, AniList untouched")
        return EXIT_OK
    if not queued:
        return EXIT_ERROR if failed_plans else EXIT_SKIP

    actions = f"download {torrent_count} torrent(s) across {len(queued)} series"
    if not args.yes and not confirm(f"Confirm  : {actions}?"):
        print("Cancelled: nothing downloaded, AniList untouched")
        return EXIT_SKIP

    failed = 0
    for result in queued:
        if commit_plan(client, result, args, do_planning=False) != EXIT_OK:
            failed += 1
    return EXIT_ERROR if failed or failed_plans else EXIT_OK


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anime-fetch",
        description="Download a HEVC/AV1 anime release into the Seanime library.",
    )
    parser.add_argument("query", nargs="*",
                        help="anime title (romaji, English or native); omit to read the clipboard")
    parser.add_argument("--all", action="store_true",
                        help="process every Releasing series on the AniList Watching list; "
                             "download aired episodes that are neither watched nor on disk")
    parser.add_argument("--provider", action="append", metavar="NAME",
                        help=f"torrent provider (repeatable or comma separated); default {DEFAULT_PROVIDER}")
    parser.add_argument("--lib", default=DEFAULT_LIB, help=f"library root (default {DEFAULT_LIB})")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"Seanime base URL (default {DEFAULT_BASE})")
    parser.add_argument("--pick", type=int, metavar="N", help="pick the Nth AniList search result")
    parser.add_argument("--episodes", type=int, metavar="N",
                        help="target episode count (default: all episodes for a finished series, "
                             "or the aired count for a releasing one)")
    parser.add_argument("--dry-run", action="store_true", help="search and select, but do not download")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="download without asking for confirmation")
    parser.add_argument("--ignore-library", action="store_true",
                        help="select releases even when the title is already in the library")
    parser.add_argument("--no-planning", action="store_true", help="do not touch the AniList Planning list")
    parser.add_argument("--max-batch-probes", type=int, default=20,
                        help="how many batch torrents to inspect for episode coverage (default 20)")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    providers: list[str] = []
    for raw in args.provider or [DEFAULT_PROVIDER]:
        providers += [p.strip() for p in raw.split(",") if p.strip()]
    providers = list(dict.fromkeys(providers))
    clients = [Seanime(args.base, provider) for provider in providers]
    client = clients[0]

    if args.all:
        return run_all(args, clients)

    query = " ".join(args.query).strip()
    if not query:
        text = clipboard_text()
        if text is None:
            print("error: no title given and the system clipboard is empty", file=sys.stderr)
            return EXIT_ERROR
        query = query_from_text(text)
        if not query:
            snippet = " ".join(text.split())[:100]
            print(f"error: cannot derive a title from the clipboard ({snippet!r}); "
                  "pass the title as an argument", file=sys.stderr)
            return EXIT_ERROR
        print(f"Clipboard: {query}")

    try:
        media = resolve_media(client, query, args.pick)
    except Ambiguous as exc:
        print(exc, file=sys.stderr)
        return EXIT_AMBIGUOUS
    except (SeanimeError, HttpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    romaji = (media.get("title") or {}).get("romaji") or (media.get("title") or {}).get("english") or query
    ongoing = (media.get("status") or "") in ONGOING_STATUSES
    if args.episodes is not None:
        total = args.episodes
    elif ongoing:
        total = aired_episode_count(media)
    else:
        total = media.get("episodes")

    aired_note = " (aired so far)" if ongoing else ""
    print(f"AniList  : {romaji} ({describe_media(media)}, {total or '?'} episodes{aired_note})")
    if not isinstance(total, int) or total <= 0:
        if ongoing:
            print("error: AniList does not report an aired episode count; pass --episodes N",
                  file=sys.stderr)
        else:
            print("error: episode count is unknown, cannot verify coverage", file=sys.stderr)
        return EXIT_ERROR

    destination = Path(args.lib) / safe_folder(romaji)

    collection: dict[str, Any] = {}
    entry: dict[str, Any] | None = None
    try:
        collection = client.collection()
        entry = Seanime.find_entry(collection, media["id"])
    except (SeanimeError, HttpError) as exc:
        if args.verbose:
            print(f"warning: could not read the library collection: {exc}", file=sys.stderr)

    main_files = int(((entry or {}).get("libraryData") or {}).get("mainFileCount") or 0)
    on_disk = count_videos(destination)
    titles = titles_of(media)[:3] or [query]

    # A finished series is all-or-nothing: any files mean it is already done.
    # An ongoing series is incremental: only fetch episodes still missing from
    # the library folder, so newly aired episodes can be picked up on a re-run.
    wanted = set(range(1, total + 1))
    if not args.ignore_library and (main_files > 0 or on_disk > 0):
        if ongoing:
            existing = library_episodes(destination, entry, titles)
            if existing:
                wanted -= {number for number in existing if number <= total}
                print(f"Library  : {len(existing)} episode(s) on disk, "
                      f"{len(wanted)} aired episode(s) missing")
                if not wanted:
                    print("Nothing to do: all aired episodes are already in the library")
                    if not args.no_planning:
                        ensure_planning(client, media, entry, dry_run=args.dry_run)
                    return EXIT_OK
            else:
                where = destination if on_disk else "library entry"
                print(f"Library  : already downloaded ({max(main_files, on_disk)} video files, {where})")
                print("Nothing to do: cannot tell which episodes are present; "
                      "use --ignore-library to search anyway")
                if not args.no_planning:
                    ensure_planning(client, media, entry, dry_run=args.dry_run)
                return EXIT_OK
        else:
            where = destination if on_disk else "library entry"
            print(f"Library  : already downloaded ({max(main_files, on_disk)} video files, {where})")
            print("Nothing to do.")
            if not args.no_planning:
                ensure_planning(client, media, entry, dry_run=args.dry_run)
            return EXIT_OK

    result = build_plan(clients, media, entry, args, total=total, wanted=wanted, query=query)
    if result.code != EXIT_OK:
        return result.code
    print_plan(result.plan, result.destination, wanted=result.wanted)

    if args.dry_run:
        print("Dry run  : no torrent added, AniList untouched")
        return EXIT_OK

    status = ((entry or {}).get("listData") or {}).get("status")
    actions = [f"download {len(result.plan.torrents)} torrent(s)"]
    if not args.no_planning and not status:
        actions.append("add to AniList Planning")
    if not args.yes and not confirm(f"Confirm  : {' and '.join(actions)}?"):
        print("Cancelled: nothing downloaded, AniList untouched")
        return EXIT_SKIP

    return commit_plan(client, result, args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
