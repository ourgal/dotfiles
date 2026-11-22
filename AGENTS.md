# AGENTS.md

This repository is a comprehensive **chezmoi** dotfiles management project targeting multiple platforms (primarily Windows and Linux/Termux), containing extensive templates (`.tmpl`), custom Ansible playbooks, Scoop custom buckets, and configuration profiles for numerous editors, shells, window managers, and utility tools.

## Essential Commands

```bash
make all                      # chezmoi apply
make config                   # apply only ~/.config/chezmoi/chezmoi.toml
chezmoi apply --refresh-externals --force   # refresh externals, skip prompts
chezmoi diff                  # preview targets that differ from source
chezmoi status                # pending changes
chezmoi cat ~/.bashrc         # render one target without writing it
chezmoi execute-template '{{ lookPath "foo" }}'   # test a template snippet
chezmoi data                  # inspect .my.* / .chezmoi.* values
chezmoi init | chezmoi update # initialize / pull + apply
```

There is no build step and no test suite. Verification is rendering the affected targets with `chezmoi cat <target>` and reviewing `chezmoi diff`; a template that fails to execute surfaces there (or via `chezmoi execute-template`).

## Code Organization & Structure

`.chezmoiroot` contains `home`, so chezmoi's source dir is **`home/`** — every dotfile source lives there. The repo root only holds `Makefile`, `AGENTS.md`, `.chezmoiroot`, and agent tool directories.

- `home/`: dotfile sources using chezmoi's naming conventions (`dot_bashrc.tmpl` -> `~/.bashrc`).
- `home/.chezmoidata/`: `main.toml` (all `[my.*]` knobs) and `themes.toml` (Windows themes).
- `home/.chezmoiscripts/`: lifecycle scripts, `run_onchange_before_NN_*` and `run_onchange_after_NN_*`.
- `home/.chezmoitemplates/`: shared snippets pulled in via `includeTemplate`.
- `home/.chezmoiexternals/main.toml.tmpl`: git-repo externals (not `.chezmoiexternal.toml`).
- `home/private_dot_config/`, `home/AppData/`, `home/dot_local/`: platform-specific configuration trees.
- `home/scoop/buckets/mygames/bucket`: hand-written games manifests. Most packages come from Ansible's `windows_scoop` role, not from this bucket.
- `home/Documents/ansible_playbooks/<os>/`: per-OS Ansible automation for bootstrap.

## Configuration Model

`[my.*]` in `home/.chezmoidata/main.toml` drives nearly every template: fonts, git identity, GPG/SSH signing, proxies and mirrors, `secrets_filename`, and `[my.modules.windows.startup]` toggles per component (aria2, transmission, glazewm, vscode, ...).

Windows window-manager selection is a single switch: `[my.modules.windows].theme` selects an entry in `home/.chezmoidata/themes.toml` — `rose-pine` -> GlazeWM, `kanagawa` -> Komorebi, `seelen` -> Seelen UI — which supplies the palette (`background`, `surface`, `text`, ...) and a `startup` component list. Templates read it as `index .my.themes .my.modules.windows.theme`, e.g. `home/private_dot_config/yasb/config.yaml.tmpl:1`, `home/private_dot_config/whkdrc.tmpl:1`, `home/private_dot_config/tacky-borders/config.yaml.tmpl:1`.

## Conventions & Patterns

- **Templates**: Heavy usage of Go templates (`{{ .chezmoi.os }}`, `{{ lookPath ... }}`, `{{ output ... }}`) to maintain cross-platform dotfiles for Windows, Linux, and Termux.
- **Ignore gate**: `home/.chezmoiignore.tmpl` starts with `*` and whitelists every target individually, usually behind `lookPath`/`stat` guards. A new source file produces no target until a matching `!path` rule is added — otherwise it silently does nothing. `Documents/` is excluded by default; only explicitly whitelisted subtrees are managed (`share`, `scripts`, `doc`, `easyos`, `browser_extensions`, `ansible_playbooks`, `PowerToys`, `game_saves`, `ventoy`).
- **On-Change Scripts**: scripts re-execute when their content hash changes. Numbering sets order and phase: `run_onchange_before_NN_*` runs before the apply, `run_onchange_after_NN_*` after.
- **Script input hashing**: many scripts embed `# {{ include . | sha256sum }}` over the files they consume (e.g. `run_onchange_after_31_install_windows_user_fonts.ps1.tmpl`) so the script hash changes — and the script re-runs — when those inputs change, without editing the script itself.
- **Externals**: `home/.chezmoiexternals/main.toml.tmpl` pins git repos with `refreshPeriod` (mpv scripts, clink plugins, awesome-copycats, ...) under `~/.local/share/repos`.

## Secrets Management

Two independent schemes:

- **chezmoi / dotfiles**: age-encrypted `home/secrets.toml.age` decrypted through `.chezmoitemplates/secrets` (`include ... | decrypt`), plus individual `encrypted_` sources (e.g. buku's `db.py`). `gopass` templates also exist in `.chezmoitemplates/gopass` and `gopassRaw`.
- **Ansible**: SOPS via `community.sops`, reading `SOPS_AGE_KEY_FILE=~/.config/age/ansible.key` (exported by `.chezmoitemplates/ansible_playbook_makefile`).

## Ansible

Each `home/Documents/ansible_playbooks/<os>/` (`windows`, `arch`, `debian`, `void`, `termux`, `wsl-arch`, ...) is self-contained: `inventory/hosts.yml`, `playbooks/main.yml`, `roles/`, `requirements.yml`, `lookup_plugins/gopass.py`, and a `Makefile.tmpl` that is just `{{ includeTemplate "ansible_playbook_makefile" . }}`.

Inside a playbook dir: `make` (playbook only), `make lint` (ansible-lint), `make install` (galaxy collections), and tags are passed as make goals (`make all docker`). Windows roles are `windows_*` (`windows_scoop`, `windows_service`, `windows_user`, ...).

## Gotchas

- Respect chezmoi's prefix conventions when adding or renaming configuration files: `dot_`, `private_`, `executable_`, `readonly_` (seen on `AppData/Roaming/Microsoft/Windows/readonly_Start Menu`), `symlink_` (`symlink_dot_tmux.conf`), `.tmpl`, `encrypted_`, `modify_`.
- `.chezmoiremove` is parsed as a template even without the `.tmpl` extension.
- Modifying files directly in the home directory gets overwritten by `chezmoi apply`; edit the sources under `home/` instead.