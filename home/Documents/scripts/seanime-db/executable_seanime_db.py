#!/usr/bin/env python3
"""Bootstrap Seanime's SQLite DB headlessly, then patch library settings.

A fresh datadir has the schema but no settings row: the server only writes it
during onboarding. This starts the server on a free port, POSTs /api/v1/start
to create the row, stops it, then updates library_path/library_paths and
torrent_provider directly in SQLite.

Seanime must be stopped while the settings are patched, otherwise the running
instance can overwrite them from memory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DB_NAME = "seanime.db"
ONBOARDING_BODY = {
    # Mirrors the defaults the onboarding UI sends for a brand-new install.
    "library": {
        "autoUpdateProgress": True,
        "enableManga": True,
        "updateChannel": "github",
    },
    "mediaPlayer": {},
    "torrent": {},
    "anilist": {},
    "discord": {},
    "manga": {},
    "notifications": {},
    "nakama": {},
    "enableTranscode": False,
    "enableTorrentStreaming": False,
    "debridProvider": "none",
    "debridApiKey": "",
}



class SetupError(RuntimeError):
    pass


def default_datadir() -> Path:
    env = os.environ.get("SEANIME_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(base) / "Seanime"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Seanime"
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "Seanime"


def find_exe(explicit: str | None) -> Path:
    if explicit:
        exe = Path(explicit).expanduser()
        if not exe.is_file():
            raise SetupError(f"seanime binary not found: {exe}")
        return exe
    for name in ("seanime", "seanime.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    # Scoop installs outside PATH shims are common enough to be worth checking.
    for candidate in (
        Path.home() / "scoop/apps/seanime-server/current/seanime.exe",
        Path.home() / "scoop/shims/seanime.exe",
    ):
        if candidate.is_file():
            return candidate
    raise SetupError("seanime binary not found; pass --seanime <path>")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def settings_ready(db: Path) -> bool:
    if not db.is_file():
        return False
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
        try:
            return con.execute("select count(*) from settings").fetchone()[0] > 0
        finally:
            con.close()
    except sqlite3.Error:
        return False


def log_tail(datadir: Path, lines: int = 20) -> str:
    logs = sorted((datadir / "logs").glob("*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return "(no log files)"
    return "\n".join(logs[-1].read_text(errors="replace").splitlines()[-lines:])


def api(port: int, method: str, path: str, payload: object = None, timeout: float = 15) -> bytes:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise SetupError(f"{method} {path} failed: HTTP {exc.code} {exc.read()[:300]!r}") from None
    except urllib.error.URLError as exc:
        raise SetupError(f"{method} {path} failed: {exc.reason}") from None


def bootstrap(datadir: Path, exe: Path, timeout: float) -> None:
    """Run the server once so it migrates a fresh DB and writes a settings row."""
    db = datadir / DB_NAME
    datadir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    proc = subprocess.Popen(
        [str(exe), "--datadir", str(datadir), "--port", str(port), "--disable-password"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                api(port, "GET", "/status", timeout=2)
                break
            except SetupError:
                if proc.poll() is not None:
                    raise SetupError(
                        f"seanime exited with code {proc.returncode}\n{log_tail(datadir)}"
                    ) from None
                if time.monotonic() > deadline:
                    raise SetupError(
                        f"timed out after {timeout:.0f}s waiting for the server\n"
                        f"{log_tail(datadir)}"
                    ) from None
                time.sleep(0.5)

        # /start is the onboarding endpoint: it upserts the settings row.
        # --disable-all-features would disable it, hence the plain launch.
        api(port, "POST", "/start", ONBOARDING_BODY)
        if not settings_ready(db):
            raise SetupError(f"server did not persist a settings row in {db}")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def normalize_libraries(libraries: list[str]) -> list[str]:
    paths = [Path(p).expanduser().resolve() for p in libraries]
    if len(set(paths)) != len(paths):
        raise SetupError("duplicate library paths")
    for i, path in enumerate(paths):
        for other in paths[i + 1 :]:
            if path in other.parents or other in path.parents:
                raise SetupError(f"library paths cannot be nested: {path} / {other}")
    return [p.as_posix() for p in paths]


def patch_settings(
    db: Path,
    *,
    libraries: list[str] | None = None,
    provider: str | None = None,
) -> list[str]:
    """Update settings in one transaction. Returns human-readable changes."""
    if not db.is_file():
        raise SetupError(f"database not found: {db}")

    assignments: list[tuple[str, object]] = []
    changes: list[str] = []

    if libraries:
        normalized = normalize_libraries(libraries)
        assignments.append(("library_path", normalized[0]))
        assignments.append(
            ("library_paths", ",".join(normalized[1:]) if len(normalized) > 1 else None)
        )
        changes.append(f"library_path = {normalized[0]}")
        if len(normalized) > 1:
            changes.append(f"library_paths = {', '.join(normalized[1:])}")

    if provider is not None:
        assignments.append(("torrent_provider", provider))
        changes.append(f"torrent_provider = {provider!r}")

    if not assignments:
        return changes

    # BEGIN IMMEDIATE fails fast when the server still holds the write lock.
    con = sqlite3.connect(db, timeout=5, isolation_level=None)
    try:
        con.execute("BEGIN IMMEDIATE")
        cols = {row[1] for row in con.execute("pragma table_info(settings)")}
        missing = {col for col, _ in assignments} - cols
        if missing:
            raise SetupError(f"settings table lacks columns: {', '.join(sorted(missing))}")
        sql = "update settings set " + ", ".join(f"{col}=?" for col, _ in assignments)
        sql += " where id = (select min(id) from settings)"
        cur = con.execute(sql, [value for _, value in assignments])
        if cur.rowcount != 1:
            raise SetupError(f"expected 1 settings row, updated {cur.rowcount}")
        con.execute("commit")
        con.execute("pragma wal_checkpoint(truncate)")
    except sqlite3.OperationalError as exc:
        con.execute("rollback") if con.in_transaction else None
        if "locked" in str(exc) or "busy" in str(exc):
            raise SetupError("database is locked; quit Seanime and retry") from None
        raise SetupError(f"sqlite error: {exc}") from None
    finally:
        con.close()
    return changes


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Seanime's SQLite DB if missing and patch library settings."
    )
    parser.add_argument("--datadir", help="Seanime data directory (default: platform default)")
    parser.add_argument("--seanime", help="path to the seanime binary")
    parser.add_argument(
        "--library",
        action="append",
        metavar="PATH",
        help="anime library path; repeat for multiple roots (first becomes the main library)",
    )
    parser.add_argument(
        "--provider",
        help="torrent provider extension id (e.g. animetosho-new); empty string clears it",
    )
    parser.add_argument("--timeout", type=float, default=120.0, help="bootstrap timeout seconds")
    parser.add_argument("--no-bootstrap", action="store_true", help="only patch an existing DB")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    datadir = Path(args.datadir).expanduser() if args.datadir else default_datadir()
    db = datadir / DB_NAME

    try:
        if not settings_ready(db):
            if args.no_bootstrap:
                raise SetupError(f"{db} is not initialized; drop --no-bootstrap")
            exe = find_exe(args.seanime)
            print(f"initializing {db} with {exe}")
            bootstrap(datadir, exe, args.timeout)
            print("settings row created")

        for path in args.library or []:
            if not Path(path).expanduser().is_dir():
                print(f"warning: library path does not exist yet: {path}", file=sys.stderr)

        changes = patch_settings(db, libraries=args.library, provider=args.provider)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"database: {db}")
    for change in changes:
        print(f"  {change}")
    if not changes:
        print("  settings unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
