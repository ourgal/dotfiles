"""Client for the local Seanime API (AniList, library, torrents)."""

from __future__ import annotations

from typing import Any, Iterable

from .net import HttpError, request_json

DEFAULT_BASE = "http://localhost:43211"
DEFAULT_PROVIDER = "animetosho-new"


class SeanimeError(RuntimeError):
    pass


class Seanime:
    def __init__(self, base: str = DEFAULT_BASE, provider: str = DEFAULT_PROVIDER) -> None:
        self.base = base.rstrip("/") + "/api/v1"
        self.provider = provider

    # ------------------------------------------------------------------ helpers
    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _post(self, path: str, payload: Any, *, retries: int = 1, timeout: float = 90.0) -> Any:
        return request_json("POST", self._url(path), payload, retries=retries, timeout=timeout)

    # ------------------------------------------------------------------- AniList
    def search_anime(self, query: str, per_page: int = 10) -> list[dict[str, Any]]:
        """Search AniList through Seanime (uses the server's token + cache)."""
        body = {"search": query, "perPage": per_page, "page": 1}
        try:
            data = self._post("/anilist/list-anime", body)
        except HttpError as exc:
            raise SeanimeError(f"AniList search failed: {exc}") from None
        media = ((data or {}).get("data") or {}).get("Page", {}).get("media") or []
        return [m for m in media if m.get("id")]

    def collection(self) -> dict[str, Any]:
        """The synced AniList collection with library stats (what is downloaded)."""
        data = request_json("GET", self._url("/library/collection"), timeout=120)
        return (data or {}).get("data") or {}

    def anilist_collection(self) -> dict[str, Any]:
        """The full AniList media-list collection (every Watching entry, not just
        the ones Seanime has files for)."""
        try:
            data = request_json("GET", self._url("/anilist/collection"), timeout=120)
        except HttpError as exc:
            raise SeanimeError(f"could not read the AniList collection: {exc}") from None
        return (((data or {}).get("data") or {}).get("MediaListCollection")) or {}

    @staticmethod
    def find_entry(collection: dict[str, Any], media_id: int) -> dict[str, Any] | None:
        for lst in collection.get("lists") or []:
            for entry in lst.get("entries") or []:
                if entry.get("mediaId") == media_id:
                    return entry
        return None

    def set_planning(self, media_id: int) -> str:
        """Add the media to the user's Planning list (never downgrades an entry)."""
        body = {"mediaId": media_id, "status": "PLANNING", "score": 0, "progress": 0}
        try:
            self._post("/anilist/list-entry", body, retries=0, timeout=60)
        except HttpError as exc:
            raise SeanimeError(f"could not set Planning for {media_id}: {exc}") from None
        return "PLANNING"

    # ------------------------------------------------------------------- torrents
    def search_torrents(
        self,
        media: dict[str, Any],
        query: str,
        *,
        batch: bool | None = None,
        episode: int | None = None,
        resolution: str = "1080p",
        retries: int = 1,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {
            "type": "smart",
            "provider": self.provider,
            "media": media,
            "query": query,
            "resolution": resolution,
        }
        if batch is not None:
            body["batch"] = batch
        if episode is not None:
            body["episodeNumber"] = episode
        try:
            data = self._post("/torrent/search", body, retries=retries, timeout=120)
        except HttpError as exc:
            raise SeanimeError(f"torrent search failed ({query!r}): {exc}") from None
        return (data or {}).get("data", {}).get("torrents") or []

    def torrent_files(self, torrent: dict[str, Any], *, retries: int = 2) -> list[str]:
        body = {"torrent": torrent, "provider": torrent.get("provider") or self.provider}
        try:
            data = self._post("/torrent-client/get-files", body, retries=retries, timeout=120)
        except HttpError as exc:
            raise SeanimeError(f"could not list torrent files for {torrent.get('name')!r}: {exc}") from None
        files = (data or {}).get("data") or []
        return [f for f in files if isinstance(f, str)]

    def download(
        self,
        torrents: Iterable[dict[str, Any]],
        destination: str,
        media: dict[str, Any],
        episodes: list[int],
    ) -> Any:
        torrents = list(torrents)
        # Smart select resolves episode numbers to file indices inside one torrent;
        # the server rejects it when the episode list is empty.
        smart = {"enabled": len(torrents) == 1 and bool(episodes), "missingEpisodeNumbers": episodes}
        body = {
            "torrents": torrents,
            "destination": destination,
            "smartSelect": smart,
            "deselect": {"enabled": False},
            "media": media,
        }
        try:
            return self._post("/torrent-client/download", body, retries=0, timeout=120)
        except HttpError as exc:
            raise SeanimeError(f"download request failed: {exc}") from None
