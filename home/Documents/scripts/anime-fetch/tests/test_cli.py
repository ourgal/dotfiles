"""Tests for the CLI helpers in anime_fetch.cli."""

from __future__ import annotations

from typing import cast

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


def test_aired_episode_count() -> None:
    assert cli.aired_episode_count({"nextAiringEpisode": {"episode": 1181}}) == 1180
    assert cli.aired_episode_count({"nextAiringEpisode": {"episode": 2}}) == 1
    assert cli.aired_episode_count({"nextAiringEpisode": {"episode": 1}}) is None
    assert cli.aired_episode_count({"nextAiringEpisode": None}) is None
    assert cli.aired_episode_count({}) is None


def test_episode_files(tmp_path) -> None:
    folder = tmp_path / "Show"
    folder.mkdir()
    for name in (
        "[ASW] Show - 01 [HEVC].mkv",
        "[ASW] Show - 02 [HEVC].MKV",
        "[ASW] Show S01E05 [HEVC].mkv",
        "poster.jpg",
    ):
        (folder / name).write_bytes(b"x")
    sub = folder / "Season 2"
    sub.mkdir()
    (sub / "Show - 08 [HEVC].mp4").write_bytes(b"x")
    assert cli.episode_files(folder) == {1, 2, 5, 8}
    assert cli.episode_files(tmp_path / "missing") == set()


def test_episode_files_title_filter(tmp_path) -> None:
    folder = tmp_path / "Library"
    folder.mkdir()
    (folder / "[A] Mushoku Tensei - 01 [HEVC].mkv").write_bytes(b"x")
    (folder / "[B] Other Show - 02 [HEVC].mkv").write_bytes(b"x")
    assert cli.episode_files(folder, titles=["Mushoku Tensei"]) == {1}


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


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Chitose-kun wa Ramune Bin no Naka Part 2", "Chitose-kun wa Ramune Bin no Naka"),
        ("Chitose Is in the Ramune Bottle 2nd Cour", "Chitose Is in the Ramune Bottle"),
        ("千歳くんはラムネ瓶のなか 2クール", "千歳くんはラムネ瓶のなか"),
        ("Show Season 4", "Show"),
        ("Mushoku Tensei III", "Mushoku Tensei III"),
        ("Part 2", "Part 2"),
    ],
)
def test_base_title(title: str, expected: str) -> None:
    assert cli.base_title(title) == expected


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

    media = cli.resolve_media(cast(cli.Seanime, FakeClient()), "Mushoku Tensei III", pick_index=None)
    assert media["id"] == 2


def test_resolve_media_skips_music_and_adult() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [
                {"id": 1, "format": "MUSIC", "title": {"romaji": "Show OP"}},
                {"id": 2, "format": "TV", "isAdult": True, "title": {"romaji": "Show"}},
            ]

    with pytest.raises(cli.SeanimeError, match="no result"):
        cli.resolve_media(cast(cli.Seanime, FakeClient()), "Show", pick_index=None)


def test_resolve_media_explicit_index() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": i, "format": "TV", "title": {"romaji": f"Show {i}"}} for i in (1, 2, 3)]

    assert cli.resolve_media(cast(cli.Seanime, FakeClient()), "Show", pick_index=2)["id"] == 2
    with pytest.raises(cli.SeanimeError, match="--pick"):
        cli.resolve_media(cast(cli.Seanime, FakeClient()), "Show", pick_index=4)


def test_resolve_media_ambiguous_raises() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": 1, "format": "TV", "title": {"romaji": "Totally Different"}}]

    with pytest.raises(cli.Ambiguous):
        cli.resolve_media(cast(cli.Seanime, FakeClient()), "Unrelated Query Words Here", pick_index=None)


def test_resolve_media_one_word_query_is_strict() -> None:
    class FakeClient:
        def search_anime(self, query, per_page=10):
            return [{"id": 1, "format": "TV", "title": {"romaji": "YaniSuu"}}]

    # loose word overlap is only trusted for queries of 3+ words
    with pytest.raises(cli.Ambiguous):
        cli.resolve_media(cast(cli.Seanime, FakeClient()), "yani", pick_index=None)


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
    candidates = cli.build_candidates(cast(cli.Seanime, client), torrents, total=12, max_probes=5, verbose=False)
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
    candidates = cli.build_candidates(cast(cli.Seanime, client), torrents, total=12, max_probes=5, verbose=False)
    assert [c.episodes for c in candidates] == [{2}]


