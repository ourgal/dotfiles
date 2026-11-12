#!/usr/bin/env bash
#
# setup-miniforge.sh — install Miniforge (conda-forge) for the current user on UOS
# Desktop 20 (eagle / arm64) or any glibc >= 2.17 Linux.
#
# Why Miniforge: it is the conda-forge distribution. Only the conda-forge channel is
# preconfigured, so there is no Anaconda defaults channel (and none of the ToS or
# rate limits that come with it), and its aarch64 installer only needs glibc 2.17+
# whereas Anaconda/Miniconda arm64 builds assume newer bases. Miniforge also bundles
# mamba, which resolves the environment much faster than conda on arm64.
#
# The install is user-level: everything lands under $HOME/miniforge3 and nothing
# outside $HOME is written, so this needs no sudo and no UOS 开发者模式. Re-running
# the script is safe; an existing prefix is left alone unless --force / --update.
#
# Shell setup is opt-in (--init) because ~/.bashrc here is managed by chezmoi: a
# block written by `conda init` would vanish on the next `chezmoi apply` unless the
# same block is added to the dotfile source (home/dot_bashrc, home/dot_bashrc.tmpl).
#
# Usage: ./setup-miniforge.sh [options]
#   --prefix DIR       install location (default: $HOME/miniforge3)
#   --version VER      Miniforge release to install (default: latest, e.g. 26.9.4-2)
#   --mirror M         auto | tuna | github   (default: auto = tuna, then github)
#   --proxy URL        HTTP(S) proxy for downloads, e.g. http://192.168.0.101:7890
#   --init             run `conda init` for bash and zsh (also edits their rc files)
#   --update           update an existing install in place, then exit
#   --force            delete an existing Miniforge prefix and reinstall it
#   --dry-run          print what would happen; change nothing
#   -h, --help         show this help
#
set -euo pipefail

INSTALL_DIR="${MINIFORGE_DIR:-$HOME/miniforge3}"
VERSION=""
MIRROR="auto"
PROXY="${https_proxy:-${HTTPS_PROXY:-}}"
INIT=0
UPDATE=0
FORCE=0
DRY_RUN=0

TUNA_BASE="https://mirrors.tuna.tsinghua.edu.cn/github-release/conda-forge/miniforge/LatestRelease"
GITHUB_RELEASES="https://github.com/conda-forge/miniforge/releases"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/miniforge-setup"

# ---------------------------------------------------------------- helpers
log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m [!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m [x]\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if (( DRY_RUN )); then printf '       DRY: %s\n' "$*"; else "$@"; fi
}

curl_it() { # curl with the optional proxy applied
  if [[ -n "$PROXY" ]]; then curl --proxy "$PROXY" "$@"; else curl "$@"; fi
}

usage() { sed -n '20,29p' "$0"; }

# --------------------------------------------------------------- usage
while (( $# )); do
  case "$1" in
    --prefix)  INSTALL_DIR="${2:?--prefix needs a path}"; shift ;;
    --version) VERSION="${2:?--version needs a release, e.g. 26.9.4-2}"; shift ;;
    --mirror)  MIRROR="${2:?--mirror needs auto, tuna or github}"; shift ;;
    --proxy)   PROXY="${2:?--proxy needs a URL, e.g. http://192.168.0.101:7890}"; shift ;;
    --init)    INIT=1 ;;
    --update)  UPDATE=1 ;;
    --force)   FORCE=1 ;;
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

[[ "$INSTALL_DIR" == /* ]] || die "--prefix must be an absolute path: $INSTALL_DIR"
[[ -n "$PROXY" ]] && log "using proxy $PROXY"

# --------------------------------------------------------------- preflight
detect_arch() {
  case "$(uname -m)" in
    aarch64|arm64) ARCH=aarch64 ;;
    x86_64|amd64)  ARCH=x86_64 ;;
    ppc64le)       ARCH=ppc64le ;;
    riscv64)       ARCH=riscv64 ;;
    s390x)         ARCH=s390x ;;
    *) die "unsupported architecture: $(uname -m)" ;;
  esac
}

preflight() {
  log "Preflight checks"
  [[ "$(uname -s)" == Linux ]] || die "this script is for Linux only"
  # Termux is Android, not glibc; conda's prebuilt binaries do not run there.
  [[ ! -d /data/data/com.termux ]] || die "Termux detected: conda cannot run here (no glibc)"

  detect_arch
  command -v curl >/dev/null || die "curl not found"
  command -v sha256sum >/dev/null || die "sha256sum not found (coreutils)"

  if (( EUID == 0 )); then
    warn "running as root: Miniforge will be installed under $HOME, owned by root"
  fi

  local parent avail_kb
  parent=$(dirname "$INSTALL_DIR")
  [[ -d "$parent" ]] || parent="$HOME"
  avail_kb=$(df -Pk "$parent" | awk 'NR==2 {print $4}')
  if [[ -n "$avail_kb" ]] && (( avail_kb < 2 * 1024 * 1024 )); then
    warn "less than 2 GiB free under $parent; the install plus its package cache needs about that much"
  fi
  log "architecture: $ARCH"
}

# ----------------------------------------------------------- release lookup
latest_version() {
  local eff listing f
  # GitHub's releases/latest redirect is the cheapest way to learn the tag.
  eff=$(curl_it -fsSL -o /dev/null -w '%{url_effective}' --max-time 30 \
          "$GITHUB_RELEASES/latest" 2>/dev/null || true)
  if [[ "$eff" == */tag/* ]]; then
    printf '%s\n' "${eff##*/tag/}"
    return 0
  fi
  # Fallback: the TUNA mirror lists every versioned installer in the directory.
  listing=$(curl_it -fsSL --max-time 30 "$TUNA_BASE/" 2>/dev/null || true)
  f=$(printf '%s\n' "$listing" \
      | grep -oE "Miniforge3-[0-9][^\"<>]*-Linux-${ARCH}\.sh" \
      | sort -Vu | tail -1 || true)
  [[ -n "$f" ]] || return 1
  f=${f#Miniforge3-}
  printf '%s\n' "${f%-Linux-$ARCH.sh}"
}

installer_name() {
  if [[ -n "$VERSION" ]]; then
    printf 'Miniforge3-%s-Linux-%s.sh\n' "$VERSION" "$ARCH"
  else
    printf 'Miniforge3-Linux-%s.sh\n' "$ARCH"
  fi
}

set_base_urls() {
  if [[ -n "$VERSION" ]]; then
    GITHUB_BASE="$GITHUB_RELEASES/download/$VERSION"
  else
    GITHUB_BASE="$GITHUB_RELEASES/latest/download"
  fi
}

fetch() { # <filename> <destination>
  local m url
  for m in "${MIRRORS[@]}"; do
    case "$m" in
      tuna)   url="$TUNA_BASE/$1" ;;
      github) url="$GITHUB_BASE/$1" ;;
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

