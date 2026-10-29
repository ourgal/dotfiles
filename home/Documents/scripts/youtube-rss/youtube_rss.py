#!/usr/bin/env python3
"""Convert a YouTube channel or user URL into an uploads RSS feed URL.

The standard YouTube channel feed contains the channel's uploaded videos.
Channel IDs and legacy usernames can be converted without a network request;
@handles and /c/ URLs are resolved by reading the channel page. If no URL is
provided, the script reads it from the system clipboard.

No third-party packages are required.
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from typing import Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen

RSS_ENDPOINT = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
CLIPBOARD_TIMEOUT = 5.0

CHANNEL_ID_PATTERN = r"UC[A-Za-z0-9_-]{22}"
CHANNEL_ID_RE = re.compile(rf"^{CHANNEL_ID_PATTERN}$")
CHANNEL_PATH_RE = re.compile(rf"/channel/({CHANNEL_ID_PATTERN})(?=/|$)")
CHANNEL_FEED_LINK_RE = re.compile(
    rf"https?://(?:www\.)?youtube\.com/feeds/videos\.xml"
    rf"\?channel_id=({CHANNEL_ID_PATTERN})(?![A-Za-z0-9_-])"
)
PATH_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
CANONICAL_RE = re.compile(r"""\brel=["']canonical["']""", re.IGNORECASE)
HREF_RE = re.compile(r"""\bhref=["']([^"']+)["']""", re.IGNORECASE)
CHANNEL_ID_PATTERNS = (
    re.compile(rf'"externalId":"({CHANNEL_ID_PATTERN})"'),
    re.compile(rf'"channelId":"({CHANNEL_ID_PATTERN})"'),
    re.compile(rf'"browseId":"({CHANNEL_ID_PATTERN})"'),
    re.compile(
        rf'itemprop=["\']identifier["\'][^>]*content=["\']'
        rf"({CHANNEL_ID_PATTERN})[\"']",
        re.IGNORECASE,
    ),
)


class ConversionError(ValueError):
    """Raised when the supplied URL cannot be converted to a feed URL."""


def read_clipboard() -> str:
    """Read text from the system clipboard using platform-native tools."""
    if sys.platform == "win32":
        candidates = [
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ],
        ]
    elif sys.platform == "darwin":
        candidates = [["pbpaste"]]
    else:
        candidates = [
            ["termux-clipboard-get"],
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-output"],
            ["xsel", "--clipboard", "--output"],
        ]

    for command in candidates:
        executable = shutil.which(command[0])
        if not executable:
            continue
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                capture_output=True,
                text=True,
                timeout=CLIPBOARD_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            text = result.stdout.strip().lstrip("\ufeff").strip()
            if text:
                return text

    raise ConversionError(
        "no URL was provided and the system clipboard is empty or unavailable"
    )


def channel_feed(channel_id: str) -> str:
    """Return the uploads RSS feed URL for a YouTube channel ID."""
    if not CHANNEL_ID_RE.fullmatch(channel_id):
        raise ConversionError(f"invalid YouTube channel ID: {channel_id!r}")
    return f"{RSS_ENDPOINT}?channel_id={quote(channel_id, safe='')}"


def user_feed(username: str) -> str:
    """Return the uploads RSS feed URL for a legacy YouTube username."""
    if not PATH_NAME_RE.fullmatch(username):
        raise ConversionError(f"invalid YouTube username: {username!r}")
    return f"{RSS_ENDPOINT}?user={quote(username, safe='')}"


def _normalize_url(value: str) -> str:
    """Add a scheme for common shorthand forms accepted on the command line."""
    value = value.strip()
    if not value:
        raise ConversionError("the YouTube URL is empty")

    if value.startswith("@"):
        return f"https://www.youtube.com/{value}"
    if value.startswith("/"):
        return f"https://www.youtube.com{value}"
    if re.match(r"(?i)^(?:www\.|m\.|music\.)?youtube\.com(?:/|$)", value):
        return f"https://{value}"
    if "://" not in value:
        raise ConversionError(
            "enter a YouTube channel/user URL, a channel ID, or an @handle"
        )
    return value


def _fetch_page(url: str, timeout: float) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "CONSENT=YES+cb; SOCS=CAI",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        page = response.read().decode(charset, errors="replace")
        final_url = response.geturl()
    return page, final_url


