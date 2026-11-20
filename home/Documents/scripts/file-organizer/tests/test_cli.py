"""Tests for the file-organizer download-folder sorter.

Everything runs in temporary directories: nothing here touches the real
Downloads folder. The CLI's journal directory is redirected to a throwaway
project root, and console output is checked through a StringIO console.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import stat
from io import StringIO
from pathlib import Path
from typing import cast

import pytest
from rich.console import Console

from file_organizer import cli

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def plain(text: str) -> str:
    """Strip ANSI styling and squeeze whitespace so assertions survive wrapping."""
    return " ".join(ANSI.sub("", text).split())


def touch(folder: Path, *names: str, content: bytes = b"x") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def printed(console: Console) -> str:
    return plain(cast(StringIO, console.file).getvalue())


def write_run(
    project: Path,
    moves: list[tuple[Path, Path, str]],
    stamp: str = "20260101-120000-000000",
) -> Path:
    """Write an undo journal the same shape write_journal produces."""
    runs = project / cli.STATE_DIRNAME / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / f"{stamp}.json"
    payload = {
        "created": "2026-01-01T12:00:00",
        "source": str(moves[0][0].parent),
        "moves": [{"src": str(src), "dst": str(dst), "category": cat} for src, dst, cat in moves],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def console() -> Console:
    return Console(file=StringIO(), width=200)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "file-organizer"\n', encoding="utf-8")
    return root


@pytest.fixture()
def app(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the CLI's project root (and thus its journal) to a temp dir."""
    monkeypatch.setattr(cli, "find_project_root", lambda: project)
    return project


# ------------------------------------------------------------------- formatting
@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1024**2, "1.0 MB"),
        (5 * 1024**2 + 512 * 1024, "5.5 MB"),
        (1024**3, "1.0 GB"),
        (1024**4, "1.0 TB"),
    ],
)
def test_human_size(size: int, expected: str) -> None:
    assert cli.human_size(size) == expected


@pytest.mark.parametrize(
    ("name", "limit", "expected"),
    [
        ("short.mp4", 46, "short.mp4"),
        ("abcdefghij", 10, "abcdefghij"),
        ("abcdefghijk", 10, "abcdefg..."),
        ("abcdefghij", 9, "abcdef..."),
    ],
)
def test_shorten(name: str, limit: int, expected: str) -> None:
    assert cli.shorten(name, limit) == expected


# ------------------------------------------------------------------ destination
def test_unique_dest_returns_plain_name_when_free(tmp_path: Path) -> None:
    assert cli.unique_dest(tmp_path, "clip.mp4", set()) == tmp_path / "clip.mp4"


def test_unique_dest_adds_counter_for_existing_files(tmp_path: Path) -> None:
    touch(tmp_path, "clip.mp4", "clip (1).mp4")
    assert cli.unique_dest(tmp_path, "clip.mp4", set()) == tmp_path / "clip (2).mp4"


def test_unique_dest_honours_reserved_names_case_insensitively(tmp_path: Path) -> None:
    assert cli.unique_dest(tmp_path, "Photo.JPG", {"photo.jpg"}) == tmp_path / "Photo (1).JPG"


def test_unique_dest_handles_names_without_suffix(tmp_path: Path) -> None:
    touch(tmp_path, "README")
    assert cli.unique_dest(tmp_path, "README", set()) == tmp_path / "README (1)"


# ------------------------------------------------------------------- planning
def test_plan_moves_categorises_and_sorts(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "b.MP4", "a.pdf", "weird.xyz")

    moves = cli.plan_moves(src, dst)

    assert [(m.src.name, m.category) for m in moves] == [
        ("a.pdf", "Documents"),
        ("b.MP4", "Videos"),
        ("weird.xyz", cli.OTHER),
    ]
    assert moves[0].dst == dst / "Documents" / "a.pdf"
    # planning must not create the target tree yet
    assert not dst.exists()


def test_plan_moves_skips_directories_excluded_and_hidden(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src / "nested", "deep.mkv")  # must not recurse
    touch(src, "desktop.ini", "DESKTOP.INI", "Thumbs.db", ".secret.pdf", "keep.pdf")

    moves = cli.plan_moves(src, dst)

    assert [m.src.name for m in moves] == ["keep.pdf"]


def test_plan_moves_can_include_hidden_files(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, ".secret.pdf", "keep.pdf")

    moves = cli.plan_moves(src, dst, include_hidden=True)

    assert [m.src.name for m in moves] == [".secret.pdf", "keep.pdf"]


def test_plan_moves_uses_only_the_last_suffix(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "backup.tar.gz", "noextension")

    moves = {m.src.name: m.category for m in cli.plan_moves(src, dst)}

    assert moves == {"backup.tar.gz": "Archives", "noextension": cli.OTHER}


def test_plan_moves_avoids_existing_targets(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "clip.mkv")
    touch(dst / "Videos", "clip.mkv")

    [move] = cli.plan_moves(src, dst)

    assert move.dst == dst / "Videos" / "clip (1).mkv"


