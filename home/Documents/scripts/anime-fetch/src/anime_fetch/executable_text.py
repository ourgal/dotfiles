"""Clipboard input and interactive confirmation."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import urllib.parse

_URL = re.compile(r"https?://[^\s<>\"']+")


def clipboard_text() -> str | None:
    """Read the system clipboard with the first available native utility."""
    if sys.platform == "win32":
        commands = [["powershell", "-NoProfile", "-Command",
                     "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw"]]
    elif sys.platform == "darwin":
        commands = [["pbpaste"]]
    else:
        commands = [["termux-clipboard-get"]] if os.environ.get("TERMUX_VERSION") else []
        commands += [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(command, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        text = result.stdout.decode("utf-8", "replace").strip()
        if result.returncode == 0 and text:
            return text
    return None


def query_from_text(text: str) -> str:
    """Turn clipboard contents into a query: the first text line, or a URL slug."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    match = _URL.search(first)
    if match is None:
        return first
    before = first[: match.start()].strip(" \t-|·:")
    if re.search(r"[A-Za-z0-9]", before):
        return before
    path = urllib.parse.urlparse(match.group(0)).path
    segments = [urllib.parse.unquote(seg) for seg in path.split("/") if seg]
    # AniList/MAL URLs look like /anime/<id>/<slug>; a bare trailing ID is not
    # searchable, so refuse it instead of searching for "anime".
    if not segments or segments[-1].isdigit():
        return ""
    return re.sub(r"[-_]+", " ", segments[-1]).strip()


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        print("Confirm  : no interactive terminal; re-run with --yes to skip the prompt",
              file=sys.stderr)
        return False
    try:
        answer = input(f"{question} [y/N] ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in {"y", "yes"}
