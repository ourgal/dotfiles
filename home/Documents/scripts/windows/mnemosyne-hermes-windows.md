# Mnemosyne + Hermes Agent on native Windows — install and integration notes

Written 2026-11-23 from the setup actually present on this machine, cross-checked against
the upstream [Hermes integration guide](https://github.com/mnemosyne-oss/mnemosyne/blob/main/docs/hermes-integration.md)
and the Hermes [Memory Providers docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers).

Mnemosyne is a **local-first memory provider plugin**: SQLite + vector/FTS5 hybrid recall in
`%LOCALAPPDATA%\hermes\mnemosyne\data\mnemosyne.db`. No cloud account or API key is needed for the
provider itself (an embedding model is downloaded on first use if local embeddings are enabled).

## Current state on this machine (reference)

| Item | Value |
| --- | --- |
| Hermes | v0.23.0, git install at `C:\Users\zxc\AppData\Local\hermes\hermes-agent` |
| Hermes home (`$HERMES_HOME`) | `C:\Users\zxc\AppData\Local\hermes` (on native Windows, `~/.hermes` resolves here, **not** `C:\Users\zxc\.hermes`) |
| Hermes Python | 3.14.9, the uv-managed interpreter under `%LOCALAPPDATA%\hermes\tools\python-3.14.9+*\python.exe` |
| Mnemosyne core | `mnemosyne-memory` 4.0.0 |
| Hermes provider | `mnemosyne-hermes` 0.7.7 |
| Side venv (persistent) | `C:\Users\zxc\AppData\Local\hermes\.mnemosyne\venv` |
| Side venv Python | `...\.mnemosyne\venv\Scripts\python.exe` (same 3.14 minor version as Hermes) |
| Side venv installer | `...\.mnemosyne\venv\Scripts\mnemosyne-hermes.exe` |
| Plugin wrapper | `C:\Users\zxc\AppData\Local\hermes\plugins\mnemosyne\` (real directory, mode `wrapper`) |
| Override skill | `C:\Users\zxc\AppData\Local\hermes\skills\memory\mnemosyne-memory-override\SKILL.md` |
| Database | `C:\Users\zxc\AppData\Local\hermes\mnemosyne\data\mnemosyne.db` |
| CLI shims (optional, via `uv tool`) | `C:\Users\zxc\scoop\persist\uv\tools\shims\mnemosyne*.exe` |

Relevant config in `%LOCALAPPDATA%\hermes\config.yaml`:

```yaml
plugins:
  enabled:
    - hermes-mnemosyne
  entries:
    hermes-mnemosyne:
      allow_tool_override: false
memory:
  provider: mnemosyne
```

`hermes memory status` reports `Provider: mnemosyne`, plugin installed and available, with
built-in `MEMORY.md` / `USER.md` still enabled alongside it.

## Why this particular install shape

Native Windows cannot reliably symlink the plugin (`WinError 1314` without Developer Mode), so the
supported route here is **persistent side-venv wrapper mode**:

- Hermes' own environment is left untouched.
- Mnemosyne's Python dependencies live in `%HERMES_HOME%\.mnemosyne\venv` and survive Hermes updates.
- `%HERMES_HOME%\plugins\mnemosyne` is a real directory containing `mnemosyne-wrapper.json`,
  `_mnemosyne_bootstrap.py`, `plugin.yaml` and `cli.py`. The bootstrap adds the side venv's
  `site-packages` to `sys.path` before importing `mnemosyne_hermes`.
- The side venv **must use the same Python major/minor as the running Hermes** (3.14 here). The
  bootstrap rejects a mismatched environment at load time.

## Install procedure (PowerShell, fresh shell)

Run as the same Windows user and in the same Hermes profile that will use Mnemosyne.

### 1. Select the active Hermes home and its Python

```powershell
$HermesHome = Join-Path $env:LOCALAPPDATA 'hermes'   # use the profile home instead if using profiles
$env:HERMES_HOME = $HermesHome

# Use the interpreter that actually runs Hermes. On this box it is the uv-managed
# Python under %LOCALAPPDATA%\hermes\tools\python-3.14.9+*\python.exe.
$HermesPython = (Get-ChildItem (Join-Path $env:LOCALAPPDATA 'hermes\tools\python-*\python.exe') |
                 Select-Object -First 1).FullName
& $HermesPython -V        # must match `hermes --version` (Python: 3.14.9)
```

Do not substitute an arbitrary `python` from `PATH`; `--python` is authoritative but does not
prove the interpreter belongs to Hermes. `hermes --version` and the side venv's `pyvenv.cfg`
are the evidence to use.

### 2. Create a new, empty persistent side venv

```powershell
$ErrorActionPreference = 'Stop'
$SideVenv = Join-Path $HermesHome '.mnemosyne\venv'
if (Test-Path -LiteralPath $SideVenv) { throw "Refusing to replace existing side venv: $SideVenv" }

uv venv --seed --python $HermesPython $SideVenv
$SidePython    = Join-Path $SideVenv 'Scripts\python.exe'
$SideInstaller = Join-Path $SideVenv 'Scripts\mnemosyne-hermes.exe'
```

`--seed` provides pip. If `uv` is missing, install it first; do not run a bare `uv venv`, which
could pick a different Python minor. Choose a new path (or keep a rollback copy) — both this
command and the installer refuse to overwrite an existing side venv.

### 3. Install the packages into the side venv

```powershell
& $SidePython -m pip install "mnemosyne-memory[embeddings,mcp]" mnemosyne-hermes
```

`[embeddings]` is the normal local semantic-search profile. `[mcp]` adds the `mcp` package
(`mcp>=2.0.0,!=2.1.0`) needed by `mnemosyne mcp`; without it MCP clients (omp, Crush, CodeBuddy,
pi) fail to start the server. `[all]` adds local-LLM consolidation dependencies
(`llama-cpp-python` etc.) and on Windows may need MSVC/Build Tools — start with
`[embeddings,mcp]` unless local LLM consolidation is required. `core` alone is not valid for a
`mnemosyne-hermes` wrapper install.

This machine currently resolves that to `mnemosyne-memory` 4.0.0 + `mnemosyne-hermes` 0.7.7;
add `==4.0.0` / `==0.7.7` if an exact reproduction is wanted.

### 4. Install the wrapper plugin

```powershell
& $SideInstaller install --mode wrapper --python $SidePython --no-profile-links
```

Windows defaults to wrapper mode anyway; the explicit flag makes it unambiguous. Omit
`--no-profile-links` only if other profiles should be linked to the same wrapper. If you ever
get `WinError 1314` from an explicit `--mode symlink` install, retry with this wrapper command
instead of enabling Developer Mode.

### 5. Enable the plugin and select the provider

```powershell
hermes plugins enable hermes-mnemosyne --no-allow-tool-override
hermes config set memory.provider mnemosyne
```

`--no-allow-tool-override` keeps Hermes' built-in tools intact. Only one external provider can
be active at a time; built-in memory remains active alongside it. **Do not** run
`hermes tools disable memory` — that disables the memory toolset, including provider tools.
`hermes memory off` is the correct way to disable just the external provider.

### 6. Restart and verify

Start a new Hermes session (or restart the gateway if it is running), then:

```powershell
hermes memory status
& $SideInstaller status
```

Expected on this machine: `Provider: mnemosyne`, plugin `installed ✓` / `available ✓`,
installer `Mode: wrapper`, `Selected environment: ...\.mnemosyne\venv\Lib\site-packages`.
The installer `status` check is metadata-only by design; it does not import the provider.

Confirm the runtime tool surface with `hermes tools list | grep mnemosyne_` (bash) or the
equivalent PowerShell select-string. The available mnemosyne tools are version-specific —
trust the runtime list, not a memorised inventory.

## Optional: standalone CLI shims

The provider does not require these, but `uv tool install mnemosyne-memory` exposes the core CLI
(`mnemosyne`, `mnemosyne-install`, `mnemosyne-auto-save`, `mnemosyne-browser`,
`mnemosyne-uninstall`) on `PATH`. With uv's tools dir on PATH (here under
`C:\Users\zxc\scoop\persist\uv\tools\shims`):

```bash
mnemosyne --help          # store / recall / stats / sleep / diagnose / export / import / backup ...
mnemosyne recall "..."
```

For the wrapper route, use the copy inside the side venv so it reads the same environment:

```powershell
& (Join-Path $SideVenv 'Scripts\mnemosyne.exe') stats
```

The packaged Hermes CLI (`hermes mnemosyne ...`) uses the provider DB under
`%HERMES_HOME%\mnemosyne\data` regardless of `MNEMOSYNE_DATA_DIR`.

## Day-to-day behaviour

- Hermes injects provider context, prefetches relevant memories before each turn, syncs turns
  after responses and mirrors built-in memory writes to Mnemosyne.
- The agent gets `mnemosyne_*` tools for recall/remember, the temporal knowledge graph,
  scratchpad, shared surfaces, export/import, sync and diagnostics.
- The `mnemosyne-memory-override` skill is **not** active by default: the default policy keeps
  small standing rules in Hermes' bounded always-injected memory tier and puts bulk durable
  facts in Mnemosyne. It only applies if the user explicitly chooses the strict Mnemosyne-only
  policy.
- `hermes memory setup` / `hermes memory status` / `hermes memory off` are the general
  provider controls.

## Maintenance

Upgrade the side venv (do not use a bare system `pip`):

```powershell
& $SidePython -m pip install --upgrade "mnemosyne-memory[embeddings,mcp]" mnemosyne-hermes
& $SideInstaller install --mode wrapper --python $SidePython --force
# restart Hermes, then: hermes memory status ; & $SideInstaller status
```

`--force` regenerates the wrapper files and does not touch the database. Only use it after
confirming `%HERMES_HOME%\plugins\mnemosyne` is the Mnemosyne wrapper you intend to replace.

Back up the store:

```powershell
& (Join-Path $SideVenv 'Scripts\mnemosyne.exe') backup      # or: export backup.json
```

Uninstall the integration:

```powershell
& $SideInstaller uninstall        # removes the plugin registration
hermes memory off                 # clears the active external provider
```

Keep (or explicitly delete) `%HERMES_HOME%\.mnemosyne\venv` and `%HERMES_HOME%\mnemosyne\data`
yourself — the uninstaller does not decide that for you.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `WinError 1314` on `--mode symlink` | Expected without Developer Mode/elevation. Use `--mode wrapper` instead; no privilege needed. |
| "Runtime Python compatibility error … recreate the Mnemosyne environment using Hermes' Python" | The side venv was built with a different Python minor. Recreate `%HERMES_HOME%\.mnemosyne\venv` with the verified `$HermesPython`, reinstall the packages, then re-run the wrapper installer with `--force`. |
| `hermes memory status` shows provider unavailable | Confirm the plugin is enabled (`hermes plugins list`), `memory.provider` is `mnemosyne`, the side venv has both packages, and restart the session/gateway. |
| Provider gone after a Hermes update | Wrapper is persistent; refresh with `--force` against the same `$SidePython`, restart Hermes, re-run both status checks. |
| MCP client (omp / Crush / CodeBuddy / pi) reports the mnemosyne server failed, or `mnemosyne mcp` prints only `Error: cli_unexpected_failure` | The side venv lacks the `mcp` extra. Install it with `& $SidePython -m pip install "mnemosyne-memory[mcp]"` (the CLI hides the underlying `RuntimeError: MCP not installed`). Confirm with `mnemosyne mcp` answering an `initialize` request over stdio. |
| `No module named pip` from a Hermes-managed venv | Use `uv pip install --python "<hermes-python>" "mnemosyne-memory[embeddings,mcp]" mnemosyne-hermes` instead. |
| Provider tools missing from the tool list | Check `hermes memory status` first; do not disable the `memory` toolset. `allow_tool_override: false` is the intended setting. |
| Embeddings fail after changing endpoint/model | `MNEMOSYNE_EMBEDDING_API_URL` / `MNEMOSYNE_EMBEDDINGS_VIA_API` route text to a remote service; local `[embeddings]` avoids sending memory text off-box. Set `MNEMOSYNE_EMBEDDING_DIM` for unknown API models. |

## Sources

- https://github.com/mnemosyne-oss/mnemosyne/blob/main/docs/hermes-integration.md (canonical setup guide, Windows wrapper section)
- https://github.com/mnemosyne-oss/mnemosyne (README: profiles, upgrade, privacy notes)
- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers (Hermes provider controls)
- https://hermes-agent.nousresearch.com/docs/llms.txt (Hermes docs index)
