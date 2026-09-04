# AGENTS.md

This repository is a comprehensive **chezmoi** dotfiles management project targeting multiple platforms (primarily Windows and Linux/Termux), containing extensive templates (`.tmpl`), custom Ansible playbooks, Scoop custom buckets, and configuration profiles for numerous editors, shells, window managers, and utility tools.

## Essential Commands

- **Apply dotfiles**: `chezmoi apply`
- **Diff local state against source**: `chezmoi diff`
- **Managed status**: `chezmoi status`
- **Initialize/Update repo**: `chezmoi init` or `chezmoi update`

## Code Organization & Structure

- Root directory contains standard chezmoi dotfile sources where filenames starting with `dot_` map to hidden dotfiles (e.g., `dot_bashrc.tmpl` -> `~/.bashrc`), and template files use Go template syntax (`.tmpl`).
- `.chezmoidata/`: Structured metadata and configuration data (e.g., Scoop packages lists).
- `.chezmoiscripts/`: Lifecycle scripts (pre/post run scripts, setup scripts like `run_onchange_*.ps1.tmpl` or `.sh.tmpl`).
- `.chezmoitemplates/`: Shared snippet templates included across multiple files.
- `private_dot_config/`, `AppData/`, `dot_local/`: Platform-specific configuration hierarchies mapped via chezmoi.
- `scoop/buckets/`: Custom Scoop app manifests.
- `Documents/ansible_playbooks/`: Ansible automation roles and playbooks for system bootstrap.

## Conventions & Patterns

- **Templates**: Heavy usage of Go templates (`{{ .chezmoi.os }}`, `{{ output ... }}`) to maintain cross-platform dotfiles for Windows, Linux, and Termux.
- **On-Change Scripts**: Scripts prefixed with `run_onchange_` automatically re-execute when their content hash changes (useful for dependency installations, tool setups, and config reloads).
- **Secrets Management**: Integration with `gopass` and encrypted keys via `.git-crypt`.

## Gotchas

- Files and directories use chezmoi's specific prefix naming conventions (`dot_`, `private_`, `executable_`, `.tmpl`). Always respect these prefixes when adding or renaming configuration files.
- Modifying files directly in the home directory will get overwritten by `chezmoi apply`; edit the sources inside this repository instead.
