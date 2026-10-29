"""Tests for the HTTP helper and the Seanime client (fully offline)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from anime_fetch import seanime
from anime_fetch.net import HttpError, request_json


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(status: int, body: bytes = b"boom") -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x", status, "err", {}, io.BytesIO(body))


def patch_urlopen(monkeypatch, respond):
    """Replace urlopen with a handler receiving (request, attempt) -> response/exception."""
    calls: list[urllib.request.Request] = []

    def handler(req, timeout=None):
        calls.append(req)
        result = respond(req, len(calls))
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("anime_fetch.net.urllib.request.urlopen", handler)
    return calls


# ------------------------------------------------------------------- net layer
def test_request_json_get(monkeypatch) -> None:
    calls = patch_urlopen(monkeypatch, lambda req, n: FakeResponse(b'{"ok": true}'))
    assert request_json("GET", "http://x/api") == {"ok": True}
    req = calls[0]
    assert req.get_method() == "GET"
    assert req.full_url == "http://x/api"


def test_request_json_post_encodes_payload(monkeypatch) -> None:
    calls = patch_urlopen(monkeypatch, lambda req, n: FakeResponse(b"{}"))

    request_json("POST", "http://x/api", {"a": 1})

    req = calls[0]
    assert req.get_method() == "POST"
    assert json.loads(req.data.decode("utf-8")) == {"a": 1}
    assert req.headers.get("Content-type") == "application/json"


def test_request_json_empty_body(monkeypatch) -> None:
    patch_urlopen(monkeypatch, lambda req, n: FakeResponse(b""))
    assert request_json("GET", "http://x") == {}


def test_request_json_retries_then_succeeds(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("anime_fetch.net.time.sleep", sleeps.append)
    calls = patch_urlopen(
        monkeypatch,
        lambda req, n: http_error(503) if n == 1 else FakeResponse(b"{}"),
    )
    assert request_json("GET", "http://x", retries=2, backoff=2.0) == {}
    assert len(calls) == 2
    assert sleeps == [2.0]


def test_request_json_retries_exhausted(monkeypatch) -> None:
    monkeypatch.setattr("anime_fetch.net.time.sleep", lambda _s: None)
    calls = patch_urlopen(monkeypatch, lambda req, n: http_error(429))
    with pytest.raises(HttpError) as excinfo:
        request_json("GET", "http://x", retries=2)
    assert excinfo.value.status == 429
    assert len(calls) == 3


def test_request_json_does_not_retry_client_error(monkeypatch) -> None:
    calls = patch_urlopen(monkeypatch, lambda req, n: http_error(404))
    with pytest.raises(HttpError):
        request_json("GET", "http://x", retries=5)
    assert len(calls) == 1


def test_request_json_url_error(monkeypatch) -> None:
    patch_urlopen(
        monkeypatch,
        lambda req, n: urllib.error.URLError(OSError("conn refused")),
    )
    with pytest.raises(HttpError) as excinfo:
        request_json("GET", "http://x", retries=0)
    assert excinfo.value.status == 0
    assert "conn refused" in str(excinfo.value)


def test_request_json_timeout_error(monkeypatch) -> None:
    patch_urlopen(monkeypatch, lambda req, n: TimeoutError())
    with pytest.raises(HttpError) as excinfo:
        request_json("GET", "http://x", retries=0)
    assert "timed out" in str(excinfo.value)


def test_http_error_as_json() -> None:
    error = HttpError(400, '{"error": "bad"} extra', "http://x")
    assert error.status == 400
    assert error.as_json() is None  # trailing junk: not valid JSON
    assert "HTTP 400 from http://x" in str(error)


# -------------------------------------------------------------- seanime client
class StubSeanime(seanime.Seanime):
    """Records payloads and answers canned responses by endpoint."""

    def __init__(self, responses: dict) -> None:
        super().__init__(base="http://seanime.local:43211/")
        self.calls: list = []
        self.responses = responses

    def _post(self, path, payload, *, retries=1, timeout=90.0):
        self.calls.append((path, payload))
        response = self.responses.get(path)
        if isinstance(response, Exception):
            raise response
        return response


def test_seanime_base_url_is_normalized() -> None:
    assert StubSeanime({}).base == "http://seanime.local:43211/api/v1"


def test_search_anime() -> None:
    client = StubSeanime(
        {"/anilist/list-anime": {"data": {"Page": {"media": [
            {"id": 154587, "title": {"romaji": "Mushoku Tensei III"}},
            {"id": None, "title": {"romaji": "dropped"}},
        ]}}}}
    )
    media = client.search_anime("mushoku", per_page=5)
    assert [m["id"] for m in media] == [154587]
    path, payload = client.calls[0]
    assert path == "/anilist/list-anime"
    assert payload == {"search": "mushoku", "perPage": 5, "page": 1}


def test_search_anime_wraps_http_error() -> None:
    client = StubSeanime({"/anilist/list-anime": HttpError(500, "boom", "http://x")})
    with pytest.raises(seanime.SeanimeError, match="AniList search failed"):
        client.search_anime("anything")


def test_collection_uses_get(monkeypatch) -> None:
    seen: dict = {}

    def fake(method, url, payload=None, **kwargs):
        seen.update(method=method, url=url)
        return {"data": {"lists": []}}

    monkeypatch.setattr(seanime, "request_json", fake)
    assert seanime.Seanime().collection() == {"lists": []}
    assert seen["method"] == "GET"
    assert seen["url"] == "http://localhost:43211/api/v1/library/collection"


def test_find_entry() -> None:
    collection = {"lists": [
        {"entries": [{"mediaId": 1, "status": "CURRENT"}]},
        {"entries": [{"mediaId": 2, "status": "PLANNING"}]},
    ]}
    assert seanime.Seanime.find_entry(collection, 2)["status"] == "PLANNING"
    assert seanime.Seanime.find_entry(collection, 99) is None
    assert seanime.Seanime.find_entry({}, 1) is None


def test_set_planning() -> None:
    client = StubSeanime({"/anilist/list-entry": {"data": {}}})
    assert client.set_planning(154587) == "PLANNING"
    path, payload = client.calls[0]
    assert path == "/anilist/list-entry"
    assert payload["mediaId"] == 154587
    assert payload["status"] == "PLANNING"


def test_set_planning_wraps_http_error() -> None:
    client = StubSeanime({"/anilist/list-entry": HttpError(400, "bad", "http://x")})
    with pytest.raises(seanime.SeanimeError, match="could not set Planning"):
        client.set_planning(1)


def test_search_torrents_body() -> None:
    client = StubSeanime({"/torrent/search": {"data": {"torrents": [{"name": "x"}]}}})
    media = {"id": 1}
    torrents = client.search_torrents(media, "Show", batch=True)
    assert torrents == [{"name": "x"}]
    _path, payload = client.calls[0]
    assert payload["type"] == "smart"
    assert payload["provider"] == seanime.DEFAULT_PROVIDER
    assert payload["media"] is media
    assert payload["resolution"] == "1080p"
    assert payload["batch"] is True
    assert "episodeNumber" not in payload


def test_search_torrents_episode_and_provider() -> None:
    client = StubSeanime({"/torrent/search": {"data": {"torrents": []}}})
    client.provider = "nyaa"
    client.search_torrents({"id": 1}, "Show", batch=False, episode=3)
    _path, payload = client.calls[0]
    assert payload["provider"] == "nyaa"
    assert payload["batch"] is False
    assert payload["episodeNumber"] == 3


def test_search_torrents_wraps_http_error() -> None:
    client = StubSeanime({"/torrent/search": HttpError(503, "down", "http://x")})
    with pytest.raises(seanime.SeanimeError, match="torrent search failed"):
        client.search_torrents({"id": 1}, "Show", batch=True)


def test_torrent_files() -> None:
    client = StubSeanime({"/torrent-client/get-files": {"data": ["a.mkv", 5, "b.mkv"]}})
    torrent = {"name": "t", "provider": "nyaa"}
    assert client.torrent_files(torrent) == ["a.mkv", "b.mkv"]
    _path, payload = client.calls[0]
    assert payload["torrent"] == torrent
    assert payload["provider"] == "nyaa"


def test_download_smart_select() -> None:
    client = StubSeanime({"/torrent-client/download": {"ok": True}})
    torrents = [{"name": "batch"}]
    media = {"id": 1}
    client.download(torrents, "C:/lib/Show", media, [1, 2, 3])
    _path, payload = client.calls[0]
    assert payload["torrents"] == torrents
    assert payload["destination"] == "C:/lib/Show"
    assert payload["smartSelect"] == {"enabled": True, "missingEpisodeNumbers": [1, 2, 3]}
    assert payload["deselect"] == {"enabled": False}
    assert payload["media"] is media


def test_download_smart_select_disabled_for_multiple() -> None:
    client = StubSeanime({"/torrent-client/download": {"ok": True}})
    client.download([{"name": "a"}, {"name": "b"}], "dest", {"id": 1}, [1])
    _path, payload = client.calls[0]
    assert payload["smartSelect"]["enabled"] is False
