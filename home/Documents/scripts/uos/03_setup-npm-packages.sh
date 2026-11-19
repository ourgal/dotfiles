#!/usr/bin/env bash
#
# 03_setup-npm-packages.sh — install global npm packages into the Miniforge base
# environment.
#
# npm comes from the conda-forge nodejs package, so global installs land under
# the Miniforge prefix ($HOME/miniforge3) without needing sudo.
#
# Usage: ./03_setup-npm-packages.sh [--prefix DIR] [--dry-run]
#
#   --prefix DIR   Miniforge root (default: $HOME/miniforge3)
#   --dry-run      print the commands; change nothing
#   -h, --help     show this help
#
set -euo pipefail

PREFIX="${MINIFORGE_DIR:-$HOME/miniforge3}"
DRY_RUN=0
PACKAGES=("@tencent-ai/codebuddy-code")
BINS=(cbc codebuddy)

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m [!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m [x]\033[0m %s\n' "$*" >&2; exit 1; }
run()  { if (( DRY_RUN )); then printf '       DRY: %s\n' "$*"; else "$@"; fi; }

usage() { sed -n '9,13p' "$0"; }

while (( $# )); do
  case "$1" in
    --prefix)  PREFIX="${2:?--prefix needs a path}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

[[ -x "$PREFIX/bin/npm" && -x "$PREFIX/bin/node" ]] \
  || die "npm/node not found in $PREFIX/bin; run 01_setup-miniforge.sh and 02_setup-miniforge-packages.sh first"

log "installing ${PACKAGES[*]} globally into $PREFIX"
run "$PREFIX/bin/npm" install -g --no-fund --no-audit "${PACKAGES[@]}"

if (( DRY_RUN )); then
  warn "dry run: nothing was installed"
  exit 0
fi

log "verification"
"$PREFIX/bin/npm" ls -g --depth=0 2>/dev/null | sed 's/^/       /'
for cmd in "${BINS[@]}"; do
  [[ -x "$PREFIX/bin/$cmd" ]] || warn "$cmd not found in $PREFIX/bin"
done

cat <<EOF

Next steps
  - The codebuddy binaries live in $PREFIX/bin, which bashrc puts on PATH.
  - In an existing shell, refresh the command cache with:  hash -r
EOF
