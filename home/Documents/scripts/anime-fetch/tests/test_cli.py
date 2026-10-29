"""Tests for the CLI helpers in anime_fetch.cli."""

from __future__ import annotations

import pytest

from anime_fetch import cli

JUDAS_BATCH = "[Judas] Show S01 - Batch (HEVC 1080p)"


# ----------------------------------------------------------------------- utils
@pytest.mark.parametrize(
    ("num", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.00 KiB"),
        (1536, "1.50 KiB"),
        (5 * 1024**3, "5.00 GiB"),
        (2 * 1024**4, "2.00 TiB"),
        (5 * 1024**5, "5120.00 TiB"),
    ],
)
def test_human_size(num: int, expected: str) -> None:
    assert cli.human_size(num) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Mushoku Tensei III: Isekai Ittara Honki Dasu", "Mushoku Tensei III"),
        ("Re:Zero kara Hajimeru Isekai Seikatsu", "ReZero kara Hajimeru Isekai Seikatsu"),
        ("Steins;Gate", "Steins;Gate"),
        ('Bad: Char?*"/<>|', "Bad Char"),
        ("Trailing dots... ", "Trailing dots"),
        ("   ", "Untitled"),
        ("", "Untitled"),
    ],
)
def test_safe_folder(name: str, expected: str) -> None:
    assert cli.safe_folder(name) == expected


def test_count_videos(tmp_path) -> None:
    (tmp_path / "Show - 01.mkv").write_bytes(b"x")
    (tmp_path / "Show - 02.MKV").write_bytes(b"x")
    (tmp_path / "poster.jpg").write_bytes(b"x")
    sub = tmp_path / "Season 1"
    sub.mkdir()
    (sub / "Show - 03.mp4").write_bytes(b"x")
    assert cli.count_videos(tmp_path) == 3
    assert cli.count_videos(tmp_path / "missing") == 0


# -------------------------------------------------------------- matching titles
def test_titles_of_orders_and_filters() -> None:
    media = {
        "title": {"romaji": "Show", "english": None, "native": "番組"},
        "synonyms": ["", "Alt Name", 5],
    }
    assert cli.titles_of(media) == ["Show", "番組", "Alt Name"]


def test_titles_of_empty() -> None:
    assert cli.titles_of({}) == []


def test_normalize() -> None:
    assert cli.normalize("Re:Zero kara Hajimeru Isekai Seikatsu!") == (
        "re zero kara hajimeru isekai seikatsu"
    )


def test_describe_media() -> None:
    media = {
        "id": 154587,
        "format": "TV",
        "seasonYear": 2023,
        "meanScore": 85,
        "genres": ["Action", "Adventure", "Fantasy", "Drama"],
    }
    assert cli.describe_media(media) == "id 154587, TV, 2023, score 85, Action, Adventure, Fantasy"


# ------------------------------------------------------------------- clipboard
def test_query_from_text_plain() -> None:
    assert cli.query_from_text("Mushoku Tensei III\nwatch later") == "Mushoku Tensei III"


def test_query_from_text_url_with_prefix() -> None:
    assert cli.query_from_text("AniList - https://anilist.co/anime/154587/Mushoku-Tensei-III/") == (
        "AniList"
    )


def test_query_from_text_bare_url_slug() -> None:
    assert cli.query_from_text("https://anilist.co/anime/154587/Mushoku-Tensei-III/") == (
        "Mushoku Tensei III"
    )


def test_query_from_text_bare_numeric_url() -> None:
    assert cli.query_from_text("https://anilist.co/anime/154587") == ""


def test_query_from_text_blank_lines() -> None:
    assert cli.query_from_text("\n \n\tShow (HEVC)\n") == "Show (HEVC)"


# ------------------------------------------------------------------ media pick
def test_resolve_media_picks_exact_match() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [
                {"id": 1, "format": "TV", "title": {"romaji": "Other Show"}, "meanScore": 80},
                {"id": 2, "format": "TV", "title": {"romaji": "Mushoku Tensei III"}, "meanScore": 80},
            ]

    media = cli.resolve_media(FakeClient(), "Mushoku Tensei III", pick_index=None)
    assert media["id"] == 2


def test_resolve_media_skips_music_and_adult() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [
                {"id": 1, "format": "MUSIC", "title": {"romaji": "Show OP"}},
                {"id": 2, "format": "TV", "isAdult": True, "title": {"romaji": "Show"}},
            ]

    with pytest.raises(cli.SeanimeError, match="no result"):
        cli.resolve_media(FakeClient(), "Show", pick_index=None)


