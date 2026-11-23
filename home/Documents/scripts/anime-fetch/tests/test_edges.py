"""Edge cases for error handling and output branches (no network access)."""

from __future__ import annotations

import io
import urllib.error
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

from anime_fetch import net, pick, plan, report, resolve, seanime, single
from anime_fetch.config import EXIT_ERROR, EXIT_OK, EXIT_SKIP


class FakeResponse:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False

    def read(self) -> bytes:
        return self.raw


def http_error(status: int, body: str = '{"detail":"busy"}') -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://example.test/api", status, "err", Message(), io.BytesIO(body.encode()))


def media(mid: int, title: str, **kwargs):
    item = {"id": mid, "title": {"romaji": title}, "format": "TV", "episodes": 12}
    item.update(kwargs)
    return item


def args(**kwargs):
    base = dict(query=[], pick=None, episodes=None, lib="/lib", verbose=False,
                ignore_library=False, no_planning=False, dry_run=False,
                max_batch_probes=20, yes=False)
    base.update(kwargs)
    return SimpleNamespace(**base)


class FakeSeanime:
    @staticmethod
    def find_entry(_collection, _mid):
        return None


# ---------------------------------------------------------------- net.py


def test_http_error_as_json():
    assert net.HttpError(500, '{"ok": true}', "u").as_json() == {"ok": True}
    assert net.HttpError(500, "not json", "u").as_json() is None


def test_request_json_get_empty_body(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["timeout"] = timeout
        return FakeResponse(b"")

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)
    assert net.request_json("GET", "http://example.test/empty") == {}
    assert seen == {"method": "GET", "timeout": 90.0}


def test_request_json_post_sets_json_header(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["data"] = req.data
        seen["content_type"] = req.get_header("Content-type")
        return FakeResponse(b'{"ok": true}')

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)
    assert net.request_json("POST", "http://example.test/go", {"a": 1}) == {"ok": True}
    assert seen["method"] == "POST"
    assert seen["data"] == b'{"a": 1}'
    assert seen["content_type"] == "application/json"


def test_request_json_retries_transient_http_status(monkeypatch):
    sleeps = []
    responses = [http_error(503), FakeResponse(b'{"ok": 1}')]

    def fake_urlopen(*_a, **_k):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert net.request_json("GET", "http://example.test/x", retries=2, backoff=2.0) == {"ok": 1}
    assert sleeps == [2.0]


def test_request_json_does_not_retry_permanent_http_status(monkeypatch):
    calls = []
    monkeypatch.setattr(net.urllib.request, "urlopen", lambda *_a, **_k: calls.append(1) or (_ for _ in ()).throw(http_error(404)))
    monkeypatch.setattr(net.time, "sleep", lambda _s: pytest.fail("should not sleep"))
    with pytest.raises(net.HttpError) as exc:
        net.request_json("GET", "http://example.test/missing", retries=3)
    assert exc.value.status == 404
    assert len(calls) == 1


def test_request_json_retries_urlerror_and_timeout(monkeypatch):
    sleeps = []
    responses = [
        urllib.error.URLError("refused"),
        TimeoutError("slow"),
        FakeResponse(b'{"done": true}'),
    ]

    def fake_urlopen(*_a, **_k):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(net.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda seconds: sleeps.append(seconds))
    assert net.request_json("GET", "http://example.test/x", retries=2, backoff=0.5) == {"done": True}
    assert sleeps == [0.5, 1.0]


def test_request_json_exhausted_timeout_raises(monkeypatch):
    monkeypatch.setattr(net.urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("slow")))
    monkeypatch.setattr(net.time, "sleep", lambda _s: None)
    with pytest.raises(net.HttpError) as exc:
        net.request_json("GET", "http://example.test/x", retries=1)
    assert exc.value.status == 0
    assert "timed out" in str(exc.value)


# ------------------------------------------------------------- resolve.py


