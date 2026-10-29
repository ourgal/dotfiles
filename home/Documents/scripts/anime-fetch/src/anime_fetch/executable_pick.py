"""Codec filtering and release selection.

Rules (the user's standard):
  * only HEVC (x265) or AV1 releases are acceptable;
  * a complete release set (every episode 1..N) wins over piecemeal singles;
  * a Judas-style season batch is preferred, then DKB/EMBER/ASW-style x265
    groups, then anything AV1;
  * no acceptable release for even one episode => download nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath

VIDEO_EXTS = {".mkv", ".mp4", ".webm", ".avi", ".m4v", ".ts"}

_HEVC = re.compile(r"(?i)(?<![a-z0-9])(?:hevc|x265|h\.?265)(?![a-z0-9])")
_AV1 = re.compile(r"(?i)(?<![a-z0-9])av1(?![a-z0-9])")
_RES_BAD = re.compile(r"(?i)(?<![0-9])(?:480p|576p|720p|2160p|4k)(?![0-9])")

_EP_PATTERNS = (
    re.compile(r"[Ss]\d{1,2}[Ee](\d{1,3})(?:v\d)?"),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:ep?|episode)\s?(\d{1,3})(?:v\d)?(?![0-9])"),
    re.compile(r"\s-\s(\d{1,3})(?:v\d)?(?![0-9])"),
    re.compile(r"[\[\(]\s*(\d{1,3})(?:v\d)?\s*[\]\)]"),
)

_SPECIAL_FILE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:nc(?:op|ed)?|op\d?|ed\d?|sp\d?|pv\d?|cm|menu|preview|sample|extra[s]?)(?:[^a-z0-9]|$)"
)

_STOPWORDS = {
    "the", "a", "an", "of", "no", "to", "wa", "ga", "wo", "ni", "de",
    "and", "season", "part", "pt", "batch", "tv", "ova", "specials",
}

_ROMAN = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi"}
_ROMAN_TO_INT = {v: k for k, v in _ROMAN.items()}

# tier 0 = the house style, tier 1 = other established x265 groups,
# tier 2 = AV1 groups / anything else that passed the codec filter.
_TIER1_GROUPS = {"dkb", "ember", "asw", "erai-raws", "erai", "varyg", "toonshub", "judas"}


def codec_of(name: str) -> str | None:
    if _HEVC.search(name):
        return "hevc"
    if _AV1.search(name):
        return "av1"
    return None


def acceptable_release(name: str) -> bool:
    """True when the name is a 1080p HEVC/AV1 release."""
    if codec_of(name) is None:
        return False
    if _RES_BAD.search(name):
        return False
    return True


def episode_of(text: str) -> int | None:
    """Best-effort episode number from a file path or torrent name."""
    name = PurePath(text.replace("\\", "/")).name
    stem = name.rsplit(".", 1)[0]
    for pattern in _EP_PATTERNS:
        match = pattern.search(stem)
        if match:
            number = int(match.group(1))
            if 0 < number < 1000:
                return number
    return None


def release_group(torrent: dict) -> str:
    group = (torrent.get("releaseGroup") or "").strip()
    if group:
        return group
    name = torrent.get("name") or ""
    bracketed = re.match(r"\s*\[([^\]]+)\]", name)
    if bracketed:
        return bracketed.group(1).strip()
    suffixed = re.search(r"-\s*([A-Za-z0-9][\w.-]*)\s*$", name)
    if suffixed:
        return suffixed.group(1)
    return "unknown"


def tier_of(group: str, codec: str | None) -> int:
    lowered = group.strip().lower()
    if lowered == "judas":
        return 0
    if lowered in _TIER1_GROUPS:
        return 1
    return 2 if codec == "av1" else 1


def words(title: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in _STOPWORDS]


def season_hint(title: str) -> int | None:
    tokens = re.findall(r"[A-Za-z0-9]+", title)
    if not tokens:
        return None
    last = tokens[-1].lower()
    if last in _ROMAN_TO_INT:
        return _ROMAN_TO_INT[last]
    if last.isdigit():
        return int(last)
    return None


def mentions_title(name: str, titles: list[str]) -> bool:
    tokens = re.findall(r"[a-z0-9]+", name.lower())
    haystack = set(tokens)
    joined = " ".join(tokens)
    for title in titles:
        wanted = words(title)
        if not wanted:
            continue
        core = wanted[:3]
        if all(word in haystack for word in core):
            return True
        if len(wanted) > len(core) and " ".join(wanted) in joined:
            return True
    return False


def matches_season(name: str, hint: int | None) -> bool:
    if not hint:
        return True
    lowered = name.lower()
    roman = _ROMAN.get(hint, "")
    if re.search(rf"s0*{hint}(?![0-9])", lowered):
        return True
    if re.search(rf"season\s*0*{hint}(?![0-9])", lowered):
        return True
    if roman and re.search(rf"(?<![a-z]){roman}(?![a-z])", lowered):
        return True
    if re.search(rf"(?<![a-z0-9]){hint}(?![a-z0-9])", lowered):
        return True
    return False


def coverage_from_files(paths: list[str], total: int) -> set[int]:
    episodes: set[int] = set()
    for path in paths:
        pure = PurePath(path.replace("\\", "/"))
        if pure.suffix.lower() not in VIDEO_EXTS:
            continue
        if _SPECIAL_FILE.search(pure.stem):
            continue
        number = episode_of(pure.name)
        if number is not None and 1 <= number <= total:
            episodes.add(number)
    return episodes


def is_batch(torrent: dict) -> bool:
    if torrent.get("isBatch"):
        return True
    name = torrent.get("name") or ""
    if re.search(r"(?i)\(batch\)|\[batch\]", name):
        return True
    return bool(re.search(r"\((?:S\d{1,2})?\s*\d{1,3}\s*-\s*\d{1,3}\)", name))


@dataclass
class Candidate:
    torrent: dict
    episodes: set[int] = field(default_factory=set)
    files: int = 0
    codec: str = ""

    @property
    def group(self) -> str:
        return release_group(self.torrent)

    @property
    def seeders(self) -> int:
        try:
            return int(self.torrent.get("seeders") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def size(self) -> int:
        try:
            return int(self.torrent.get("size") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def tier(self) -> int:
        return tier_of(self.group, self.codec)

    def sort_key(self) -> tuple:
        return (self.tier, -self.seeders, -self.size)


@dataclass
class Plan:
    torrents: list[Candidate]
    strategy: str  # "batch" or "per-episode"
    group: str = ""
    missing: list[int] = field(default_factory=list)

    @property
    def episodes(self) -> list[int]:
        covered: set[int] = set()
        for cand in self.torrents:
            covered |= cand.episodes
        return sorted(covered)

    @property
    def size(self) -> int:
        return sum(c.size for c in self.torrents)

    @property
    def min_seeders(self) -> int:
        return min((c.seeders for c in self.torrents), default=0)


def choose(candidates: list[Candidate], total: int) -> Plan | None:
    """Cover every episode 1..N, preferring better groups and no overlap.

    A Judas-style batch wins because its tier sorts first; leftover episodes are
    then filled from the next-best group. Torrents whose files would duplicate
    already covered episodes are only used when nothing else is left.
    """
    wanted = set(range(1, total + 1))
    pool = [cand for cand in candidates if cand.episodes & wanted]
    if not pool:
        return None
    for episode in wanted:
        if not any(episode in cand.episodes for cand in pool):
            return None

    remaining = set(wanted)
    picked: list[Candidate] = []
    while remaining:
        best: Candidate | None = None
        best_key: tuple | None = None
        for cand in pool:
            fresh = cand.episodes & remaining
            if not fresh:
                continue
            overlap = len(cand.episodes & (wanted - remaining))
            key = (cand.tier, 1 if overlap else 0, -len(fresh), -cand.seeders, -cand.size)
            if best_key is None or key < best_key:
                best_key, best = key, cand
        assert best is not None
        picked.append(best)
        remaining -= best.episodes & remaining

    if len(picked) == 1 and len(picked[0].episodes & wanted) == total:
        strategy = "single-batch"
    elif len({c.group.lower() for c in picked}) == 1:
        strategy = "group-set"
    else:
        strategy = "mixed"
    return Plan(torrents=picked, strategy=strategy, group=picked[0].group)


def missing_episodes(candidates: list[Candidate], total: int) -> list[int]:
    covered: set[int] = set()
    for cand in candidates:
        covered |= cand.episodes
    return sorted(set(range(1, total + 1)) - covered)