def test_resolve_media_explicit_index() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": i, "format": "TV", "title": {"romaji": f"Show {i}"}} for i in (1, 2, 3)]

    assert cli.resolve_media(FakeClient(), "Show", pick_index=2)["id"] == 2
    with pytest.raises(cli.SeanimeError, match="--pick"):
        cli.resolve_media(FakeClient(), "Show", pick_index=4)


def test_resolve_media_ambiguous_raises() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": 1, "format": "TV", "title": {"romaji": "Totally Different"}}]

    with pytest.raises(cli.Ambiguous):
        cli.resolve_media(FakeClient(), "Unrelated Query Words Here", pick_index=None)


def test_resolve_media_one_word_query_is_strict() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": 1, "format": "TV", "title": {"romaji": "YaniSuu"}}]

    # loose word overlap is only trusted for queries of 3+ words
    with pytest.raises(cli.Ambiguous):
        cli.resolve_media(FakeClient(), "yani", pick_index=None)


# ------------------------------------------------------------- build_candidates
class StubClient:
    def __init__(self, files_by_name: dict[str, list[str]]) -> None:
        self.files_by_name = files_by_name

    def torrent_files(self, torrent):
        name = torrent.get("name")
        if name not in self.files_by_name:
            raise cli.SeanimeError(f"no such torrent: {name}")
        return self.files_by_name[name]


def _torrent(name: str, batch: bool = False) -> dict:
    return {"name": name, "isBatch": batch, "releaseGroup": "Group", "seeders": 5, "size": 10}


def test_build_candidates_probes_batches() -> None:
    files = [f"Show - {i:02d} [HEVC].mkv" for i in range(1, 13)]
    batch_name = "[Judas] Show S01 - Batch (HEVC 1080p)"
    client = StubClient({batch_name: files})
    torrents = [
        _torrent(batch_name, batch=True),
        _torrent("Show - 01 [HEVC].mkv"),
    ]
    candidates = cli.build_candidates(client, torrents, total=12, max_probes=5, verbose=False)
    batch = next(c for c in candidates if c.torrent["name"] == batch_name)
    assert batch.episodes == set(range(1, 13))
    single = next(c for c in candidates if c.episodes == {1})
    assert single.codec == "hevc"


def test_build_candidates_drops_failing_probe() -> None:
    client = StubClient({})  # every probe raises
    torrents = [
        _torrent(JUDAS_BATCH, batch=True),
        _torrent("Show - 02 [HEVC].mkv"),
    ]
    candidates = cli.build_candidates(client, torrents, total=12, max_probes=5, verbose=False)
    assert [c.episodes for c in candidates] == [{2}]


def test_build_candidates_respects_probe_limit() -> None:
    files = [f"Show - {i:02d} [HEVC].mkv" for i in range(1, 13)]
    names = [JUDAS_BATCH, "B (HEVC)", "C (HEVC)"]
    client = StubClient({name: files for name in names})
    torrents = [_torrent(names[0], batch=True), _torrent(names[1], batch=True),
                _torrent(names[2], batch=True)]
    candidates = cli.build_candidates(client, torrents, total=12, max_probes=2, verbose=False)
    assert len([c for c in candidates if c.episodes]) == 2


def test_build_candidates_ignores_out_of_range_single() -> None:
    client = StubClient({})
    torrents = [_torrent("Show - 99 [HEVC].mkv")]
    assert cli.build_candidates(client, torrents, total=12, max_probes=5, verbose=False) == []


# ---------------------------------------------------------------------- parser
def test_build_parser_defaults() -> None:
    args = cli.build_parser().parse_args(["Mushoku", "Tensei", "III"])
    assert args.query == ["Mushoku", "Tensei", "III"]
    assert args.lib == cli.DEFAULT_LIB
    assert args.base == cli.DEFAULT_BASE
    assert args.pick is None
    assert not args.dry_run
    assert not args.yes
    assert not args.ignore_library
    assert not args.no_planning
    assert args.max_batch_probes == 20


def test_build_parser_repeated_providers() -> None:
    args = cli.build_parser().parse_args(
        ["--provider", "animetosho-new", "--provider", "nyaa", "-y", "--dry-run", "Show"]
    )
    assert args.provider == ["animetosho-new", "nyaa"]
    assert args.yes and args.dry_run