# -------------------------------------------------------------------- applying
def test_apply_moves_moves_files_and_writes_journal(project: Path, console: Console, tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "a.pdf", content=b"pdf")
    touch(src, "b.mp4", content=b"mp4")

    done, failed = cli.apply_moves(cli.plan_moves(src, dst), project, console, verbose=False)

    assert failed == []
    assert {(m.src.name, m.dst.parent.name) for m in done} == {
        ("a.pdf", "Documents"),
        ("b.mp4", "Videos"),
    }
    assert (dst / "Documents" / "a.pdf").read_bytes() == b"pdf"
    assert (dst / "Videos" / "b.mp4").read_bytes() == b"mp4"
    assert not (src / "a.pdf").exists()
    assert not (src / "b.mp4").exists()

    [journal] = list((project / cli.STATE_DIRNAME / "runs").glob("*.json"))
    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert payload["source"] == str(src)
    assert {(Path(item["src"]).name, item["category"]) for item in payload["moves"]} == {
        ("a.pdf", "Documents"),
        ("b.mp4", "Videos"),
    }


def test_apply_moves_rechecks_collisions_at_move_time(
    project: Path, console: Console, tmp_path: Path
) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "movie.mkv", content=b"new")
    moves = cli.plan_moves(src, dst)
    # Another program drops a file into the category folder after planning.
    touch(dst / "Videos", "movie.mkv", content=b"old")

    done, failed = cli.apply_moves(moves, project, console, verbose=False)

    assert failed == []
    assert done[0].dst.name == "movie (1).mkv"
    assert (dst / "Videos" / "movie.mkv").read_bytes() == b"old"
    assert (dst / "Videos" / "movie (1).mkv").read_bytes() == b"new"


def test_apply_moves_reports_failures_and_logs_only_moved_files(
    project: Path, console: Console, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "a.pdf")
    touch(src, "locked.mp4")

    real_move = shutil.move

    def flaky(source: str, target: str) -> None:
        if Path(source).name == "locked.mp4":
            raise OSError("file is in use")
        real_move(source, target)

    monkeypatch.setattr(cli.shutil, "move", flaky)

    done, failed = cli.apply_moves(cli.plan_moves(src, dst), project, console, verbose=False)

    assert [m.src.name for m in done] == ["a.pdf"]
    assert [move.src.name for move, _ in failed] == ["locked.mp4"]
    assert "file is in use" in failed[0][1]
    assert (src / "locked.mp4").exists()

    [journal] = list((project / cli.STATE_DIRNAME / "runs").glob("*.json"))
    payload = json.loads(journal.read_text(encoding="utf-8"))
    assert [Path(item["src"]).name for item in payload["moves"]] == ["a.pdf"]


