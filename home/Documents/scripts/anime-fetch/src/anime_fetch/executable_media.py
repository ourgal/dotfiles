"""Title, library-folder and episode-number helpers."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from . import pick
from .config import ONGOING_STATUSES

_PART_SUFFIX = re.compile(
    r"(?i)[\s:\u2013\u2014-]*(?:part|season|cour)\s*\d+(?:st|nd|rd|th)?\s*(?:cour)?[\s:\u2013\u2014-]*$"
)
_ORDINAL_COUR = re.compile(r"(?i)[\s:\u2013\u2014-]*\d+(?:st|nd|rd|th)?\s*cour[\s:\u2013\u2014-]*$")
_JP_COUR = re.compile(r"[\s:\u2013\u2014-]*\d+\s*クール[\s:\u2013\u2014-]*$")


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


def base_title(title: str) -> str:
    """Drop a cour/part marker for torrent searches.

    Releases of a second cour use the base series title plus absolute episode
    numbers ("Show - 14"), so searching "Show Part 2" finds nothing useful.
    """
    cleaned = _PART_SUFFIX.sub("", title)
    cleaned = _ORDINAL_COUR.sub("", cleaned)
    cleaned = _JP_COUR.sub("", cleaned)
    return cleaned.strip(" :\u2013\u2014-") or title


def is_ongoing(media: dict[str, Any]) -> bool:
    return (media.get("status") or "") in ONGOING_STATUSES


def describe_media(media: dict[str, Any]) -> str:
    bits = [f"id {media['id']}", str(media.get("format") or "?")]
    if media.get("seasonYear"):
        bits.append(str(media["seasonYear"]))
    if media.get("meanScore"):
        bits.append(f"score {media['meanScore']}")
    bits += [g for g in (media.get("genres") or []) if isinstance(g, str)][:3]
    return ", ".join(bits)