def test_build_candidates_respects_probe_limit() -> None:
    files = [f"Show - {i:02d} [HEVC].mkv" for i in range(1, 13)]
    names = [JUDAS_BATCH, "B (HEVC)", "C (HEVC)"]
    client = StubClient({name: files for name in names})
    torrents = [_torrent(names[0], batch=True), _torrent(names[1], batch=True),
                _torrent(names[2], batch=True)]
    candidates = cli.build_candidates(cast(cli.Seanime, client), torrents, total=12, max_probes=2, verbose=False)
    assert len([c for c in candidates if c.episodes]) == 2


def test_build_candidates_ignores_out_of_range_single() -> None:
    client = StubClient({})
    torrents = [_torrent("Show - 99 [HEVC].mkv")]
    assert cli.build_candidates(cast(cli.Seanime, client), torrents, total=12, max_probes=5, verbose=False) == []


def test_build_candidates_uses_requested_episode_hint() -> None:
    # Cour sequels continue with absolute numbers (S01E14 = entry episode 1);
    # Seanime already mapped the request, so trust that over the filename.
    name = "[Erai-raws] Show S01E14 [1080p HEVC]"
    client = StubClient({})
    hints: dict[str, int] = {name.lower(): 1}
    candidates = cli.build_candidates(
        cast(cli.Seanime, client), [_torrent(name)], total=6, max_probes=5, verbose=False, hints=hints
    )
    assert [c.episodes for c in candidates] == [{1}]


def test_gather_records_requested_episode() -> None:
    class FakeClient:
        def search_torrents(self, media, query, *, batch=None, episode=None, **kwargs):
            return [{"name": "[Erai-raws] Show S01E14 [1080p HEVC]", "seeders": 1, "size": 1}]

    found: dict = {}
    hints: dict = {}
    cli.gather(cast(list[cli.Seanime], [FakeClient()]), {"id": 1}, ["Show"], batch=False, episode=1,
               titles=["Show"], hint=None, found=found, hints=hints)
    assert len(found) == 1
    assert list(hints.values()) == [1]


def test_gather_passes_low_retries_and_keeps_working_queries() -> None:
    calls: list = []

    class FakeClient:
        def search_torrents(self, media, query, *, batch=None, episode=None, **kwargs):
            calls.append((query, kwargs.get("retries")))
            if query == "bad":
                raise cli.SeanimeError("feed_unavailable")
            return [{"name": "[ASW] Show - 01 [HEVC 1080p]", "seeders": 1, "size": 1}]

    found: dict = {}
    cli.gather(cast(list[cli.Seanime], [FakeClient()]), {"id": 1}, ["bad", "good"], batch=False, episode=1,
               titles=["Show"], hint=None, found=found)

    assert calls == [("bad", 1), ("good", 1)]
    assert len(found) == 1


def test_gather_skips_failed_query() -> None:
    class FlakyClient:
        def search_torrents(self, media, query, *, batch=None, episode=None, **kwargs):
            if query == "bad":
                raise cli.SeanimeError("feed_unavailable")
            return [{"name": "[ASW] Show - 01 [HEVC 1080p]", "seeders": 1, "size": 1}]

    found: dict = {}
    hints: dict = {}
    cli.gather(cast(list[cli.Seanime], [FlakyClient()]), {"id": 1}, ["bad", "good"], batch=False, episode=1,
               titles=["Show"], hint=None, found=found, hints=hints)
    assert len(found) == 1
    assert list(hints.values()) == [1]


def test_gather_raises_when_every_query_fails() -> None:
    class FailingClient:
        def search_torrents(self, media, query, *, batch=None, episode=None, **kwargs):
            raise cli.SeanimeError("down")

    with pytest.raises(cli.SeanimeError, match="all torrent searches failed"):
        cli.gather(cast(list[cli.Seanime], [FailingClient()]), {"id": 1}, ["x"], batch=False, episode=1,
                   titles=["Show"], hint=None, found={})


# ---------------------------------------------------------------------- parser
def test_build_parser_defaults() -> None:
    args = cli.build_parser().parse_args(["Mushoku", "Tensei", "III"])
    assert args.query == ["Mushoku", "Tensei", "III"]
    assert args.lib == cli.DEFAULT_LIB
    assert args.base == cli.DEFAULT_BASE
    assert args.pick is None
    assert args.episodes is None
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


def test_build_parser_episodes_override() -> None:
    args = cli.build_parser().parse_args(["Show", "--episodes", "12"])
    assert args.episodes == 12


