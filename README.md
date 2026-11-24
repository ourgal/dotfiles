<div align="center">

# Dotfiles

[![chezmoi](https://img.shields.io/badge/managed%20by-chezmoi-5A45FF)](https://www.chezmoi.io/)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20Termux%20%7C%20macOS-lightgrey)](#supported-platforms)
[![nvfetcher](https://github.com/ourgal/dotfiles/actions/workflows/nvfetcher.yaml/badge.svg)](.github/workflows/nvfetcher.yaml)

Cross-platform dotfiles, dotfile-driven automation, and pinned package sources in one repo.

[Overview](#overview) • [Repository layout](#repository-layout) • [Getting started](#getting-started) • [Configuration](#configuration) • [Commands](#commands) • [Bootstrap automation](#bootstrap-automation) • [Secrets](#secrets) • [Making changes](#making-changes)

</div>

## Overview

Everything here is a [chezmoi](https://www.chezmoi.io/) source file. One repo renders shell/rc files, editor and terminal configs, window-manager themes, tiling-WM stacks, Scoop manifests, and per-OS Ansible bootstrap playbooks for Windows, Linux/Termux, WSL, and macOS.

Highlights:

- **One source of truth** — Go templates branch on `.chezmoi.os`, `lookPath`, and `[my.*]` data keys instead of forking configs per machine.
- **Declarative config model** — fonts, git identity, proxies, shell integrations, WM theme, and startup services are TOML switches in `.chezmoidata/`.
- **Lifecycle automation** — `run_onchange_*` scripts install fonts, register apps, deploy plugins, and seed databases; scripts re-run when their hashed inputs change.
- **Bootstrap playbooks** — self-contained Ansible projects per OS, driven by roles and SOPS-encrypted variables.
- **Reproducible pins** — `nvfetcher.toml` pins AUR `*-bin` release archives; a scheduled GitHub Action refreshes `_sources/`.
- **Secrets at rest** — age-encrypted chezmoi secrets, gopass templates, and SOPS for Ansible; no plaintext credentials in the repo.

## Supported platforms

| Platform | Notes |
| --- | --- |
| Windows | PowerShell pwsh + Clink, Shell/taskbar/WM integration, Scoop bucket and persisted app config |
| Arch / Debian / Void / Alpine / easyOS | Linux desktops (Qtile, Awesome, kitty, picom, PipeWire, ...), plus live variants |
| Termux / Android | Mobile shell, mpv plugins, awesome-copycats |
| WSL (Arch / Debian), UOS, Omarchy, NixOS | Dedicated Ansible playbooks |
| macOS | Bootstrap playbook; chezmoi targets gated by `lookPath` |

## Repository layout

| Path | Purpose |
| --- | --- |
| `home/` | chezmoi source directory (selected by `.chezmoiroot`) |
| `home/.chezmoidata/` | `[my.*]` toggles (`main.toml`) and Windows theme palettes (`themes.toml`) |
| `home/.chezmoitemplates/` | shared template snippets included across configs |
| `home/.chezmoiscripts/` | `run_onchange_before_*` / `after_*` lifecycle scripts |
| `home/.chezmoiexternals/main.toml.tmpl` | pinned git externals for plugins, themes, and fonts |
| `home/.chezmoiignore.tmpl` | whitelist gate — nothing is managed until listed here |
| `home/private_dot_config/` | `~/.config` application configs |
| `home/AppData/`, `home/scoop/` | Windows targets and Scoop bucket + persisted app config |
| `home/dot_agents/`, `dot_claude/`, `dot_codex/`, `dot_omp/`, `private_dot_hermes/` | agent configs and shared skill templates |
| `home/Documents/ansible_playbooks/<os>/` | per-OS Ansible bootstrap projects |
| `nvfetcher.toml`, `_sources/` | pinned source metadata and generated Nix expressions |
| `.github/workflows/nvfetcher.yaml` | nightly nvfetcher refresh + auto-commit |

## Getting started

Prerequisites: [chezmoi](https://www.chezmoi.io/docs/install/), Git, and [age](https://age-encryption.org/) (for secrets). Ansible is only needed for the bootstrap playbooks.

```bash
chezmoi init git@github.com:ourgal/dotfiles
chezmoi diff                 # review before writing anything
chezmoi apply --refresh-externals --force
```

Or, once the source repo is already wired up:

```bash
make all                     # config + ssh-keys + chezmoi apply
```

> [!IMPORTANT]
> Bootstrap needs the age identity at `~/.config/age/chezmoi.key`. `make all` creates `~/.config/chezmoi/chezmoi.toml` and the SSH keypair on first run; keep the age key safe, since `secrets.toml.age` cannot decrypt without it.

> [!NOTE]
> `chezmoi apply` gates every target through `.chezmoiignore.tmpl`. A new source file is inert until a matching `!path` rule exists there.

## Configuration

All knobs live in `home/.chezmoidata/main.toml`. Templates read them as `.my.*`; module toggles are booleans and feature lists are arrays.

```toml
[my.modules.windows]
theme = "rose-pine"          # rose-pine | kanagawa | seelen

[my.modules.windows.startup]
aria2.enable = true
chromium.enable = true
vscode.enable = false

[my.modules.shell.bash]
fzf.enable = true
starship.enable = true
zoxide.enable = true
```

The Windows theme selects a palette and a startup component list from `themes.toml`, shared by YASB, WHKD, GlazeWM/Komorebi, and tacky-borders:

| `theme` | Window manager | Startup components |
| --- | --- | --- |
| `rose-pine` | GlazeWM | glazewm, whkd, yasb |
| `kanagawa` | Komorebi | komorebi, whkd, yasb |
| `seelen` | Seelen UI | seelen_ui |

Fonts, git identity, proxy/mirror URLs, mpv and tmux plugins, browser theme, and host-specific overrides follow the same pattern.

## Commands

| Command | Effect |
| --- | --- |
| `make all` | apply `chezmoi.toml` + SSH keys, then `chezmoi apply` |
| `make config` | apply only `~/.config/chezmoi/chezmoi.toml` |
| `chezmoi diff` | preview pending target changes |
| `chezmoi status` | list pending changes |
| `chezmoi cat ~/.bashrc` | render one target without writing it |
| `chezmoi execute-template '{{ lookPath "foo" }}'` | test a template expression |
| `chezmoi data` | inspect `.my.*` and `.chezmoi.*` values |
| `chezmoi init` / `chezmoi update` | initialize / pull + apply |
| `chezmoi apply --refresh-externals --force` | re-fetch externals and apply without prompts |

Inside an Ansible playbook directory: `make` runs the playbook, `make lint` runs ansible-lint, `make install` installs Galaxy collections, and tags are passed as goals (e.g. `make all docker`).

## Bootstrap automation

`home/Documents/ansible_playbooks/` holds independent projects: `inventory/hosts.yml`, `playbooks/main.yml`, `roles/`, `requirements.yml`, `lookup_plugins/gopass.py`, and a `Makefile.tmpl` generated from the shared `ansible_playbook_makefile` template.

Available targets: `windows`, `arch`, `wsl-arch`, `debian`, `wsl-debian`, `debian-live`, `alpine`, `void`, `void-live`, `easyos`, `termux`, `uos`, `uos-live`, `nixos-uos-arm`, `omarchy`, `macos`.

Windows package installation is centralized in the `windows_scoop` role; `home/scoop/buckets/mygames/bucket` holds hand-written game manifests. Arch `*-bin` replacements come from nvfetcher pins in `nvfetcher.toml`, refreshed nightly by the GitHub Action and materialized in `_sources/`.

## Secrets

Three independent schemes, all encrypted at rest:

- **chezmoi** — `home/secrets.toml.age`, decrypted by `.chezmoitemplates/secrets` (`include ... | decrypt`) with the age identity above; individual files use `encrypted_` sources.
- **gopass** — `.chezmoitemplates/gopass` and `gopassRaw` for values pulled from a pass store.
- **Ansible** — SOPS via `community.sops`, reading `SOPS_AGE_KEY_FILE=~/.config/age/ansible.key`, exported by the shared playbook Makefile template.

> [!WARNING]
> Never commit decrypted secrets or keyfiles. `.gitignore` already excludes `keyfile.toml` and `.env`.

## Making changes

1. Edit sources under `home/`, never the rendered files in `$HOME` — `chezmoi apply` overwrites them.
2. Respect chezmoi prefixes: `dot_`, `private_`, `executable_`, `readonly_`, `symlink_`, `.tmpl`, `encrypted_`, `modify_`.
3. Add a `!path` rule to `.chezmoiignore.tmpl` for any new target; use `lookPath`/`.chezmoi.os` guards where appropriate.
4. Verify with `chezmoi cat <target>` and `chezmoi diff` before applying.
5. For a `run_onchange_*` script that consumes files, embed `# {{ include . | sha256sum }}` over those inputs so the script hash — and therefore its re-run — tracks them.

> [!TIP]
> On-change scripts are numbered: `run_onchange_before_NN_*` runs before the apply, `run_onchange_after_NN_*` after. The number sets execution order.
