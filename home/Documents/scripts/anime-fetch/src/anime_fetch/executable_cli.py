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

With no title argument the query is read from the system clipboard. The match
and the selected releases are printed first; nothing is downloaded or added to
AniList until the user confirms.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
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


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anime-fetch",
        description="Download a HEVC/AV1 anime release into the Seanime library.",
    )
    parser.add_argument("query", nargs="*",
                        help="anime title (romaji, English or native); omit to read the clipboard")
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

    providers: list[str] = []
    for raw in args.provider or [DEFAULT_PROVIDER]:
        providers += [p.strip() for p in raw.split(",") if p.strip()]
    providers = list(dict.fromkeys(providers))
    clients = [Seanime(args.base, provider) for provider in providers]
    client = clients[0]

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
            existing = episode_files(destination)
            shared = ((entry or {}).get("libraryData") or {}).get("sharedPath")
            if isinstance(shared, str) and shared:
                existing |= episode_files(Path(shared), titles=titles)
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

    hint = pick.season_hint(titles[0]) if titles else None
    terms = [base_title(t) for t in titles] + titles + [query]
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
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"Search   : {len(found)} candidate release(s) with HEVC/AV1")
    candidates = build_candidates(client, list(found.values()), total,
                                  max_probes=args.max_batch_probes, verbose=args.verbose,
                                  hints=hints)

    plan = pick.choose(candidates, total, wanted=wanted)
    if plan is None and not ongoing:
        # Batch search was incomplete: look for one release per missing episode.
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if missing:
            print(f"Search   : per-episode fallback for {len(missing)} episode(s)")
        extra: dict[str, dict[str, Any]] = {}
        try:
            for episode in missing:
                gather(clients, media, queries[:2], batch=False, episode=episode,
                       titles=titles, hint=hint, found=extra, hints=hints, verbose=args.verbose)
        except (SeanimeError, HttpError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        new_items = [t for k, t in extra.items() if k not in found]
        if new_items:
            candidates += build_candidates(client, new_items, total,
                                           max_probes=args.max_batch_probes, verbose=args.verbose,
                                           hints=hints)
        plan = pick.choose(candidates, total, wanted=wanted)

    if plan is None:
        missing = pick.missing_episodes(candidates, total, wanted=wanted)
        if missing:
            print(f"Skip     : no HEVC/AV1 release covers episode(s) {missing}; nothing downloaded")
        else:
            print("Skip     : no HEVC/AV1 release found; nothing downloaded")
        return EXIT_SKIP

    # A batch may contain episodes that are already on disk; only queue the
    # ones we actually set out to fetch.
    episodes = sorted(set(plan.episodes) & wanted)
    print_plan(plan, destination, wanted=wanted)

    if args.dry_run:
        print("Dry run  : no torrent added, AniList untouched")
        return EXIT_OK

    status = ((entry or {}).get("listData") or {}).get("status")
    actions = [f"download {len(plan.torrents)} torrent(s)"]
    if not args.no_planning and not status:
        actions.append("add to AniList Planning")
    if not args.yes and not confirm(f"Confirm  : {' and '.join(actions)}?"):
        print("Cancelled: nothing downloaded, AniList untouched")
        return EXIT_SKIP

    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create destination folder {destination}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        client.download([c.torrent for c in plan.torrents], str(destination), media, episodes)
    except (SeanimeError, HttpError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"Download : queued {len(plan.torrents)} torrent(s) to {destination}")

    if not args.no_planning:
        try:
            ensure_planning(client, media, entry, dry_run=False)
        except (SeanimeError, HttpError) as exc:
            print(f"warning: download queued but AniList update failed: {exc}", file=sys.stderr)
            return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
