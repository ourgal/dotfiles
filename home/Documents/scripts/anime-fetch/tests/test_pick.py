"""Tests for the HEVC/AV1 release-selection rules."""

from __future__ import annotations

import pytest

from anime_fetch import pick


# ---------------------------------------------------------------------- codecs
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("[Judas] Mushoku Tensei III - S3 (HEVC 1080p)", "hevc"),
        ("Show x265 1080p", "hevc"),
        ("Show H.265 1080p", "hevc"),
        ("Show H265 1080p", "hevc"),
        ("[AV1] Show 1080p", "av1"),
        ("Show x264 1080p", None),
        ("Show AVC 1080p", None),
        ("Show 1080p", None),
        # a codec tag embedded in a word must not count
        ("HevcFan Fansub 1080p", None),
        # 265 without a codec prefix is not HEVC
        ("Season 265 1080p", None),
    ],
)
def test_codec_of(name: str, expected: str | None) -> None:
    assert pick.codec_of(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("[Judas] Show S01 (HEVC 1080p)", True),
        ("[Group] Show (AV1 1080p)", True),
        ("[Group] Show (x265 720p)", False),
        ("[Group] Show (HEVC 2160p)", False),
        ("[Group] Show (x264 1080p)", False),
    ],
)
def test_acceptable_release(name: str, expected: bool) -> None:
    assert pick.acceptable_release(name) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("[ToonsHub] Show S01E01 1080p WEB-DL DDP2.0 H.264", "h264"),
        ("Show S01 1080p AMZN WEB-DL AAC2.0 x264-Group", "h264"),
        ("Show 1080p AVC", "h264"),
        ("[Judas] Show S01 (HEVC 1080p)", "hevc"),  # good codecs still win
        ("Show 1080p", None),
    ],
)
def test_codec_of_any_codec(name: str, expected: str | None) -> None:
    assert pick.codec_of(name, any_codec=True) == expected


def test_h264_is_only_a_last_resort() -> None:
    # 1080p H.264 is acceptable with any_codec, but still rejects bad resolutions.
    assert pick.acceptable_release("[ToonsHub] Show S01E01 1080p H.264", any_codec=True) is True
    assert pick.acceptable_release("[ToonsHub] Show S01E01 720p H.264", any_codec=True) is False
    assert pick.tier_of("ToonsHub", "h264") == 3
    assert pick.tier_of("ToonsHub", "hevc") == 1
    assert pick.tier_of("SomeAV1", "av1") == 2


# -------------------------------------------------------------------- episodes
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[Judas] Show S01E05 (HEVC 1080p)", 5),
        ("Show - 12 [1080p][HEVC]", 12),
        ("Show Episode 07 [HEVC]", 7),
        ("[Group] Show [EP 23][HEVC 1080p]", 23),
        ("[Group] Show [12][HEVC 1080p]", 12),
        ("Show - 04v2 [HEVC]", 4),
        ("pack/dir/Show - 9 [HEVC].mkv", 9),
        # a hash like [E733B800] must not be read as episode 733
        ("[ASW] Show - 07 [1080p HEVC][E733B800].mkv", 7),
        # "(1080p)" alone must not be read as an episode
        ("[Judas] Show Complete Batch (HEVC 1080p)", None),
        # a 4-digit number is never an episode
        ("Show E1000 [HEVC]", None),
    ],
)
def test_episode_of(text: str, expected: int | None) -> None:
    assert pick.episode_of(text) == expected


# ----------------------------------------------------------------------- group
@pytest.mark.parametrize(
    ("torrent", "expected"),
    [
        ({"name": "[Judas] Show (HEVC)", "releaseGroup": ""}, "Judas"),
        ({"name": "Show (HEVC) - DKB"}, "DKB"),
        ({"name": "Show (HEVC)", "releaseGroup": " EMBER "}, "EMBER"),
        ({"name": "no group here"}, "unknown"),
    ],
)
def test_release_group(torrent: dict, expected: str) -> None:
    assert pick.release_group(torrent) == expected


@pytest.mark.parametrize(
    ("group", "codec", "expected"),
    [
        ("Judas", "hevc", 0),
        ("judas", "hevc", 0),
        ("DKB", "hevc", 1),
        ("EMBER", "hevc", 1),
        ("SomeFans", "hevc", 1),
        ("SomeFans", "av1", 2),
        ("judas-evil", "hevc", 1),  # not an exact "Judas"
    ],
)
def test_tier_of(group: str, codec: str, expected: int) -> None:
    assert pick.tier_of(group, codec) == expected


