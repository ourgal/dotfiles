"""Clipboard reading and interactive confirmation edge cases."""

from __future__ import annotations

import subprocess
import sys as real_sys
from types import SimpleNamespace

import pytest

from anime_fetch import text


class _Stdin:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def _fake_sys(monkeypatch: pytest.MonkeyPatch, *, platform: str = "linux", tty: bool = True) -> None:
    monkeypatch.setattr(
        text,
        "sys",
        SimpleNamespace(platform=platform, stdin=_Stdin(tty), stderr=real_sys.stderr),
    )


def _clipboard(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    available: set[str],
    *,
    returncode: int = 0,
    stdout: bytes = b"Show Name\n",
    error: Exception | None = None,
) -> str | None:
    _fake_sys(monkeypatch, platform=platform)
    monkeypatch.delenv("TERMUX_VERSION", raising=False)
    monkeypatch.setattr(
        text.shutil, "which", lambda cmd: f"/bin/{cmd}" if cmd in available else None
    )

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if error is not None:
            raise error
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=b"")

    monkeypatch.setattr(text.subprocess, "run", fake_run)
    return text.clipboard_text()


def test_clipboard_powershell(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _clipboard(monkeypatch, "win32", {"powershell"}) == "Show Name"


def test_clipboard_pbpaste(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _clipboard(monkeypatch, "darwin", {"pbpaste"}) == "Show Name"


def test_clipboard_termux(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_sys(monkeypatch)
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    monkeypatch.setattr(
        text.shutil, "which", lambda cmd: f"/bin/{cmd}" if cmd == "termux-clipboard-get" else None
    )
    monkeypatch.setattr(
        text.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=b"Termux Show\n", stderr=b""),
    )
    assert text.clipboard_text() == "Termux Show"


@pytest.mark.parametrize("command", ["wl-paste", "xclip", "xsel"])
def test_clipboard_linux_utilities(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    assert _clipboard(monkeypatch, "linux", {command}) == "Show Name"


def test_clipboard_no_utility(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _clipboard(monkeypatch, "linux", set()) is None


def test_clipboard_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _clipboard(monkeypatch, "linux", {"wl-paste"}, error=OSError("missing")) is None
    assert (
        _clipboard(monkeypatch, "linux", {"wl-paste"}, error=subprocess.SubprocessError("boom"))
        is None
    )


@pytest.mark.parametrize(
    ("returncode", "stdout"), [(1, b"oops"), (0, b"   "), (0, b"")]
)
def test_clipboard_empty_or_failed_output(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: bytes
) -> None:
    assert (
        _clipboard(monkeypatch, "linux", {"wl-paste"}, returncode=returncode, stdout=stdout)
        is None
    )


def test_confirm_non_interactive(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _fake_sys(monkeypatch, tty=False)
    assert text.confirm("Proceed?") is False
    assert "--yes" in capsys.readouterr().err


@pytest.mark.parametrize("answer", ["y", "YES", " yes "])
def test_confirm_accepts_yes(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    _fake_sys(monkeypatch)
    monkeypatch.setattr(text, "input", lambda _prompt: answer, raising=False)
    assert text.confirm("Proceed?") is True


@pytest.mark.parametrize("answer", ["", "n", "maybe"])
def test_confirm_declines(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    _fake_sys(monkeypatch)
    monkeypatch.setattr(text, "input", lambda _prompt: answer, raising=False)
    assert text.confirm("Proceed?") is False


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_confirm_interrupted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], exc: type[Exception]
) -> None:
    _fake_sys(monkeypatch)

    def interrupt(_prompt: str) -> str:
        raise exc

    monkeypatch.setattr(text, "input", interrupt, raising=False)
    assert text.confirm("Proceed?") is False
    assert capsys.readouterr().out == "\n"