def test_resolve_filters_music_and_adult_and_picks():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [
        media(1, "Op", format="MUSIC"),
        media(2, "Adult", isAdult=True),
        media(3, "Good Show"),
    ])
    assert resolve.resolve_media(client, "Good Show", None)["id"] == 3
    assert resolve.resolve_media(client, "Good Show", 1)["id"] == 3


def test_resolve_pick_out_of_range():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [media(1, "A"), media(2, "B")])
    with pytest.raises(seanime.SeanimeError, match="between 1 and 2"):
        resolve.resolve_media(client, "A", 3)


def test_resolve_no_results_after_filtering():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [media(1, "Op", format="MUSIC")])
    with pytest.raises(seanime.SeanimeError, match="no result"):
        resolve.resolve_media(client, "Op", None)


def test_resolve_ambiguous_low_score_lists_picks():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [media(1, "Unrelated")])
    with pytest.raises(resolve.Ambiguous, match="--pick N"):
        resolve.resolve_media(client, "Something", None)


def test_resolve_ambiguous_tie():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [
        media(1, "Same Title"), media(2, "Same Title")
    ])
    with pytest.raises(resolve.Ambiguous, match="equally good"):
        resolve.resolve_media(client, "Same Title", None)


def test_resolve_loose_word_overlap_for_long_query():
    client = SimpleNamespace(search_anime=lambda *_a, **_k: [media(7, "three two one")])
    assert resolve.resolve_media(client, "one two three", None)["id"] == 7


# ---------------------------------------------------------------- plan.py


def test_ensure_planning_branches(capsys):
    client = SimpleNamespace(set_planning=lambda _mid: None)
    item = media(1, "Show")

    plan.ensure_planning(client, item, {"listData": {"status": "PLANNING"}}, dry_run=False)
    assert "already on Planning" in capsys.readouterr().out
    plan.ensure_planning(client, item, {"listData": {"status": "COMPLETED"}}, dry_run=False)
    assert "left as COMPLETED" in capsys.readouterr().out
    plan.ensure_planning(client, item, None, dry_run=True)
    assert "would be added" in capsys.readouterr().out

    plan.ensure_planning(client, item, None, dry_run=False)
    assert "added to Planning" in capsys.readouterr().out


def _plan_result(tmp_path: Path):
    torrent = {"name": "[Grp] Show - 01 [1080p]", "size": 123, "seeders": 9}
    chosen = pick.Plan([pick.Candidate(torrent, episodes={1})], "per-episode")
    return plan.PlanResult(media(1, "Show"), None, chosen, tmp_path, {1}, [1], EXIT_OK)


def test_commit_plan_destination_failure(tmp_path, monkeypatch, capsys):
    result = _plan_result(tmp_path)
    monkeypatch.setattr(Path, "mkdir", lambda *_a, **_k: (_ for _ in ()).throw(OSError("denied")))
    assert plan.commit_plan(SimpleNamespace(), result, args(), do_planning=False) == EXIT_ERROR
    assert "cannot create destination folder" in capsys.readouterr().err


def test_commit_plan_download_failure(tmp_path, capsys):
    result = _plan_result(tmp_path)

    def fail(*_a, **_k):
        raise seanime.SeanimeError("seanime down")

    client = SimpleNamespace(download=fail)
    assert plan.commit_plan(client, result, args(), do_planning=False) == EXIT_ERROR
    assert "seanime down" in capsys.readouterr().err


def test_commit_plan_planning_failure_is_error_after_download(tmp_path, capsys):
    result = _plan_result(tmp_path)
    events = []

    def fail_planning(_mid):
        raise net.HttpError(500, '{"error": "anilist"}', "http://example.test")

    client = SimpleNamespace(download=lambda *_a, **_k: events.append("download"),
                             set_planning=fail_planning)
    assert plan.commit_plan(client, result, args()) == EXIT_ERROR
    assert events == ["download"]
    assert "AniList update failed" in capsys.readouterr().err


