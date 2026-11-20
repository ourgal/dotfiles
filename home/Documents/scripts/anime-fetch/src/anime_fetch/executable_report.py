"""Human-readable output for release plans."""

from __future__ import annotations

from pathlib import Path

from . import pick


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{num} B"


def print_plan(plan: pick.Plan, destination: Path, *, wanted: set[int]) -> None:
    episodes = sorted(set(plan.episodes) & wanted)
    print(
        f"Selected : {plan.strategy} ({len(plan.torrents)} torrent(s), "
        f"{len(episodes)}/{len(wanted)} episodes)"
    )
    for cand in plan.torrents:
        covered = sorted(cand.episodes & wanted)
        shows = covered if len(covered) <= 12 else f"{min(covered)}-{max(covered)}"
        print(f"  [{cand.group}] {cand.torrent.get('name')}")
        print(f"      {human_size(cand.size)}, {cand.seeders} seeds, episodes {shows}")
    print(f"Destination: {destination}")
    print(f"Total size : {human_size(plan.size)}")
