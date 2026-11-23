"""Tiny JSON-over-HTTP helper (stdlib only, retries transient 5xx/429)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class HttpError(RuntimeError):
    def __init__(self, status: int, body: str, url: str) -> None:
        self.status = status
        self.body = body
        self.url = url
        snippet = " ".join(body.split())[:300]
        super().__init__(f"HTTP {status} from {url}: {snippet}")

    def as_json(self) -> Any:
        try:
            return json.loads(self.body)
        except ValueError:
            return None


def request_json(
    method: str,
    url: str,
    payload: Any | None = None,
    *,
    timeout: float = 90.0,
    retries: int = 0,
    backoff: float = 1.5,
    retry_status: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> Any:
    """Perform a JSON request, retrying transient failures."""
    data = None
    headers = {"Accept": "application/json", "User-Agent": "anime-fetch/0.1"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last: HttpError | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            last = HttpError(exc.code, body, url)
            if exc.code in retry_status and attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            raise last from None
        except urllib.error.URLError as exc:
            last = HttpError(0, str(exc.reason), url)
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            raise last from None
        except TimeoutError:
            last = HttpError(0, "request timed out", url)
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            raise last from None
    assert last is not None  # pragma: no cover - loop always returns or raises
    raise last