# ------------------------------------------------------------ releasing series
RELEASING = {
    "id": 7,
    "status": "RELEASING",
    "format": "TV",
    "title": {"romaji": "Show"},
    "synonyms": [],
    "nextAiringEpisode": {"episode": 5},  # four episodes have aired
}

FINISHED = {
    "id": 8,
    "status": "FINISHED",
    "format": "TV",
    "title": {"romaji": "Show"},
    "synonyms": [],
    "episodes": 4,
}


class FakeSeanime:
    """Offline Seanime stub that records downloads and planning updates."""

    media = RELEASING

    def __init__(self, base, provider):
        self.base = base
        self.provider = provider
        self.downloads: list = []
        self.planning: list = []
        self.search_calls: list = []
        self.batch = {
            "name": "[Judas] Show S01 - Batch (HEVC 1080p)",
            "isBatch": True, "releaseGroup": "Judas", "seeders": 20, "size": 100,
        }
        self.single4 = {
            "name": "[ASW] Show - 04 (HEVC 1080p)",
            "releaseGroup": "ASW", "seeders": 5, "size": 10,
        }

    def search_anime(self, query, per_page=10):
        return [self.media]

    def collection(self):
        return {"lists": []}

    def search_torrents(self, media, query, *, batch=None, episode=None, **kwargs):
        self.search_calls.append({"batch": batch, "episode": episode, "query": query})
        if batch is True:
            return [self.batch]
        if batch is False and episode is not None:
            if episode == 4:
                return [self.single4]
            return [{
                "name": f"[ASW] Show - {episode:02d} (HEVC 1080p)",
                "releaseGroup": "ASW", "seeders": 5, "size": 10,
            }]
        return []

    def torrent_files(self, torrent):
        if torrent is self.batch:
            return [f"[Judas] Show - {i:02d} [HEVC 1080p].mkv" for i in range(1, 5)]
        number = cli.pick.episode_of(torrent["name"])
        return [f"[ASW] Show - {number:02d} [HEVC 1080p].mkv"]

    def download(self, torrents, destination, media, episodes):
        self.downloads.append((list(torrents), destination, media, episodes))

    def set_planning(self, media_id):
        self.planning.append(media_id)


def _fake_client(monkeypatch):
    instances = []

    def factory(*args, **kwargs):
        client = FakeSeanime(*args, **kwargs)
        instances.append(client)
        return client

    setattr(factory, "find_entry", cli.Seanime.find_entry)  # main() calls it on the class
    monkeypatch.setattr(cli, "Seanime", factory)
    return instances


def _write_episodes(folder, numbers):
    folder.mkdir(parents=True)
    for number in numbers:
        (folder / f"[ASW] Show - {number:02d} [HEVC 1080p].mkv").write_bytes(b"x")


