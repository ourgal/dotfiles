"""anime-fetch: check the Seanime library, then download a HEVC/AV1 release.

Standard workflow (matches the user's rules):
  1. resolve the title on AniList through Seanime;
  2. if the library already has files, stop;
  3. search torrents (batch first, then per episode);
  4. accept only HEVC/x265 or AV1 1080p releases, preferring a complete
     Judas-style batch, then DKB/EMBER/ASW-style x265 groups, then AV1;
  5. if any episode has no acceptable release, retry the search once with any
     1080p codec (H.264 included) and use those only for the uncovered
     episodes, so a season can finish as a mixed plan. H.264 is taken only as a
     single-episode fill; an H.264 season pack is never downloaded;
  6. if even that leaves an episode uncovered, download nothing;
  7. otherwise add the torrents and put the title on the AniList Planning list.

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

from . import batch, pick, single
from .config import (
    DEFAULT_LIB,
    EXIT_AMBIGUOUS,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_SKIP,
    ONGOING_STATUSES,
)
from .media import (
    aired_episode_count,
    base_title,
    count_videos,
    describe_media,
    episode_files,
    library_episodes,
    normalize,
    safe_folder,
    series_destination,
    titles_of,
)
from .net import HttpError
from .plan import (
    PlanResult,
    build_plan,
    commit_plan,
    ensure_planning,
)
from .report import human_size, print_plan
from .resolve import Ambiguous, resolve_media
from .search import build_candidates, gather
from .seanime import DEFAULT_BASE, DEFAULT_PROVIDER, Seanime, SeanimeError
from .text import clipboard_text, confirm, query_from_text
from .batch import (
    batch_targets,
    entry_media_id,
    entry_progress,
    run_all,
    select_watching_releasing,
)

# The names above are re-exported so existing callers and tests can keep
# importing them from `anime_fetch.cli`, where they used to live.


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

    if args.all:
        return batch.run_all(args, clients, confirm_fn=confirm)
    return single.run(args, clients, seanime_cls=Seanime, confirm_fn=confirm)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
