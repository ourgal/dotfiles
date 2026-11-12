#!/usr/bin/env bash
#
# setup-miniforge-python.sh — minimal UOS bootstrap: install Miniforge only,
# then install Python through that Miniforge.
#
# Why this exists: 01_setup-miniforge.sh + 02_setup-miniforge-packages.sh set up
# a full workstation (git, nodejs, chezmoi, tmux, ... and remove distro packages
# with sudo). Some boxes only need a conda-forge Python. This script does two
# things and nothing else:
#   1. install Miniforge (conda-forge) into $HOME/miniforge3 in batch mode —
#      no `conda init`, no rc file edits, no sudo, no apt changes;
#   2. `mamba install -n base python` from conda-forge.
# Everything stays under $HOME, so no root and no UOS 开发者模式 are needed.
#
# Miniforge's base already ships a conda-forge Python; step 2 keeps it current
# (or pins a version with --python). Pinning base Python changes the interpreter
# conda itself uses, so prefer a separate env for non-default versions.
#
# The installer is fetched from TUNA (fallback: GitHub releases) and its
# published sha256 is checked before running it. Re-running is safe: an
# existing prefix is left alone and already-installed packages are untouched.
#
# Usage: ./setup-miniforge-python.sh [options]
#   --prefix DIR    install location (default: $HOME/miniforge3)
#   --python SPEC   conda spec for Python (default: python), e.g. python=3.12
#                   or just 3.12
#   --version VER   Miniforge release (default: latest, e.g. 26.9.4-2)
#   --mirror M      auto | tuna | github   (default: auto = tuna, then github)
#   --proxy URL     HTTP(S) proxy for downloads, e.g. http://192.168.0.101:7890
#   --dry-run       print what would happen; change nothing
#   -h, --help      show this help
#
set -euo pipefail

PREFIX="${MINIFORGE_DIR:-$HOME/miniforge3}"
PYTHON_SPEC="python"
VERSION=""
MIRROR="auto"
PROXY="${https_proxy:-${HTTPS_PROXY:-}}"
DRY_RUN=0

TUNA_BASE="https://mirrors.tuna.tsinghua.edu.cn/github-release/conda-forge/miniforge/LatestRelease"
GITHUB_RELEASES="https://github.com/conda-forge/miniforge/releases"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/miniforge-setup"

log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m [!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m [x]\033[0m %s\n' "$*" >&2; exit 1; }
curl_it() { if [[ -n "$PROXY" ]]; then curl --proxy "$PROXY" "$@"; else curl "$@"; fi; }
usage() { sed -n '/^# Usage:/,/^#   -h/p' "$0"; }

while (( $# )); do
  case "$1" in
    --prefix)  PREFIX="${2:?--prefix needs a path}"; shift ;;
    --python)  PYTHON_SPEC="${2:?--python needs a spec, e.g. python=3.12}"; shift ;;
    --version) VERSION="${2:?--version needs a release, e.g. 26.9.4-2}"; shift ;;
    --mirror)  MIRROR="${2:?--mirror needs auto, tuna or github}"; shift ;;
    --proxy)   PROXY="${2:?--proxy needs a URL}"; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

case "$MIRROR" in
  auto)   MIRRORS=(tuna github) ;;
  tuna)   MIRRORS=(tuna) ;;
  github) MIRRORS=(github) ;;
  *)      die "--mirror must be auto, tuna or github, got: $MIRROR" ;;
esac
[[ "$PREFIX" == /* ]] || die "--prefix must be an absolute path: $PREFIX"
# Convenience: `--python 3.12` means `python=3.12`.
case "$PYTHON_SPEC" in
  *=*|python*) ;;
  *) PYTHON_SPEC="python=$PYTHON_SPEC" ;;
esac
if [[ -n "$PROXY" ]]; then log "using proxy $PROXY"; fi

preflight() {
  log "Preflight checks"
  [[ "$(uname -s)" == Linux ]] || die "this script is for Linux only"
  # Termux is Android, not glibc; conda's prebuilt binaries do not run there.
  [[ ! -d /data/data/com.termux ]] || die "Termux detected: conda cannot run here (no glibc)"
  case "$(uname -m)" in
    aarch64|arm64) ARCH=aarch64 ;;
    x86_64|amd64)  ARCH=x86_64 ;;
    ppc64le)       ARCH=ppc64le ;;
    *) die "unsupported architecture: $(uname -m)" ;;
  esac
  command -v curl >/dev/null      || die "curl not found"
  command -v sha256sum >/dev/null || die "sha256sum not found (coreutils)"
  if (( EUID == 0 )); then
    warn "running as root: Miniforge will be installed under $HOME, owned by root"
  fi
  local parent avail_kb
  parent=$(dirname "$PREFIX")
  [[ -d "$parent" ]] || parent="$HOME"
  avail_kb=$(df -Pk "$parent" | awk 'NR==2 {print $4}')
  if [[ -n "$avail_kb" ]] && (( avail_kb < 2 * 1024 * 1024 )); then
    warn "less than 2 GiB free under $parent; the install plus package cache needs about that much"
  fi
  log "architecture: $ARCH"
}

# Resolve the latest tag from GitHub's redirect; fall back to the TUNA listing,
# which contains every versioned installer of the current release.
latest_version() {
  local eff listing f
  eff=$(curl_it -fsSL -o /dev/null -w '%{url_effective}' --max-time 30 \
          "$GITHUB_RELEASES/latest" 2>/dev/null || true)
  if [[ "$eff" == */tag/* ]]; then
    printf '%s\n' "${eff##*/tag/}"
    return 0
  fi
  listing=$(curl_it -fsSL --max-time 30 "$TUNA_BASE/" 2>/dev/null || true)
  f=$(printf '%s\n' "$listing" \
      | grep -oE "Miniforge3-[0-9][^\"<>]*-Linux-${ARCH}\.sh" \
      | sort -Vu | tail -1 || true)
  [[ -n "$f" ]] || return 1
  f=${f#Miniforge3-}
  printf '%s\n' "${f%-Linux-$ARCH.sh}"
}

fetch() { # <filename> <destination>
  local m url
  for m in "${MIRRORS[@]}"; do
    case "$m" in
      tuna)   url="$TUNA_BASE/$1" ;;
      github) if [[ -n "$VERSION" ]]; then url="$GITHUB_RELEASES/download/$VERSION/$1"
              else url="$GITHUB_RELEASES/latest/download/$1"; fi ;;
    esac
    log "downloading $url"
    if curl_it -fL --retry 3 --retry-delay 2 --max-time 1800 -o "$2" "$url"; then
      return 0
    fi
    rm -f "$2"
    warn "download failed from $m"
  done
  return 1
}