# ------------------------------------------------------------------ title text
@pytest.mark.parametrize(
    ("name", "titles", "expected"),
    [
        ("[Judas] Mushoku Tensei III - Batch (HEVC)", ["Mushoku Tensei III"], True),
        ("[Judas] Mushoku Tensei III - Batch (HEVC)", ["Mushoku Tensei III: Isekai Ittara Honki Dasu"], True),
        # a two-word title matches when both words appear
        ("[G] Re Zero kara Hajimeru Isekai Seikatsu (HEVC)", ["Re:Zero"], True),
        ("[G] Show (HEVC)", ["Show"], True),
        ("[G] Unrelated Name (HEVC)", ["Show"], False),
        ("[G] Show Specials (HEVC)", [""], False),
    ],
)
def test_mentions_title(name: str, titles: list[str], expected: bool) -> None:
    assert pick.mentions_title(name, titles) == expected


def test_mentions_title_requires_full_words() -> None:
    assert not pick.mentions_title("Mushoku Tensei IIII Batch HEVC", ["Mushoku Tensei III"])


@pytest.mark.parametrize(
    ("name", "hint", "expected"),
    [
        ("Show S02 (HEVC)", 2, True),
        ("Show Season 2 (HEVC)", 2, True),
        ("Show II (HEVC)", 2, True),
        ("Show 2 (HEVC)", 2, True),
        ("Show 12 (HEVC)", 2, False),
        ("Show S01E02 (HEVC)", 2, False),  # the 2 in E02 must not count
        ("Show (HEVC)", 2, False),
        ("Show (HEVC)", 0, True),  # no hint matches everything
    ],
)
def test_matches_season(name: str, hint: int, expected: bool) -> None:
    assert pick.matches_season(name, hint) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Mushoku Tensei III", 3),
        ("Show Season 4", 4),
        # "Part 2" / "Cour 2" are the same season, with absolute episode numbers
        ("Show Part 2", None),
        ("Show Cour 2", None),
        # "2nd" is not the last token, so no hint is derived
        ("Show 2nd Season", None),
        ("Re:Zero", None),
        ("Show Movie", None),
    ],
)
def test_season_hint(title: str, expected: int | None) -> None:
    assert pick.season_hint(title) == expected


# -------------------------------------------------------------------- coverage
def test_coverage_from_files() -> None:
    paths = [
        "Show - 01 [HEVC].mkv",
        "Show - 02 [HEVC].mkv",
        "Show - 02v2 [HEVC].mkv",
        "Show - 03 [HEVC].mp4",
        "Show - NCOP [HEVC].mkv",
        "Show SP 1 [HEVC].mkv",
        "Show - 99 [HEVC].mkv",
        "cover.jpg",
    ]
    assert pick.coverage_from_files(paths, total=12) == {1, 2, 3}


def test_is_batch() -> None:
    assert pick.is_batch({"isBatch": True, "name": "Show"})
    assert pick.is_batch({"name": "Show S01 (Batch) (HEVC)"})
    assert pick.is_batch({"name": "Show (01-12) (HEVC)"})
    assert pick.is_batch({"name": "Show (S01 01-12) (HEVC)"})
    assert not pick.is_batch({"name": "Show - 01 (HEVC)"})


# ---------------------------------------------------------------------- choose
def _candidate(
    name: str,
    episodes: set[int],
    *,
    group: str = "Group",
    codec: str = "hevc",
    seeders: int = 10,
    size: int = 1,
) -> pick.Candidate:
    torrent = {"name": name, "releaseGroup": group, "seeders": seeders, "size": size}
    return pick.Candidate(torrent=torrent, episodes=episodes, codec=codec)


JUDAS_BATCH = "[Judas] Show S01 - Batch (HEVC 1080p)"


def test_choose_prefers_batch() -> None:
    batch = _candidate(JUDAS_BATCH, set(range(1, 13)), group="Judas")
    single = _candidate("Show - 01 (HEVC)", {1}, group="DKB")
    plan = pick.choose([single, batch], total=12)
    assert plan is not None
    assert plan.strategy == "single-batch"
    assert [c.group for c in plan.torrents] == ["Judas"]


def test_choose_fills_missing_episodes() -> None:
    dkb = _candidate("[DKB] Show Vol.1 (HEVC)", {1, 2, 3, 4}, group="DKB")
    ember = _candidate("[EMBER] Show Vol.2 (HEVC)", {5, 6, 7, 8}, group="EMBER")
    plan = pick.choose([ember, dkb], total=8)
    assert plan is not None
    assert plan.strategy == "mixed"
    assert plan.episodes == list(range(1, 9))


def test_choose_rejects_incomplete_coverage() -> None:
    dkb = _candidate("[DKB] Show Vol.1 (HEVC)", {1, 2, 3})
    assert pick.choose([dkb], total=12) is None