# ------------------------------------------------------------- shell setup
init_shell() {
  local sh
  warn "conda init edits ~/.bashrc / ~/.zshrc; chezmoi apply will revert those"
  warn "edits unless the same block is added to the dotfile source in this repo"
  for sh in bash zsh; do
    command -v "$sh" >/dev/null 2>&1 \
      && run "$INSTALL_DIR/bin/conda" init "$sh"
  done
}

verify() {
  local v
  v=$("$INSTALL_DIR/bin/conda" --version) || die "installed conda does not run"
  log "$v | $("$INSTALL_DIR/bin/python" -V 2>&1)"
  if [[ -x "$INSTALL_DIR/bin/mamba" ]]; then log "mamba is bundled"; fi
  log "base prefix: $("$INSTALL_DIR/bin/conda" info --base)"
}

next_steps() {
  cat <<EOF

Next steps
  1. Activate conda in this shell:
       source "$INSTALL_DIR/etc/profile.d/conda.sh"
       conda activate base
     (or open a new login shell after --init)
  2. Expect only the conda-forge channel:
       conda config --show channels
  3. Create environments normally, e.g.:
       conda create -n py311 python=3.11 -y
  4. Uninstall: remove the conda block from your rc files (if any) and
       rm -rf "$INSTALL_DIR" "$CACHE_DIR"
EOF
}

# --------------------------------------------------------------- main
preflight

if [[ -e "$INSTALL_DIR" ]]; then
  [[ -x "$INSTALL_DIR/bin/conda" ]] \
    || die "$INSTALL_DIR exists but is not a conda prefix; pick another --prefix or remove it yourself"

  if (( FORCE )); then
    # Only delete a directory we can positively identify as a conda prefix.
    [[ -d "$INSTALL_DIR/conda-meta" ]] \
      || die "refusing to delete $INSTALL_DIR: no conda-meta directory"
    warn "removing existing Miniforge at $INSTALL_DIR (--force)"
    run rm -rf "$INSTALL_DIR"
  elif (( UPDATE )); then
    log "updating the base environment in $INSTALL_DIR"
    if (( DRY_RUN )); then
      printf '       DRY: %s\n' "$INSTALL_DIR/bin/conda update -n base --all -y"
      exit 0
    fi
    "$INSTALL_DIR/bin/conda" update -n base --all -y
    verify
    exit 0
  else
    log "Miniforge already installed at $INSTALL_DIR"
    verify
    (( INIT )) && init_shell
    next_steps
    exit 0
  fi
fi

if [[ -z "$VERSION" ]]; then
  if VERSION=$(latest_version); then
    log "latest Miniforge release: $VERSION"
  else
    warn "could not determine the latest release; falling back to the unversioned installer"
    VERSION=""
  fi
fi
set_base_urls

INSTALLER=$(installer_name)
log "installer: $INSTALLER"

if (( DRY_RUN )); then
  printf '       DRY: download %s into %s and run "bash <installer> -b -p %s"\n' \
    "$INSTALLER" "$CACHE_DIR" "$INSTALL_DIR"
  exit 0
fi

mkdir -p "$CACHE_DIR" "$(dirname "$INSTALL_DIR")"
installer="$CACHE_DIR/$INSTALLER"

if [[ -s "$installer" ]]; then
  log "using cached $INSTALLER"
else
  fetch "$INSTALLER" "$installer" || die "could not download $INSTALLER from any mirror"
fi
verify_checksum "$installer"

log "installing Miniforge into $INSTALL_DIR (batch mode, rc files untouched)"
bash "$installer" -b -p "$INSTALL_DIR" || die "installer failed"
hash -r 2>/dev/null || true

verify
(( INIT )) && init_shell

if command -v conda >/dev/null 2>&1; then
  case "$(command -v conda)" in
    "$INSTALL_DIR"/bin/conda) ;;
    *) warn "conda on PATH resolves to $(command -v conda), not $INSTALL_DIR; run: hash -r" ;;
  esac
fi

next_steps