def test_releasing_series_downloads_only_missing_episodes(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    _write_episodes(tmp_path / "Show", [1, 2, 3])

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert len(instances[0].downloads) == 1
    assert instances[0].downloads[0][3] == [4]
    assert instances[0].planning == [7]  # Planning behaviour is unchanged
    assert not any(c["batch"] is True for c in instances[0].search_calls)
    assert {c["episode"] for c in instances[0].search_calls} == {4}


def test_releasing_series_up_to_date(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    _write_episodes(tmp_path / "Show", [1, 2, 3, 4])

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert instances[0].downloads == []


def test_episodes_override_without_airing_data(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    monkeypatch.setitem(RELEASING, "nextAiringEpisode", None)

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes", "--episodes", "4"])

    assert code == cli.EXIT_OK
    assert instances[0].downloads[0][3] == [1, 2, 3, 4]
    assert not any(c["batch"] is True for c in instances[0].search_calls)
    assert {c["episode"] for c in instances[0].search_calls} == {1, 2, 3, 4}


def test_releasing_series_without_count_errors(monkeypatch, tmp_path) -> None:
    _fake_client(monkeypatch)
    monkeypatch.setitem(RELEASING, "nextAiringEpisode", None)
    assert cli.main(["Show", "--lib", str(tmp_path), "--yes"]) == cli.EXIT_ERROR


def test_finished_series_still_stops_when_present(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    monkeypatch.setattr(FakeSeanime, "media", FINISHED)
    _write_episodes(tmp_path / "Show", [1])

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert instances[0].downloads == []


def test_creates_destination_before_download(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    destination = tmp_path / "Show"
    assert destination.is_dir()
    assert instances[0].downloads[0][1] == str(destination)


def test_releasing_series_searches_base_title(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    media = dict(RELEASING, title={"romaji": "Show Part 2", "english": "Show 2nd Cour"})
    monkeypatch.setattr(FakeSeanime, "media", media)

    cli.main(["Show Part 2", "--lib", str(tmp_path), "--yes", "--dry-run"])

    assert "Show" in {c["query"] for c in instances[0].search_calls}


def test_finished_series_searches_batch(monkeypatch, tmp_path) -> None:
    instances = _fake_client(monkeypatch)
    monkeypatch.setattr(FakeSeanime, "media", FINISHED)

    code = cli.main(["Show", "--lib", str(tmp_path), "--yes", "--dry-run"])

    assert code == cli.EXIT_OK
    assert any(c["batch"] is True for c in instances[0].search_calls)


# ----------------------------------------------------------------- batch / --all
SERIES_A = {
    "id": 11,
    "status": "RELEASING",
    "format": "TV",
    "title": {"romaji": "Show"},
    "synonyms": [],
    "nextAiringEpisode": {"episode": 5},  # four episodes aired
}
SERIES_B = {
    "id": 12,
    "status": "RELEASING",
    "format": "TV",
    "title": {"romaji": "Show"},
    "synonyms": [],
    "nextAiringEpisode": {"episode": 6},  # five episodes aired
}

ENTRY_A = {
    "mediaId": 11,
    "media": SERIES_A,
    "listData": {"status": "CURRENT", "progress": 2},
    "libraryData": {"mainFileCount": 6, "unwatchedCount": 4},
}
ENTRY_B = {
    "mediaId": 12,
    "media": SERIES_B,
    "listData": {"status": "CURRENT", "progress": "3"},
    "libraryData": {"mainFileCount": 5, "unwatchedCount": 2},
}
BATCH_COLLECTION = {
    "lists": [
        {"status": "CURRENT", "entries": [ENTRY_A, ENTRY_B, dict(ENTRY_A)]},
        {"status": "PLANNING", "entries": [
            {"mediaId": 13, "media": SERIES_A, "listData": {"progress": 0}},
        ]},
        {"status": "COMPLETED", "entries": [
            {"mediaId": 14, "media": dict(SERIES_A, status="FINISHED"),
             "listData": {"progress": 0}},
        ]},
    ],
}


def _to_anilist(collection: dict) -> dict:
    """Turn a library-style collection into the AniList collection shape."""
    lists = []
    for lst in collection.get("lists") or []:
        entries = []
        for e in lst.get("entries") or []:
            if not isinstance(e, dict):
                continue
            ld = e.get("listData") or {}
            entries.append({
                "id": cli.entry_media_id(e),
                "media": e.get("media") or {},
                "status": ld.get("status") or e.get("status") or lst.get("status"),
                "progress": ld["progress"] if "progress" in ld else e.get("progress", 0),
            })
        lists.append({"name": lst.get("name"), "status": lst.get("status"),
                      "entries": entries})
    return {"lists": lists}


class BatchFakeSeanime(FakeSeanime):
    """FakeSeanime with an AniList list, a library collection, and download failures."""

    collection_data: dict = {"lists": []}
    anilist_data: dict = {"lists": []}
    fail_download = False
    fail_anilist = False

    def collection(self):
        self.collection_calls = getattr(self, "collection_calls", 0) + 1
        return self.collection_data

    def anilist_collection(self):
        self.anilist_calls = getattr(self, "anilist_calls", 0) + 1
        if self.fail_anilist:
            raise cli.SeanimeError("AniList down")
        return self.anilist_data

    def download(self, torrents, destination, media, episodes):
        if self.fail_download and media["id"] == 11:
            raise cli.SeanimeError("download failed")
        super().download(torrents, destination, media, episodes)


def _batch_fake_client(monkeypatch, *, collection=None, anilist=None,
                       confirm_answer=True, fail_download=False, fail_anilist=False):
    instances: list = []
    confirms: list = []

    def factory(*args, **kwargs):
        client = BatchFakeSeanime(*args, **kwargs)
        client.collection_data = BATCH_COLLECTION if collection is None else collection
        source = anilist if anilist is not None else client.collection_data
        client.anilist_data = _to_anilist(source)
        client.fail_download = fail_download
        client.fail_anilist = fail_anilist
        instances.append(client)
        return client

    setattr(factory, "find_entry", cli.Seanime.find_entry)
    monkeypatch.setattr(cli, "Seanime", factory)
    monkeypatch.setattr(cli, "confirm", lambda question: confirms.append(question) or confirm_answer)
    return instances, confirms


def test_select_watching_releasing_filters_and_dedups() -> None:
    selected = cli.select_watching_releasing(BATCH_COLLECTION)
    assert [entry["mediaId"] for entry in selected] == [11, 12]
    assert cli.select_watching_releasing({}) == []
    assert cli.select_watching_releasing({"lists": None}) == []


def test_batch_targets_uses_progress() -> None:
    assert cli.batch_targets(ENTRY_A) == (4, {3, 4})
    assert cli.batch_targets(ENTRY_B) == (5, {4, 5})  # string progress "3"


@pytest.mark.parametrize("progress", [None, 0, "0", "bad", -2])
def test_batch_targets_progress_falls_back_to_one(progress) -> None:
    entry = {"media": SERIES_A, "listData": {"progress": progress}}
    assert cli.batch_targets(entry) == (4, {1, 2, 3, 4})


@pytest.mark.parametrize("progress", [4, 9])
def test_batch_targets_watched_through_aired_is_empty(progress) -> None:
    assert cli.batch_targets({"media": SERIES_A, "listData": {"progress": progress}}) is None


def test_batch_targets_without_airing_data() -> None:
    assert cli.batch_targets({"media": {"status": "RELEASING", "title": {}}}) is None


def test_batch_targets_episodes_cap() -> None:
    assert cli.batch_targets(ENTRY_A, episodes_override=3) == (4, {3})


def test_build_parser_all_flag() -> None:
    args = cli.build_parser().parse_args(["--all", "--yes"])
    assert args.all and args.yes
    assert not cli.build_parser().parse_args([]).all


def test_batch_all_queues_only_unwatched_episodes(monkeypatch, tmp_path) -> None:
    instances, confirms = _batch_fake_client(monkeypatch)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert confirms == []  # --yes skips the prompt
    client = instances[0]
    assert client.collection_calls == 1
    assert [download[3] for download in client.downloads] == [[3, 4], [4, 5]]
    assert client.planning == []  # already on the Watching list
    assert not any(call["batch"] is True for call in client.search_calls)
    assert {call["episode"] for call in client.search_calls} == {3, 4, 5}


def test_batch_all_confirms_once(monkeypatch, tmp_path) -> None:
    instances, confirms = _batch_fake_client(monkeypatch)

    code = cli.main(["--all", "--lib", str(tmp_path)])

    assert code == cli.EXIT_OK
    assert len(confirms) == 1
    assert "2 series" in confirms[0]
    assert len(instances[0].downloads) == 2


def test_batch_all_dry_run(monkeypatch, tmp_path) -> None:
    instances, confirms = _batch_fake_client(monkeypatch)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes", "--dry-run"])

    assert code == cli.EXIT_OK
    assert instances[0].downloads == []
    assert confirms == []
    assert not (tmp_path / "Show").exists()


def test_batch_all_all_up_to_date(monkeypatch, tmp_path) -> None:
    collection = {"lists": [{"status": "CURRENT", "entries": [
        {"mediaId": 11, "media": SERIES_A, "listData": {"progress": 4}},
        {"mediaId": 12, "media": SERIES_B, "listData": {"progress": 5}},
    ]}]}
    instances, _ = _batch_fake_client(monkeypatch, collection=collection)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_SKIP
    assert instances[0].downloads == []
    assert instances[0].search_calls == []


def test_batch_all_empty_selection_skips(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch, collection={"lists": []})

    assert cli.main(["--all", "--lib", str(tmp_path), "--yes"]) == cli.EXIT_SKIP
    assert instances[0].downloads == []


def test_batch_all_mixed_skip_and_ok(monkeypatch, tmp_path) -> None:
    collection = {"lists": [{"status": "CURRENT", "entries": [
        {"mediaId": 11, "media": SERIES_A, "listData": {"progress": 4}},
        ENTRY_B,
    ]}]}
    instances, _ = _batch_fake_client(monkeypatch, collection=collection)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert [download[3] for download in instances[0].downloads] == [[4, 5]]


def test_batch_all_download_error(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch, fail_download=True)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_ERROR
    assert len(instances[0].downloads) == 1  # the other series still queued


def test_batch_all_confirm_declined(monkeypatch, tmp_path) -> None:
    instances, confirms = _batch_fake_client(monkeypatch, confirm_answer=False)

    code = cli.main(["--all", "--lib", str(tmp_path)])

    assert code == cli.EXIT_SKIP
    assert len(confirms) == 1
    assert instances[0].downloads == []


def test_batch_all_multiple_providers_uses_first_client(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes", "--provider", "a,b"])

    assert code == cli.EXIT_OK
    assert len(instances) == 2
    assert instances[0].collection_calls == 1
    assert getattr(instances[1], "collection_calls", 0) == 0
    assert len(instances[0].downloads) == 2
    assert instances[1].downloads == []


def test_batch_all_episodes_cap(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes", "--episodes", "3"])

    # Series A (progress 2) still wants episode 3; series B (progress 3) is
    # capped at 3 and has nothing left to fetch.
    assert code == cli.EXIT_OK
    assert [download[3] for download in instances[0].downloads] == [[3]]


def test_library_episodes_filters_shared_path_by_title(tmp_path) -> None:
    shared = tmp_path / "Library"
    _write_episodes(shared, [1, 2])
    (shared / "[B] Totally Different - 09 [HEVC].mkv").write_bytes(b"x")
    entry = {"libraryData": {"sharedPath": str(shared)}}
    assert cli.library_episodes(tmp_path / "empty", entry, ["Show"]) == {1, 2}


def test_batch_all_skips_unwatched_episodes_already_on_disk(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch)
    _write_episodes(tmp_path / "Show", [3, 4, 5, 6, 7])

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_SKIP
    assert instances[0].downloads == []
    assert instances[0].search_calls == []


def test_batch_all_queues_only_missing_unwatched_episodes(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch)
    _write_episodes(tmp_path / "Show", [3])

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert [download[3] for download in instances[0].downloads] == [[4], [4, 5]]


def test_batch_all_uses_shared_path_to_skip_disk_episodes(monkeypatch, tmp_path) -> None:
    shared = tmp_path / "SharedLib"
    _write_episodes(shared, [3, 4, 5, 6, 7])
    collection = {"lists": [{"status": "CURRENT", "entries": [
        dict(ENTRY_A, libraryData={"sharedPath": str(shared)}),
        dict(ENTRY_B, libraryData={"sharedPath": str(shared)}),
    ]}]}
    instances, _ = _batch_fake_client(monkeypatch, collection=collection)

    code = cli.main(["--all", "--lib", str(tmp_path / "other"), "--yes"])

    assert code == cli.EXIT_SKIP
    assert instances[0].downloads == []


def test_entry_progress_reads_both_collection_shapes() -> None:
    assert cli.entry_progress({"listData": {"progress": 3}}) == 3
    assert cli.entry_progress({"progress": "2"}) == 2
    assert cli.entry_progress({"progress": 4, "listData": {}}) == 4
    assert cli.entry_progress({}) == 0


def test_batch_all_uses_anilist_watching_not_library(monkeypatch, tmp_path) -> None:
    library = {"lists": [{"status": "CURRENT", "entries": [ENTRY_A]}]}
    instances, _ = _batch_fake_client(monkeypatch, collection=library, anilist=BATCH_COLLECTION)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert instances[0].anilist_calls == 1
    assert instances[0].collection_calls == 1
    assert [download[3] for download in instances[0].downloads] == [[3, 4], [4, 5]]


def test_batch_all_fetches_series_absent_from_library(monkeypatch, tmp_path) -> None:
    # Watching on AniList, but Seanime has no files or library entry for it.
    series = {
        "id": 20, "status": "RELEASING", "format": "TV",
        "title": {"romaji": "Show"}, "synonyms": [],
        "nextAiringEpisode": {"episode": 9},  # eight aired, seven watched
    }
    anilist = {"lists": [{"status": "CURRENT", "entries": [
        {"id": 99, "media": series, "status": "CURRENT", "progress": 7},
    ]}]}
    instances, _ = _batch_fake_client(monkeypatch, collection={"lists": []}, anilist=anilist)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_OK
    assert len(instances[0].downloads) == 1
    assert instances[0].downloads[0][2]["id"] == 20
    assert instances[0].downloads[0][3] == [8]


def test_batch_all_anilist_failure_is_fatal(monkeypatch, tmp_path) -> None:
    instances, _ = _batch_fake_client(monkeypatch, fail_anilist=True)

    code = cli.main(["--all", "--lib", str(tmp_path), "--yes"])

    assert code == cli.EXIT_ERROR
    assert instances[0].downloads == []
