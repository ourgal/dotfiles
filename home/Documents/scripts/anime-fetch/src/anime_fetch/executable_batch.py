"""The --all workflow: every Watching + Releasing series in one batch."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .config import EXIT_ERROR, EXIT_OK, EXIT_SKIP
from .media import aired_episode_count, library_episodes, series_destination, titles_of
from .net import HttpError
from .plan import PlanResult, build_plan, commit_plan
from .report import print_plan
from .seanime import Seanime, SeanimeError


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


def run_all(
    args: argparse.Namespace,
    clients: list[Seanime],
    *,
    confirm_fn: Callable[[str], bool],
) -> int:
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

    results_by_index: dict[int, PlanResult] = {}
    pending: list[tuple[int, dict[str, Any], dict[str, Any], int, set[int]]] = []
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
            results_by_index[index] = PlanResult(media, entry, None, destination, set(), [],
                                                 EXIT_SKIP, message)
            continue
        total, wanted = targets
        unwatched = set(wanted)
        wanted -= {number for number in library_episodes(destination, lib_entry, titles)
                   if number <= total}
        if not wanted:
            message = (f"skip     : all {len(unwatched)} unwatched episode(s) "
                       "are already on disk")
            print(f"  [{index}/{len(entries)}] {title}: {message}")
            results_by_index[index] = PlanResult(media, entry, None, destination, set(), [],
                                                 EXIT_SKIP, message)
            continue
        span = f"{min(wanted)}-{max(wanted)}" if len(wanted) > 1 else str(min(wanted))
        on_disk = len(unwatched) - len(wanted)
        note = f", {on_disk} already on disk" if on_disk else ""
        print(f"  [{index}/{len(entries)}] {title}: {len(wanted)} episode(s) "
              f"after progress ({span}){note}")
        pending.append((index, entry, media, total, wanted))

    # What is left is all HTTP torrent searching. Run series concurrently so
    # slow/unavailable feeds do not add up; the cap avoids hammering Seanime.
    if pending:
        def build(item):
            index, entry, media, total, wanted = item
            return index, build_plan(clients, media, entry, args, total=total,
                                     wanted=wanted, echo=False)

        if len(pending) == 1:
            built = [build(pending[0])]
        else:
            with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
                built = list(pool.map(build, pending))
        for index, result in built:
            results_by_index[index] = result

    results = [results_by_index[i] for i in range(1, len(entries) + 1)]
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
    if not args.yes and not confirm_fn(f"Confirm  : {actions}?"):
        print("Cancelled: nothing downloaded, AniList untouched")
        return EXIT_SKIP

    failed = 0
    for result in queued:
        if commit_plan(client, result, args, do_planning=False) != EXIT_OK:
            failed += 1
    return EXIT_ERROR if failed or failed_plans else EXIT_OK
