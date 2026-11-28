#!/usr/bin/env python3
"""Golden-output diff for a behavior-preserving refactor with no test suite.

Runs the script at a git revision and the current working copy against the same
fixture inputs, in separate directory trees, then diffs the resulting outputs.
Exit 0 = identical, 1 = differences, 2 = a run failed.

    python golden_diff.py gen.py --fixtures fixtures/
    python golden_diff.py gen.py --fixtures fixtures/ --git-ref HEAD~1 --workdir ./probe

The script is expected to read its inputs from relative paths in the current
directory (most generators do). The fixture dir must contain every input the
script needs, plus pre-created outputs whose absence would trigger side effects
(an already-resized cover.jpg, a warm cache dir, an existing generated file).
The script file itself is excluded from the comparison -- it differs by design.
"""

import argparse
import difflib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def tree_files(root: Path) -> set[Path]:
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def compare(old: Path, new: Path, skip: set[Path]) -> int:
    """Print mismatches between two trees; return the number of differing files."""
    old_files = tree_files(old) - skip
    new_files = tree_files(new) - skip
    diffs = 0
    for rel in sorted(old_files ^ new_files):
        print(f"only in {'old' if rel in old_files else 'new'}: {rel}")
        diffs += 1
    for rel in sorted(old_files & new_files):
        a, b = old / rel, new / rel
        if a.read_bytes() == b.read_bytes():
            continue
        diffs += 1
        print(f"\n--- {rel} (old -> new)")
        lines = difflib.unified_diff(
            a.read_text(encoding="utf-8", errors="replace").splitlines(),
            b.read_text(encoding="utf-8", errors="replace").splitlines(),
            "old",
            "new",
            lineterm="",
            n=2,
        )
        for line in lines:
            print(line)
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, help="script being refactored")
    ap.add_argument("--fixtures", type=Path, required=True, help="dir of inputs copied into both runs")
    ap.add_argument("--git-ref", default="HEAD", help="revision to compare against (default HEAD)")
    ap.add_argument("--workdir", type=Path, help="where old/ and new/ are built (default: temp dir)")
    args = ap.parse_args()

    script = args.script.resolve()
    fixtures = args.fixtures.resolve()
    if not fixtures.is_dir():
        sys.exit(f"fixtures dir not found: {fixtures}")

    work = (args.workdir or Path(tempfile.mkdtemp(prefix="golden_diff_"))).resolve()
    print(f"workdir: {work}")

    head = subprocess.run(
        ["git", "-C", str(script.parent), "show", f"{args.git_ref}:{script.name}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if head.returncode != 0:
        sys.exit(f"cannot read {args.git_ref}:{script.name}: {head.stderr.strip()}")

    failed = False
    for side, source in (("old", head.stdout), ("new", script.read_text(encoding="utf-8"))):
        dest = work / side
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(fixtures, dest)
        (dest / script.name).write_text(source.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        run = subprocess.run(
            [sys.executable, script.name],
            cwd=dest,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(f"{side}: exit {run.returncode}")
        if run.returncode != 0:
            failed = True
            print((run.stderr or run.stdout).strip()[-1200:])

    diffs = compare(work / "old", work / "new", {Path(script.name)})
    if failed:
        return 2
    print("IDENTICAL" if diffs == 0 else f"\n{diffs} differing file(s) -- justify each or revert")
    return 0 if diffs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