def test_apply_moves_writes_no_journal_when_nothing_moved(
    project: Path, console: Console, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    src.mkdir()
    touch(src, "locked.mp4")

    def always_fails(source: str, target: str) -> None:
        raise OSError("in use")

    monkeypatch.setattr(cli.shutil, "move", always_fails)

    done, failed = cli.apply_moves(cli.plan_moves(src, dst), project, console, verbose=False)

    assert done == []
    assert len(failed) == 1
    assert not (project / cli.STATE_DIRNAME).exists()


# ----------------------------------------------------------------------- undo
def test_undo_without_journal(project: Path, console: Console) -> None:
    assert cli.undo_last_run(project, console, verbose=False) == 1
    assert "No undo log found" in printed(console)


def test_undo_restores_files_and_removes_log(project: Path, console: Console, tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    touch(dst / "Documents", "a.pdf", content=b"pdf")
    touch(dst / "Videos", "b.mp4", content=b"mp4")
    log = write_run(
        project,
        [
            (src / "a.pdf", dst / "Documents" / "a.pdf", "Documents"),
            (src / "b.mp4", dst / "Videos" / "b.mp4", "Videos"),
        ],
    )

    assert cli.undo_last_run(project, console, verbose=False) == 0

    assert (src / "a.pdf").read_bytes() == b"pdf"
    assert (src / "b.mp4").read_bytes() == b"mp4"
    assert not (dst / "Documents" / "a.pdf").exists()
    assert not (dst / "Videos" / "b.mp4").exists()
    assert not log.exists()
    assert "log cleared" in printed(console)


def test_undo_keeps_log_when_original_name_is_taken(
    project: Path, console: Console, tmp_path: Path
) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    touch(src, "a.pdf", content=b"blocker")
    touch(dst / "Documents", "a.pdf", content=b"moved")
    log = write_run(project, [(src / "a.pdf", dst / "Documents" / "a.pdf", "Documents")])

    assert cli.undo_last_run(project, console, verbose=False) == 1

    assert log.exists()
    payload = json.loads(log.read_text(encoding="utf-8"))
    assert [Path(item["dst"]).name for item in payload["moves"]] == ["a.pdf"]
    assert (src / "a.pdf").read_bytes() == b"blocker"
    assert "could not be restored" in printed(console)

    # Once the blocker is gone the retained log can finish the rollback.
    (src / "a.pdf").unlink()
    assert cli.undo_last_run(project, console, verbose=False) == 0
    assert (src / "a.pdf").read_bytes() == b"moved"
    assert not log.exists()


def test_undo_skips_files_missing_from_category_folder(
    project: Path, console: Console, tmp_path: Path
) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    log = write_run(project, [(src / "gone.pdf", dst / "Documents" / "gone.pdf", "Documents")])

    assert cli.undo_last_run(project, console, verbose=False) == 0

    assert not log.exists()
    assert "Skipped" in printed(console)


def test_undo_reports_unreadable_log(project: Path, console: Console) -> None:
    path = project / cli.STATE_DIRNAME / "runs" / "broken.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    assert cli.undo_last_run(project, console, verbose=False) == 2
    assert "Cannot read undo log" in printed(console)


def test_undo_replays_only_the_latest_run(project: Path, console: Console, tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "sorted"
    touch(dst / "Documents", "old.pdf", "new.pdf")
    older = write_run(
        project,
        [(src / "old.pdf", dst / "Documents" / "old.pdf", "Documents")],
        stamp="20260101-000000-000000",
    )
    latest = write_run(
        project,
        [(src / "new.pdf", dst / "Documents" / "new.pdf", "Documents")],
        stamp="20260102-000000-000000",
    )

    assert cli.undo_last_run(project, console, verbose=False) == 0

    assert not latest.exists()
    assert older.exists()
    assert (src / "new.pdf").is_file()
    assert not (src / "old.pdf").exists()
    assert (dst / "Documents" / "old.pdf").is_file()


# ------------------------------------------------------------------ detection
def test_is_hidden_detects_dotfiles(tmp_path: Path) -> None:
    hidden = tmp_path / ".secret"
    hidden.write_text("x", encoding="utf-8")
    assert cli.is_hidden(hidden) is True


def test_is_hidden_accepts_plain_files(tmp_path: Path) -> None:
    visible = tmp_path / "visible.txt"
    visible.write_text("x", encoding="utf-8")
    assert cli.is_hidden(visible) is False


@pytest.mark.skipif(os.name != "nt", reason="Windows file attributes")
@pytest.mark.parametrize("flag", [stat.FILE_ATTRIBUTE_HIDDEN, stat.FILE_ATTRIBUTE_SYSTEM])
def test_is_hidden_detects_windows_attributes(tmp_path: Path, flag: int) -> None:
    path = tmp_path / "flagged.txt"
    path.write_text("x", encoding="utf-8")
    kernel32 = getattr(ctypes, "windll").kernel32
    assert kernel32.SetFileAttributesW(str(path), flag)
    try:
        assert cli.is_hidden(path) is True
    finally:
        kernel32.SetFileAttributesW(str(path), stat.FILE_ATTRIBUTE_NORMAL)


# ------------------------------------------------------------------ project root
def test_find_project_root_walks_up_to_pyproject(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "__file__", str(project / "src" / "file_organizer" / "cli.py"))
    assert cli.find_project_root() == project


def test_default_source_is_the_projects_parent(app: Path) -> None:
    assert cli.default_source() == app.parent


# --------------------------------------------------------------------- the CLI
def test_main_preview_moves_nothing(app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    src = tmp_path / "Downloads"
    src.mkdir()
    touch(src, "clip.mkv")

    assert cli.main(["-s", str(src), "-d", str(src)]) == 0

    assert (src / "clip.mkv").is_file()
    assert not (src / "Videos").exists()
    out = plain(capsys.readouterr().out)
    assert "Preview only" in out
    assert "Videos" in out


def test_main_apply_then_undo(app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    src = tmp_path / "Downloads"
    src.mkdir()
    touch(src, "movie.mkv")

    assert cli.main(["-s", str(src), "--apply"]) == 0

    assert (src / "Videos" / "movie.mkv").is_file()
    assert len(list((app / cli.STATE_DIRNAME / "runs").glob("*.json"))) == 1

    assert cli.main(["--undo"]) == 0

    assert (src / "movie.mkv").is_file()
    assert not (src / "Videos" / "movie.mkv").exists()


def test_main_reports_missing_source(app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli.main(["-s", str(tmp_path / "nope")]) == 2
    assert "Directory not found" in plain(capsys.readouterr().out)


def test_main_rejects_file_as_destination(
    app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    touch(src, "a.pdf")
    dest = tmp_path / "dest"
    dest.write_text("", encoding="utf-8")

    assert cli.main(["-s", str(src), "-d", str(dest)]) == 2
    assert "Destination is not a directory" in plain(capsys.readouterr().out)


def test_main_reports_nothing_to_organize(
    app: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    src = tmp_path / "src"
    src.mkdir()

    assert cli.main(["-s", str(src)]) == 0
    assert "Nothing to organize" in plain(capsys.readouterr().out)


def test_main_handles_keyboard_interrupt(
    app: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "src"
    src.mkdir()

    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "plan_moves", interrupted)

    assert cli.main(["-s", str(src)]) == 130
    assert "Cancelled" in plain(capsys.readouterr().out)


def test_main_handles_permission_error(
    app: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = tmp_path / "src"
    src.mkdir()

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(cli, "plan_moves", denied)

    assert cli.main(["-s", str(src)]) == 3
    assert "Permission denied" in plain(capsys.readouterr().out)
