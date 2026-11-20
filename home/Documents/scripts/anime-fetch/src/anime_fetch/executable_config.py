"""Shared constants for anime-fetch."""

from __future__ import annotations

from pathlib import Path

DEFAULT_LIB = str(Path.home() / "Videos" / "Seanime")

# AniList statuses that still have episodes left to air.
ONGOING_STATUSES = {"RELEASING", "NOT_YET_RELEASED", "HIATUS"}

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_AMBIGUOUS = 2
EXIT_SKIP = 3
