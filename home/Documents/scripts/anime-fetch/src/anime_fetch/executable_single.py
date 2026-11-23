"""Single-title workflow: resolve, inspect the library, then download."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Type

from .config import EXIT_AMBIGUOUS, EXIT_ERROR, EXIT_OK, EXIT_SKIP
from .media import (
    aired_episode_count,
    count_videos,
    describe_media,
    is_ongoing,
    library_episodes,
    safe_folder,
    titles_of,
)
from .net import HttpError
from .plan import build_plan, commit_plan, ensure_planning
from .report import print_plan
from .resolve import Ambiguous, resolve_media
from .seanime import Seanime, SeanimeError
from .text import clipboard_text, query_from_text


def run(
    args: argparse.Namespace,
    clients: list[Seanime],
    *,
    seanime_cls: Type[Seanime],
    confirm_fn: Callable[[str], bool],
) -> int:
    client = clients[0]
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
    ongoing = is_ongoing(media)
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
        entry = seanime_cls.find_entry(collection, media["id"])
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
    if result.plan is None:  # pragma: no cover - build_plan sets a plan on EXIT_OK
        return EXIT_ERROR
    print_plan(result.plan, result.destination, wanted=result.wanted)

    if args.dry_run:
        print("Dry run  : no torrent added, AniList untouched")
        return EXIT_OK

    status = ((entry or {}).get("listData") or {}).get("status")
    actions = [f"download {len(result.plan.torrents)} torrent(s)"]  # type: ignore[union-attr]
    if not args.no_planning and not status:
        actions.append("add to AniList Planning")
    if not args.yes and not confirm_fn(f"Confirm  : {' and '.join(actions)}?"):
        print("Cancelled: nothing downloaded, AniList untouched")
        return EXIT_SKIP

    return commit_plan(client, result, args)