def test_choose_mixes_h264_into_gaps_only() -> None:
    hevc = _candidate("[DKB] Show 1-11 (HEVC 1080p)", set(range(1, 12)),
                      group="DKB", codec="hevc")
    h264 = _candidate("[ToonsHub] Show - 12 (1080p H.264)", {12},
                      group="ToonsHub", codec="h264")
    plan = pick.choose([h264, hevc], total=12)
    assert plan is not None
    assert plan.strategy == "mixed"
    assert [c.codec for c in plan.torrents] == ["hevc", "h264"]
    assert plan.episodes == list(range(1, 13))


def test_choose_keeps_hevc_when_h264_could_cover_the_rest() -> None:
    hevc = _candidate("[DKB] Show 1-4 (HEVC 1080p)", {1, 2, 3, 4},
                      group="DKB", codec="hevc", seeders=1)
    h264 = _candidate("[ToonsHub] Show 1-4 (1080p H.264)", {1, 2, 3, 4},
                      group="ToonsHub", codec="h264", seeders=99)
    plan = pick.choose([h264, hevc], total=4)
    assert plan is not None
    assert [c.codec for c in plan.torrents] == ["hevc"]


def test_choose_never_takes_h264_season_pack() -> None:
    # The H.264 pack would cover episode 12, but a season pack in H.264 is
    # never downloaded: only a single-episode H.264 release may fill the gap.
    hevc = _candidate("[DKB] Show 1-11 (HEVC 1080p)", set(range(1, 12)), group="DKB")
    pack = _candidate("[ToonsHub] Show S01 (1080p H.264)", set(range(1, 13)),
                      group="ToonsHub", codec="h264")
    assert pick.choose([hevc, pack], total=12) is None
    assert pick.missing_episodes([hevc, pack], total=12) == [12]

    single = _candidate("[ToonsHub] Show - 12 (1080p H.264)", {12},
                        group="ToonsHub", codec="h264")
    plan = pick.choose([hevc, pack, single], total=12)
    assert plan is not None
    assert [c.codec for c in plan.torrents] == ["hevc", "h264"]
    assert plan.torrents[1].episodes == {12}


def test_choose_prefers_one_group_per_episode() -> None:
    dkb = _candidate("[DKB] Show Vol.1 (HEVC)", {1, 2, 3}, group="DKB", seeders=99)
    ember = _candidate("[EMBER] Show Vol.1-2 (HEVC)", {1, 2, 3, 4}, group="EMBER")
    plan = pick.choose([dkb, ember], total=4)
    assert plan is not None
    assert {c.group for c in plan.torrents} == {"EMBER"}


def test_choose_prefers_non_overlapping_torrent() -> None:
    # EMBER covers episodes 4-6 without overlapping the Judas batch, so it wins
    # over the higher-seeded group whose files would duplicate episodes 3-6.
    judas = _candidate(JUDAS_BATCH, {1, 2, 3}, group="Judas")
    seeded = _candidate("[EMBER] Show 3-6 (HEVC)", {3, 4, 5, 6}, group="EMBER", seeders=99)
    clean = _candidate("[ASW] Show 4-6 (HEVC)", {4, 5, 6}, group="ASW", seeders=1)
    plan = pick.choose([judas, seeded, clean], total=6)
    assert plan is not None
    assert [c.group for c in plan.torrents] == ["Judas", "ASW"]
    assert plan.episodes == [1, 2, 3, 4, 5, 6]


def test_plan_properties() -> None:
    batch = _candidate(JUDAS_BATCH, {1, 2, 3}, group="Judas", seeders=7, size=100)
    plan = pick.choose([batch], total=3)
    assert plan is not None
    assert plan.episodes == [1, 2, 3]
    assert plan.size == 100
    assert plan.min_seeders == 7
    assert plan.group == "Judas"


def test_missing_episodes() -> None:
    covered = [_candidate("Show - 01 (HEVC)", {1}), _candidate("Show - 03 (HEVC)", {3})]
    assert pick.missing_episodes(covered, total=4) == [2, 4]


# ------------------------------------------------------- partial (releasing) sets
def test_choose_covers_only_wanted_episodes() -> None:
    old = _candidate("[DKB] Show 1-2 (HEVC)", {1, 2}, group="DKB")
    new = _candidate("[ASW] Show 3-4 (HEVC)", {3, 4}, group="ASW")
    plan = pick.choose([old, new], total=4, wanted={3, 4})
    assert plan is not None
    assert [c.group for c in plan.torrents] == ["ASW"]


def test_choose_rejects_partial_wanted_coverage() -> None:
    partial = _candidate("[DKB] Show 3-4 (HEVC)", {3, 4})
    assert pick.choose([partial], total=5, wanted={3, 5}) is None


def test_missing_episodes_respects_wanted() -> None:
    covered = [_candidate("Show 1-2 (HEVC)", {1, 2})]
    assert pick.missing_episodes(covered, total=4, wanted={2, 4}) == [4]