verify_checksum() { # <installer path>
  local f sum
  f=$(basename "$1")
  sum="$1.sha256"
  if [[ ! -s "$sum" ]]; then
    fetch "$f.sha256" "$sum" \
      || { warn "no checksum published for $f; skipping verification"; return 0; }
  fi
  # The published file lists "./<name>", so run the check from the cache dir.
  ( cd "$(dirname "$1")" && sha256sum -c --quiet "$(basename "$sum")" ) \
    || die "sha256 mismatch for $f"
  log "checksum verified"
}

# ------------------------------------------------------------------- main
preflight

if [[ -e "$PREFIX" ]]; then
  [[ -x "$PREFIX/bin/conda" ]] \
    || die "$PREFIX exists but is not a conda prefix; pick another --prefix or remove it yourself"
  log "Miniforge already installed at $PREFIX; leaving it as is"
  HAVE_MINIFORGE=1
else
  HAVE_MINIFORGE=0
fi

if [[ -z "$VERSION" && $HAVE_MINIFORGE -eq 0 ]]; then
  if VERSION=$(latest_version); then
    log "latest Miniforge release: $VERSION"
  else
    warn "could not determine the latest release; falling back to the unversioned installer"
    VERSION=""
  fi
fi

if [[ -n "$VERSION" ]]; then
  INSTALLER="Miniforge3-$VERSION-Linux-$ARCH.sh"
else
  INSTALLER="Miniforge3-Linux-$ARCH.sh"
fi
if [[ -x "$PREFIX/bin/mamba" ]]; then SOLVER="$PREFIX/bin/mamba"; else SOLVER="$PREFIX/bin/conda"; fi

if (( DRY_RUN )); then
  if (( ! HAVE_MINIFORGE )); then
    printf '       DRY: download %s into %s and run "bash %s -b -p %s"\n' \
      "$INSTALLER" "$CACHE_DIR" "$CACHE_DIR/$INSTALLER" "$PREFIX"
  fi
  printf '       DRY: %s install -n base -y -c conda-forge %s\n' "$SOLVER" "$PYTHON_SPEC"
  warn "dry run: nothing was installed"
  exit 0
fi

# ------------------------------------------------------------- step 1: Miniforge
if (( ! HAVE_MINIFORGE )); then
  mkdir -p "$CACHE_DIR" "$(dirname "$PREFIX")"
  installer="$CACHE_DIR/$INSTALLER"
  if [[ -s "$installer" ]]; then
    log "using cached $INSTALLER"
  else
    fetch "$INSTALLER" "$installer" || die "could not download $INSTALLER from any mirror"
  fi
  verify_checksum "$installer"
  log "installing Miniforge into $PREFIX (batch mode, rc files untouched)"
  bash "$installer" -b -p "$PREFIX" || die "installer failed"
  hash -r 2>/dev/null || true
  if [[ -x "$PREFIX/bin/mamba" ]]; then SOLVER="$PREFIX/bin/mamba"; fi
fi

# ------------------------------------------------------------- step 2: Python
[[ -x "$SOLVER" ]] || die "no conda/mamba in $PREFIX/bin; Miniforge install failed"
# The solver may shell out to other binaries in this prefix.
export PATH="$PREFIX/bin:$PATH"
log "installing $PYTHON_SPEC via Miniforge into the base environment"
"$SOLVER" install -n base -y -c conda-forge "$PYTHON_SPEC"

log "verification"
"$PREFIX/bin/conda" --version
"$PREFIX/bin/python" -V
log "python: $("$PREFIX/bin/python" -c 'import sys; print(sys.executable)')"

cat <<EOF

Next steps
  - No \`conda init\` was run: ~/.bashrc is managed by chezmoi, so a conda
    block written there would be reverted on the next \`chezmoi apply\`.
  - In this shell: source "$PREFIX/etc/profile.d/conda.sh" && conda activate base
  - In an already-open shell, refresh the command cache with:  hash -r
  - Uninstall: rm -rf "$PREFIX" "$CACHE_DIR"
EOF