def test_build_plan_search_error(tmp_path, monkeypatch):
    def fail(*_a, **_k):
        raise seanime.SeanimeError("search down")

    monkeypatch.setattr(plan, "gather", fail)
    result = plan.build_plan([SimpleNamespace()], media(1, "Show", status="RELEASING"), None,
                             args(lib=str(tmp_path)), total=12, wanted={1}, echo=False)
    assert result.code == EXIT_ERROR
    assert "search down" in result.message
    assert result.plan is None


# --------------------------------------------------------------- single.py


def test_single_clipboard_empty(monkeypatch, capsys):
    monkeypatch.setattr(single, "clipboard_text", lambda: None)
    assert single.run(args(), [SimpleNamespace()], seanime_cls=FakeSeanime,
                      confirm_fn=lambda _q: True) == EXIT_ERROR
    assert "clipboard is empty" in capsys.readouterr().err


def test_single_clipboard_slug_without_title(monkeypatch, capsys):
    monkeypatch.setattr(single, "clipboard_text",
                        lambda: "https://anilist.co/anime/12345")
    assert single.run(args(), [SimpleNamespace()], seanime_cls=FakeSeanime,
                      confirm_fn=lambda _q: True) == EXIT_ERROR
    assert "cannot derive a title" in capsys.readouterr().err


def test_single_unknown_episode_count(monkeypatch, capsys):
    monkeypatch.setattr(single, "resolve_media",
                        lambda *_a, **_k: media(1, "Show", episodes=None))
    assert single.run(args(query=["Show"]), [SimpleNamespace()], seanime_cls=FakeSeanime,
                      confirm_fn=lambda _q: True) == EXIT_ERROR
    assert "episode count is unknown" in capsys.readouterr().err


def test_single_ongoing_without_aired_count(monkeypatch, capsys):
    monkeypatch.setattr(single, "resolve_media",
                        lambda *_a, **_k: media(1, "Show", status="RELEASING"))
    assert single.run(args(query=["Show"]), [SimpleNamespace()], seanime_cls=FakeSeanime,
                      confirm_fn=lambda _q: True) == EXIT_ERROR
    assert "does not report an aired episode count" in capsys.readouterr().err


@pytest.mark.parametrize("dry_run,confirmed,expected,word", [
    (True, True, EXIT_OK, "Dry run"),
    (False, False, EXIT_SKIP, "Cancelled"),
])
def test_single_plan_preview_and_cancel(tmp_path, monkeypatch, capsys,
                                        dry_run, confirmed, expected, word):
    monkeypatch.setattr(single, "resolve_media", lambda *_a, **_k: media(1, "Show"))
    monkeypatch.setattr(single, "build_plan",
                        lambda *_a, **_k: _plan_result(tmp_path))
    result = single.run(args(query=["Show"], episodes=1, lib=str(tmp_path), dry_run=dry_run),
                        [SimpleNamespace(collection=lambda: [])], seanime_cls=FakeSeanime,
                        confirm_fn=lambda _q: confirmed)
    assert result == expected
    assert word in capsys.readouterr().out


# --------------------------------------------------------------- report.py


@pytest.mark.parametrize("size,expected", [
    (0, "0 B"), (1023, "1023 B"), (1024, "1.00 KiB"), (1536, "1.50 KiB"),
    (1024 ** 2, "1.00 MiB"), (1024 ** 3, "1.00 GiB"), (1024 ** 4, "1.00 TiB"),
])
def test_human_size(size, expected):
    assert report.human_size(size) == expected


def test_print_plan_compacts_long_episode_ranges(capsys):
    torrent = {"name": "[Grp] Show Batch", "size": 2048, "seeders": 3}
    chosen = pick.Plan([pick.Candidate(torrent, episodes=set(range(1, 14)))], "batch")
    report.print_plan(chosen, Path("/lib/Show"), wanted=set(range(1, 14)))
    out = capsys.readouterr().out
    assert "episodes 1-13" in out
    assert "13/13 episodes" in out
    assert "2.00 KiB" in out
