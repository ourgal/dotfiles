# file-organizer

Sort files in a download folder into English category folders (`Videos`, `Audio`, `Documents`, `Archives`, `Installers`, ...). Dependencies and the environment are managed by [uv](https://docs.astral.sh/uv/).

## Usage

Run from the project folder:

```bash
uv run file-organizer                  # preview, moves nothing
uv run file-organizer --apply          # move files
uv run file-organizer -v --apply       # move files and list each one
uv run file-organizer --undo           # roll back the last run
```

By default it organizes the project's parent folder (i.e. `Downloads`) and creates the category folders there. To organize another folder:

```bash
uv run file-organizer -s "D:\Downloads" -d "D:\Downloads\sorted" --apply
```

## Behavior

- Only top-level files are handled; no recursion, existing subfolders are left alone.
- Hidden files and `desktop.ini` / `Thumbs.db` are skipped by default (`--include-hidden` overrides).
- Name clashes are resolved with `(1)`, `(2)` suffixes; nothing is overwritten.
- Every `--apply` writes a JSON log under `.state/runs/`; `--undo` replays it in reverse.
- Category rules live in `CATEGORIES` in `src/file_organizer/cli.py`; edit as needed.