def _extract_channel_id(page: str, final_url: str) -> Optional[str]:
    """Find the current channel ID in a YouTube channel page."""
    page = html.unescape(page).replace("\\/", "/")

    # Channel pages advertise their uploads feed directly.
    match = CHANNEL_FEED_LINK_RE.search(page)
    if match:
        return match.group(1)

    # A redirect may already point at the canonical /channel/UC... URL.
    match = CHANNEL_PATH_RE.search(urlparse(final_url).path)
    if match:
        return match.group(1)

    # The canonical link is the next most reliable source.
    for tag in LINK_TAG_RE.findall(page):
        if not CANONICAL_RE.search(tag):
            continue
        href_match = HREF_RE.search(tag)
        if not href_match:
            continue
        canonical_url = urljoin(final_url, href_match.group(1))
        match = CHANNEL_PATH_RE.search(urlparse(canonical_url).path)
        if match:
            return match.group(1)

    # Last resort: well-known IDs embedded in the page's initial data.
    for pattern in CHANNEL_ID_PATTERNS:
        match = pattern.search(page)
        if match:
            return match.group(1)

    return None


def _resolve_channel_id(page_url: str, timeout: float) -> str:
    """Resolve an @handle or /c/ URL to its canonical channel ID."""
    page, final_url = _fetch_page(page_url, timeout)
    channel_id = _extract_channel_id(page, final_url)
    if channel_id:
        return channel_id
    raise ConversionError(
        "could not find a channel ID on the YouTube page; "
        "the handle may be invalid or YouTube may be showing a consent page"
    )


def youtube_url_to_rss(value: str, timeout: float = 20.0) -> str:
    """Convert a YouTube channel/user URL into an uploads RSS feed URL.

    Supported forms include /channel/UC..., /user/..., /@handle, /c/name,
    and bare channel IDs or @handles.
    """
    value = value.strip()
    if CHANNEL_ID_RE.fullmatch(value):
        return channel_feed(value)

    parsed = urlparse(_normalize_url(value))
    if parsed.scheme not in {"http", "https"}:
        raise ConversionError("the URL must use http:// or https://")

    host = (parsed.hostname or "").lower()
    if host not in YOUTUBE_HOSTS:
        raise ConversionError("the URL must point to youtube.com")

    # Accept an already-converted feed URL as a convenience.
    if parsed.path.rstrip("/") == "/feeds/videos.xml":
        query = parse_qs(parsed.query)
        channel_ids = query.get("channel_id", [])
        usernames = query.get("user", [])
        if channel_ids and CHANNEL_ID_RE.fullmatch(channel_ids[0]):
            return channel_feed(channel_ids[0])
        if usernames and PATH_NAME_RE.fullmatch(usernames[0]):
            return user_feed(usernames[0])
        raise ConversionError("the feed URL needs a valid channel_id or user")

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if not segments:
        raise ConversionError("the URL does not identify a YouTube channel or user")

    kind = segments[0].lower()

    if kind == "channel":
        if len(segments) < 2:
            raise ConversionError("the /channel/ URL is missing a channel ID")
        return channel_feed(segments[1])

    if kind == "user":
        if len(segments) < 2:
            raise ConversionError("the /user/ URL is missing a username")
        return user_feed(segments[1])

    if segments[0].startswith("@"):
        handle = segments[0][1:]
        if not PATH_NAME_RE.fullmatch(handle):
            raise ConversionError(f"invalid YouTube handle: @{handle}")
        page_url = f"https://www.youtube.com/@{quote(handle, safe='._-')}"
        return channel_feed(_resolve_channel_id(page_url, timeout))

    if kind in {"c", "custom"}:
        if len(segments) < 2:
            raise ConversionError("the custom channel URL is missing a name")
        name = segments[1]
        if not PATH_NAME_RE.fullmatch(name):
            raise ConversionError(f"invalid custom channel name: {name!r}")
        page_url = f"https://www.youtube.com/c/{quote(name, safe='._-')}"
        return channel_feed(_resolve_channel_id(page_url, timeout))

    raise ConversionError(
        "the URL is not a channel/user URL (expected /channel/, /user/, "
        "/@handle, or /c/name)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a YouTube channel or user URL into an RSS feed URL "
            "containing its uploaded videos. If URL is omitted or empty, "
            "it is read from the system clipboard."
        ),
        epilog=(
            "examples:\n"
            "  %(prog)s https://www.youtube.com/@YouTube\n"
            "  %(prog)s https://www.youtube.com/channel/"
            "UCBR8-60-B28hp2BmDPdntcQ\n"
            "  %(prog)s https://www.youtube.com/user/YouTube\n"
            "  %(prog)s                         # read the URL from the clipboard"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help=(
            "YouTube channel/user URL, channel ID, or @handle; "
            "omit to read it from the clipboard"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        metavar="SECONDS",
        help="network timeout when resolving @handles or /c/ URLs (default: 20)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        url = args.url.strip() if args.url else ""
        if not url:
            url = read_clipboard()
        print(youtube_url_to_rss(url, timeout=args.timeout))
    except ConversionError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
    except HTTPError as exc:
        print(
            f"{parser.prog}: error: YouTube returned HTTP {exc.code} "
            f"({exc.reason})",
            file=sys.stderr,
        )
        return 1
    except URLError as exc:
        print(f"{parser.prog}: error: could not reach YouTube: {exc.reason}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"{parser.prog}: error: network request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
