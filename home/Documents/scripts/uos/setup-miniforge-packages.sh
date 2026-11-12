#!/usr/bin/env bash
#
# setup-miniforge-packages.sh — install git, lazygit, chezmoi and nodejs from
# conda-forge into the Miniforge base environment.
#
# Why these come from conda-forge: the distro git has been removed on this UOS
# box, the repo scripts need git, and lazygit/chezmoi are not in the UOS repos.
# Node.js comes from here too, with npm bundled in the same package.
#
# The script removes distro git, nodejs and npm first so only the conda-forge
# builds remain; that step uses sudo, everything else stays in $HOME.
# Re-running is safe: already-installed packages are left as they are.
#
# Usage: ./setup-miniforge-packages.sh [--prefix DIR] [--dry-run]
#
#   --prefix DIR   Miniforge root (default: $HOME/miniforge3)
#   --dry-run      print the commands; change nothing
#   -h, --help     show this help
#
set -euo pipefail

PREFIX="${MINIFORGE_DIR:-$HOME/miniforge3}"
DRY_RUN=0
PACKAGES=(git lazygit chezmoi nodejs)
DISTRO_REMOVE=(git nodejs npm)
VERIFY_CMDS=(git lazygit chezmoi node npm)

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m [!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m [x]\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if (( DRY_RUN )); then printf '       DRY: %s\n' "$*"; else "$@"; fi; }

usage() { sed -n '14,18p' "$0"; }

while (( $# )); do
  case "$1" in
    --prefix)  PREFIX="${2:?--prefix needs a path}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

[[ -x "$PREFIX/bin/conda" ]] || die "Miniforge not found at $PREFIX; run setup-miniforge.sh first"

# mamba resolves conda-forge much faster; fall back to conda if it is absent.
if [[ -x "$PREFIX/bin/mamba" ]]; then SOLVER="$PREFIX/bin/mamba"; else SOLVER="$PREFIX/bin/conda"; fi

# The solver may shell out to binaries in this environment.
export PATH="$PREFIX/bin:$PATH"

# Duplicate toolchains on one box drift apart; keep only the conda-forge ones.
distro_installed=()
for pkg in "${DISTRO_REMOVE[@]}"; do
  if [[ "$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || true)" == "install ok installed" ]]; then
    distro_installed+=("$pkg")
  fi
done
if (( ${#distro_installed[@]} )); then
  command -v apt-get >/dev/null || die "apt-get not found; remove ${distro_installed[*]} manually"
  command -v sudo >/dev/null || die "sudo not found; remove ${distro_installed[*]} manually"
  log "removing distro packages: ${distro_installed[*]}"
  run sudo apt-get remove -y "${distro_installed[@]}"
else
  log "no distro git/nodejs/npm packages to remove"
fi

log "installing ${PACKAGES[*]} into the base environment ($PREFIX)"
run "$SOLVER" install -n base -y -c conda-forge "${PACKAGES[@]}"

if (( DRY_RUN )); then
  warn "dry run: nothing was installed"
  exit 0
fi

log "verification"
for cmd in "${VERIFY_CMDS[@]}"; do
  if [[ -x "$PREFIX/bin/$cmd" ]]; then
    log "$cmd: $("$PREFIX/bin/$cmd" --version 2>/dev/null | head -1)"
  else
    warn "$cmd not found in $PREFIX/bin"
  fi
done

cat <<EOF

Next steps
  - New shells pick these up automatically ($PREFIX/bin is prepended in bashrc).
  - In an existing shell, refresh the command cache with:  hash -r
EOF
