#!/usr/bin/env bash
#
# 04_setup-fcitx5.sh — build and enable Fcitx 5 from source on UOS Desktop 20 (eagle / arm64).
#
# Why a source build: the only fcitx5 in the UOS repos is a 2018 pre-release snapshot
# (0~20181128+ds1-1) that ships no input method at all, and Debian's fcitx5 5.x binary
# debs need glibc >= 2.31 while this base provides 2.28. So we compile a coherent
# fcitx5 5.0.x stack against this machine's gcc 8.3 / boost 1.67 / ICU 63.
#
# The Rime branch (on by default) adds librime 1.8.5 with the bundled librime-lua
# plugin, fcitx5-rime and the 声笔系列码 (sbsrf) schemas. The repo's librime is 1.4.0,
# which is both too old for sbsrf's lua scripts and has no rime-data package at all.
# Pass --no-rime / --no-sbsrf to skip those; --proxy is needed for the sbsrf download.
#
# The script is idempotent, records everything it touches for --rollback, and never
# stores a password. Run it as your normal user; it will prompt for sudo once.
#
set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
JOBS="${JOBS:-$(nproc)}"

# Filled in by discover_module_dirs once the -dev packages are installed.
GTK2_DIR=""
GTK3_DIR=""
QT5_DIR=""
STATE_DIR="$HOME/.local/share/fcitx5-setup"
BUILD_DIR="$STATE_DIR/build"
MANIFEST="$STATE_DIR/installed.manifest"
BACKUP_DIR="$STATE_DIR/fcitx4-backup"

DRY_RUN=0
ACTION="setup"
OPENCC=ON
RIME=ON
SBSRF=ON
# Set by install_sbsrf once rime_deployer has actually built the dictionaries.
SBSRF_DEPLOYED=0
ONLY=""
PROXY=""

MIRROR_PRIMARY="https://mirrors.tuna.tsinghua.edu.cn/debian/pool"
MIRROR_FALLBACK="https://deb.debian.org/debian/pool"

# Rime directories. RIME_SHARE_DIR is the read-only "shared data" dir that holds the
# stock Rime data (default.yaml, essay.txt, symbols.yaml) that every schema's config
# chain eventually refers back to; fcitx5-rime's user dir holds the live schemas.
# RIME_SHARE_DIR is derived after argument parsing, because --prefix can move PREFIX.
RIME_USER_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/fcitx5/rime"
# Where we synthesize a pkg-config name the librime-lua probe list understands.
PC_SHIM_DIR="$STATE_DIR/pkgconfig"

# ---------------------------------------------------------------- pinned stack
# Version set is deliberately the Debian 11 (bullseye) line: it is the newest
# release that still configures and compiles with gcc 8.3, boost 1.67, ICU 63
# and fmt 7.1.3. Do not bump individual entries on their own -- they are matched
# (chinese-addons 5.0.16 requires Fcitx5Core >= 5.0.11 and libime >= 1.0.13).
fmt_URL="main/f/fmtlib/fmtlib_7.1.3%2Bds1.orig.tar.gz"
imdkit_URL="main/x/xcb-imdkit/xcb-imdkit_1.0.9.orig.tar.xz"
fcitx5_URL="main/f/fcitx5/fcitx5_5.0.21.orig.tar.xz"
libime_URL="main/libi/libime/libime_1.0.16.orig.tar.xz"
gtk_URL="main/f/fcitx5-gtk/fcitx5-gtk_5.0.21.orig.tar.xz"
qt_URL="main/f/fcitx5-qt/fcitx5-qt_5.0.16.orig.tar.xz"
addons_URL="main/f/fcitx5-chinese-addons/fcitx5-chinese-addons_5.0.16.orig.tar.xz"
# Rime chain. opencc 1.1.9 because librime 1.8.5's simplifier.cc includes
# <opencc/Dict.hpp>, a header that only exists from OpenCC 1.1.0 -- the repo has 1.0.5.
# librime's Debian source ships the lua plugin as a second orig tarball.
opencc_URL="main/o/opencc/opencc_1.1.9%2Bds1.orig.tar.xz"
librime_URL="main/libr/librime/librime_1.8.5%2Bdfsg1.orig.tar.xz"
librime_lua_URL="main/libr/librime/librime_1.8.5%2Bdfsg1.orig-librime-lua.tar.xz"
rimefe_URL="main/f/fcitx5-rime/fcitx5-rime_5.0.15.orig.tar.xz"
# Not a Debian pool path: a GitHub release asset, so it needs --proxy on this host.
SBSRF_URL="https://github.com/sbsrf/sbsrf/releases/latest/download/sbsrf.zip"
# Set SBSRF_ZIP=/path/to/sbsrf.zip to install from a local copy instead of downloading.
SBSRF_ZIP="${SBSRF_ZIP:-}"

# Build order matters. fmt first because the repo's libfmt-dev (5.2.1) predates the
# API fcitx5 uses; we install fmt to $PREFIX and never apt-install libfmt-dev, so
# find_package(fmt) resolves to ours. xcb-imdkit next: the repo copy is a 2017
# snapshot and fcitx5 requires >= 1.0.3. opencc precedes addons/chinese-addons so
# that addons' FindOpenCC picks our 1.1.9 rather than the repo's 1.0.5, and librime
# precedes fcitx5-rime, which pkg-checks for rime >= 1.0.0.
BUILD_ORDER=(fmt imdkit fcitx5 libime opencc gtk qt addons librime rimefe)

# ---------------------------------------------------------------- helpers
log()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m [!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m [x]\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if (( DRY_RUN )); then printf '       DRY: %s\n' "$*"; else "$@"; fi
}

record() { # files/dirs we created, for rollback
  if (( DRY_RUN )); then printf '       DRY: record %s\n' "$*"
  else printf '%s\n' "$@" >> "$MANIFEST"; fi
}

record_file() { # a path rollback must delete again (not covered by install_manifest.txt)
  if (( DRY_RUN )); then printf '       DRY: record file %s\n' "$*"
  else printf 'installed=%s\n' "$@" >> "$MANIFEST"; fi
}

pkg_available() { apt-cache show "$1" >/dev/null 2>&1; }

in_build_set() {
  case " ${ONLY:-${BUILD_ORDER[*]}} " in
    *" $1 "*) return 0 ;;
  esac
  return 1
}

# --------------------------------------------------------------- usage
while (( $# )); do
  case "$1" in
    --dry-run)        DRY_RUN=1 ;;
    --rollback)       ACTION="rollback" ;;
    --preflight)      ACTION="preflight" ;;
    --no-opencc)      OPENCC=OFF ;;
    --no-rime)        RIME=OFF; SBSRF=OFF ;;
    --no-sbsrf)       SBSRF=OFF ;;
    --proxy)          PROXY="${2:?--proxy needs a URL, e.g. http://192.168.0.101:7890}"; shift ;;
    --only)           ONLY="${2:?--only needs a component list}"; shift ;;
    --prefix)         PREFIX="${2:?--prefix needs a path}"; shift ;;
    --jobs)           JOBS="${2:?--jobs needs a number}"; shift ;;
    -h|--help)        sed -n '1,17p' "$0"; exit 0 ;;
    *)                die "unknown argument: $1" ;;
  esac
  shift
done

if [[ -n "$PROXY" ]]; then
  export http_proxy="$PROXY" https_proxy="$PROXY" all_proxy="$PROXY"
  export HTTP_PROXY="$PROXY" HTTPS_PROXY="$PROXY" ALL_PROXY="$PROXY"
fi

RIME_SHARE_DIR="$PREFIX/share/rime-data"

# GNUInstallDirs resolves libdir to $PREFIX/lib/<multiarch> on Debian-derived systems
# because /usr/lib/<multiarch> exists, so that is where our .pc files actually land.
MULTIARCH=$(gcc -print-multiarch 2>/dev/null || echo "")
PKG_CONFIG_SEARCH="$PC_SHIM_DIR:$PREFIX/lib/pkgconfig"
if [[ -n "$MULTIARCH" ]]; then
  PKG_CONFIG_SEARCH="$PKG_CONFIG_SEARCH:$PREFIX/lib/$MULTIARCH/pkgconfig"
fi
export PKG_CONFIG_PATH="$PKG_CONFIG_SEARCH"

if [[ "$RIME" == OFF ]]; then
  # Trim the rime chain out of the default build order rather than teaching build()
  # about the flag, so --only keeps working unchanged.
  BUILD_ORDER=(fmt imdkit fcitx5 libime gtk qt addons)
fi

# --------------------------------------------------------------- preflight
preflight() {
  log "Preflight checks"

  [[ $EUID -ne 0 ]] || die "do not run as root; sudo is used where needed"
  (( $(nproc) >= 2 )) || warn "only $(nproc) cpu(s): this build will take a long time"

  command -v gcc >/dev/null || die "gcc not found"
  command -v sudo >/dev/null || die "sudo not found"

  local missing=() p want=("${REQUIRED_PKGS[@]}")
  if [[ "$RIME" == ON ]]; then want+=("${RIME_PKGS[@]}"); fi
  for p in "${want[@]}"; do
    pkg_available "$p" || missing+=("$p")
  done
  if ((${#missing[@]})); then
    die "these build deps are NOT in your repos: ${missing[*]}
     Without them the build will fail. Re-check the apt sources before running."
  fi

  # The 2018 snapshot packages ship CMake configs and Fcitx5* dev files in /usr/lib
  # that shadow what we install to $PREFIX. They must not be installed.
  local stale
  stale=$(dpkg-query -W -f='${Package} ${Version}\n' 'fcitx5*' 'libfcitx5*' 2>/dev/null \
          | awk '$2 ~ /^0~/ {print $1}' || true)
  if [[ -n "$stale" ]]; then
    warn "fcitx5 2018-snapshot packages present; install_deps removes them first:"
    printf '       %s\n' $stale
  fi

  # UOS blocks root filesystem writes until 开发者模式 is enabled, and that applies
  # to /usr/local too, so probe with a real write rather than a test -w.
  log "Checking write access to $PREFIX (UOS developer mode)"
  if (( DRY_RUN )); then
    printf '       DRY: sudo tee -a %s/.qoder-wtest\n' "$PREFIX"
  elif ! sudo tee -a "$PREFIX/.qoder-wtest" >/dev/null </dev/null; then
    die "cannot write to $PREFIX.
     UOS restricts root filesystem access outside 开发者模式.
     Enable it: 控制中心 -> 通用 -> 开发者模式 (requires reboot), then re-run."
  else
    run sudo rm -f "$PREFIX/.qoder-wtest"
  fi

  # Network: GitHub is blocked on this host, Debian mirrors are not.
  local ok=0
  for m in "$MIRROR_PRIMARY" "$MIRROR_FALLBACK"; do
    if curl -sS -o /dev/null --max-time 15 "$m/main/f/fcitx5/"; then ok=1; break; fi
  done
  (( ok )) || die "no Debian mirror reachable; cannot download sources"

  # sbsrf comes from a GitHub release asset, which this host cannot reach directly.
  # Only the asset URL is probed, with a byte range, so preflight stays fast. A cached
  # or user-supplied zip means no network access to GitHub is needed at all.
  if [[ "$SBSRF" == ON && -z "$SBSRF_ZIP" && ! -s "$STATE_DIR/sbsrf.zip" ]]; then
    if curl -fsS -o /dev/null --max-time 25 -r 0-1023 "$SBSRF_URL" \
       || curl -I -fsS -o /dev/null --max-time 25 "$SBSRF_URL"; then
      log "sbsrf release reachable${PROXY:+ through $PROXY}"
    else
      die "cannot reach $SBSRF_URL.
     GitHub is blocked on this network: pass --proxy http://<host>:<port>,
     drop --no-sbsrf to install the Rime engine without the 声笔 schemas, or
     point SBSRF_ZIP at a locally downloaded copy of sbsrf.zip."
    fi
  elif [[ "$SBSRF" == ON ]]; then
    log "sbsrf archive available locally; no GitHub access needed"
  fi

  log "Toolchain: $(gcc --version | head -1) | cmake will be installed via apt"
  log "Preflight passed"
}

# fcitx5's CMakeLists asks ECM's FindXCB for components XCB AUX XKB XFIXES ICCCM
# XINERAMA RANDR EWMH KEYSYMS, and FindXCB turns each into a pkg-config xcb-<lower>
# probe -- so every one needs its -dev package present or configure aborts. XFIXES in
# turn drags in xcb-shape/xcb-render. ENABLE_X11 additionally appends the X11 component
# to the REQUIRED XKBCommon lookup, hence libxkbcommon-x11-dev. libcurl is only needed
# by the chinese-addons cloud pinyin module, which we keep enabled. qtbase5-private-dev
# is not optional either: the Qt5 platform input context plugin includes
# <qpa/qplatforminputcontextplugin_p.h>, and without those headers moc cannot resolve
# QPlatformInputContextFactoryInterface_iid, so AUTOMOC dies with "Parse error at IID"
# before the compiler is even involved.
REQUIRED_PKGS=(
  g++ make cmake ninja-build pkg-config gettext git wget ca-certificates
  extra-cmake-modules libuv1-dev libsystemd-dev libdbus-1-dev dbus-x11
  libexpat1-dev libicu-dev libmarisa-dev libjson-c-dev zlib1g-dev libbrotli-dev
  libcurl4-openssl-dev
  libboost-dev libboost-iostreams-dev libboost-filesystem-dev libboost-regex-dev
  libxcb1-dev libxcb-ewmh-dev libxcb-icccm4-dev libxcb-randr0-dev
  libxcb-util0-dev libxcb-xkb-dev libxcb-xfixes0-dev libxcb-shm0-dev
  libxcb-keysyms1-dev libxcb-xinerama0-dev libxcb-shape0-dev uthash-dev
  libxkbcommon-dev libxkbcommon-x11-dev libxkbfile-dev libx11-dev xkb-data xcb-proto x11proto-dev
  libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libglib2.0-dev libgirepository1.0-dev
  libgtk-3-dev libgtk2.0-dev libgtk-3-bin libgtk2.0-bin qtbase5-dev qtbase5-dev-tools
  qtbase5-private-dev libqt5dbus5
  libenchant-2-dev libopencc-dev iso-codes shared-mime-info desktop-file-utils
)
# Extra build deps for the Rime branch: all verified present in the UOS repos except
# darts-clone, which opencc 1.1.9 only needs for the legacy .ocd format -- we build
# with ENABLE_DARTS=OFF. yaml-cpp 0.6.2 is enough: librime only uses Node/Emitter and
# as<>/size(), all present since 0.5.
RIME_PKGS=(
  libleveldb-dev libyaml-cpp-dev libgoogle-glog-dev libgflags-dev
  libboost-system-dev liblua5.3-dev python3
  rapidjson-dev libtclap-dev unzip
)
OPTIONAL_PKGS=(appstream librsvg2-dev libwayland-dev libxcb-imdkit0)

# --------------------------------------------------------------- apt deps
install_deps() {
  log "Installing build dependencies"
  local avail=() p want=("${REQUIRED_PKGS[@]}")
  if [[ "$RIME" == ON ]]; then want+=("${RIME_PKGS[@]}"); fi
  for p in "${want[@]}"; do pkg_available "$p" && avail+=("$p"); done
  for p in "${OPTIONAL_PKGS[@]}"; do pkg_available "$p" && avail+=("$p"); done

  run sudo apt-get update -qq || warn "apt-get update failed; continuing with cached index"
  run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${avail[@]}"

  # Never keep the 2018 snapshot or a competing system fmt: both put CMake config
  # files in /usr/lib that outrank $PREFIX.
  local stale
  stale=$(dpkg-query -W -f='${Package} ${Version}\n' 'fcitx5*' 'libfcitx5*' 2>/dev/null \
          | awk '$2 ~ /^0~/ {print $1}' || true)
  if [[ -n "$stale" ]]; then run sudo apt-get remove -y $stale; fi
  # fmt 5.2.1 ships /usr/lib/.../cmake/fmt/fmt-config.cmake, which find_package(fmt)
  # can prefer over our /usr/local fmt 7.
  if dpkg-query -W libfmt-dev >/dev/null 2>&1; then run sudo apt-get remove -y libfmt-dev; fi

  run sudo ldconfig
}

# --------------------------------------------------------- toolkit module dirs
# GTK and Qt only load input modules from the directories compiled into them, and
# this box's GTK3 uses the legacy .../gtk-3.0/3.0.0/immodules layout with an
# immodules.cache. Installing to $PREFIX would therefore drop the modules somewhere
# nothing scans, so these three builds are pointed at the live system directories.
# Derived from the installed packages rather than hardcoded, and run after
# install_deps so that qmake exists.
discover_module_dirs() {
  log "Locating toolkit module directories"
  GTK2_DIR=$(dpkg -L fcitx-frontend-gtk2 2>/dev/null \
             | grep -E '/immodules/im-fcitx\.so$' | head -1)
  GTK3_DIR=$(dpkg -L fcitx-frontend-gtk3 2>/dev/null \
             | grep -E '/immodules/im-fcitx\.so$' | head -1)
  QT5_DIR=$(qmake -query QT_INSTALL_PLUGINS 2>/dev/null || true)
  GTK2_DIR=${GTK2_DIR%/*}; GTK3_DIR=${GTK3_DIR%/*}

  [[ -d "$GTK2_DIR" ]] || GTK2_DIR=$(find /usr/lib -maxdepth 5 -type d \
        -path '*gtk-2.0*/immodules' 2>/dev/null | head -1)
  [[ -d "$GTK3_DIR" ]] || GTK3_DIR=$(find /usr/lib -maxdepth 5 -type d \
        -path '*gtk-3.0*/immodules' 2>/dev/null | head -1)
  [[ -d "$QT5_DIR" ]] || QT5_DIR=$(find /usr/lib -maxdepth 4 -type d \
        -path '*qt5*/plugins' 2>/dev/null | head -1)

  # Installing a module where no toolkit looks is worse than not installing it:
  # fcitx5 would run yet every app would keep using whatever IM it found before.
  local d
  for d in "$GTK2_DIR" "$GTK3_DIR" "$QT5_DIR"; do
    [[ -d "$d" ]] || die "could not locate a toolkit input-module directory
     (gtk2=$GTK2_DIR gtk3=$GTK3_DIR qt5=$QT5_DIR).
     Inspect libgtk-*-dev / qtbase5-dev and re-run."
  done
  log "gtk2=$GTK2_DIR"
  log "gtk3=$GTK3_DIR"
  log "qt5 =$QT5_DIR"
}

# --------------------------------------------------------------- build engine
download() { # <relpath> -> prints local path
  local rel="$1" name out
  # Separate declarations: bash creates all names in one `local` statement before
  # assigning any of them, so referencing $name on the same line trips `set -u`.
  name="$(basename "${rel//%2B/+}")"
  out="$STATE_DIR/dl/$name"
  mkdir -p "$STATE_DIR/dl"
  [[ -s "$out" ]] && { printf '%s\n' "$out"; return; }
  for m in "$MIRROR_PRIMARY" "$MIRROR_FALLBACK"; do
    if curl -fL --retry 2 --max-time 900 -o "$out" "$m/$rel"; then
      # -t with no compression flag: this stack mixes .gz and .xz tarballs.
      tar -tf "$out" >/dev/null 2>&1 || die "$name downloaded but is not a valid tarball"
      printf '%s\n' "$out"; return
    fi
    rm -f "$out"
  done
  die "could not download $rel from either mirror"
}

# build <component> <url> [--extra <url>@<subdir>]... <cmake-args...>
build() {
  local c="$1" url="$2"; shift 2
  local src="$STATE_DIR/src/$c" tarball extracted e
  local -a extras=() args=()
  while (($#)); do
    if [[ "$1" == --extra ]]; then
      shift; extras+=("${1:?--extra needs a url@subdir argument}")
    else
      args+=("$1")
    fi
    shift
  done

  if ! in_build_set "$c"; then log "skipping $c (not in --only)"; return; fi

  log "Building $c"
  mkdir -p "$src"
  tarball="$(download "$url")"
  extracted="$src/extracted"
  if [[ ! -d "$extracted" ]]; then
    mkdir -p "$extracted"
    tar -xf "$tarball" -C "$extracted" --strip-components=1
  fi
  # Extra tarballs unpack into a named subdirectory of the main source tree; that is
  # how Debian delivers librime-lua, which librime's plugins/CMakeLists.txt then picks
  # up by globbing directories under plugins/. Re-checked every run so an interrupted
  # first pass cannot leave the tree without the plugin.
  for e in "${extras[@]}"; do
    local eurl=${e%@*} esub=${e#*@}
    [[ "$esub" != "$e" ]] || die "--extra needs the url@subdir form, got: $e"
    if compgen -G "$extracted/$esub/*" >/dev/null; then
      log "$c: $esub already populated, keeping it"
    else
      local etar; etar="$(download "$eurl")"
      mkdir -p "$extracted/$esub"
      tar -xf "$etar" -C "$extracted/$esub" --strip-components=1
    fi
  done

  # -DCMAKE_PREFIX_PATH puts $PREFIX ahead of /usr/lib for find_package() and
  # pkg-config so fmt/fcitx5 pick up the versions we just installed.
  local -a cfg=(
    -G Ninja -B "$src/build" -S "$extracted"
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_INSTALL_PREFIX="$PREFIX"
    -DCMAKE_PREFIX_PATH="$PREFIX"
    -DPKG_CONFIG_USE_CMAKE_PREFIX_PATH=ON
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    -DENABLE_TEST=OFF -DENABLE_COVERAGE=OFF
    -DBUILD_SHARED_LIBS=ON
  )
  cfg+=("${args[@]}")

  CMAKE_PREFIX_PATH="$PREFIX" PKG_CONFIG_PATH="$PKG_CONFIG_SEARCH" \
    run cmake "${cfg[@]}" || die "cmake configure failed for $c"
  run cmake --build "$src/build" -j "$JOBS" || die "compile failed for $c"
  # cmake records every installed path in install_manifest.txt; rollback deletes
  # exactly those files, so no checkinstall/fpm packaging step is needed.
  run sudo cmake --install "$src/build" || die "install failed for $c"
  record "component=$c prefix=$PREFIX"
  log "$c done"
}

# --------------------------------------------------------------- rime plumbing
# librime-lua's CMakeLists probes exactly these pkg-config names:
#   lua lua54 lua53 lua52 luajit lua51
# but Debian's liblua5.3-dev installs the file as lua5.3.pc, and UOS has no Lua 5.4 at
# all, so the probe finds nothing and configure aborts. Copying the system descriptor
# to a name it does probe -- in a directory we own, prepended to PKG_CONFIG_PATH --
# keeps /usr untouched. The variables inside lua5.3.pc are self-contained, so a plain
# copy still resolves to -I/usr/include/lua5.3 -llua5.3.
prepare_lua_pkgconfig() {
  log "Preparing a pkg-config name librime-lua understands"
  local name
  for name in lua lua54 lua53 lua52 luajit lua51; do
    if pkg-config --exists "$name" 2>/dev/null; then
      log "pkg-config already provides $name (Lua $(pkg-config --modversion "$name"))"
      return 0
    fi
  done

  local sys
  sys=$( { ls /usr/lib/*/pkgconfig/lua5.*.pc /usr/lib/pkgconfig/lua5.*.pc \
             /usr/local/lib*/pkgconfig/lua5.*.pc 2>/dev/null || true; } \
         | grep -v 'c++' | head -1 || true)
  if [[ -z "$sys" ]]; then
    # Nothing to find yet in a dry run: install_deps has not had a chance to put
    # liblua5.3-dev on the system, and a preview should not need privileges.
    if (( DRY_RUN )); then
      warn "dry run: no lua5.x pkg-config descriptor to shim (liblua5.3-dev arrives with install_deps)"
      return 0
    fi
    die "no lua5.x pkg-config descriptor found.
     Install liblua5.3-dev, or build Lua 5.4 and put its lua.pc on PKG_CONFIG_PATH."
  fi

  run mkdir -p "$PC_SHIM_DIR"
  run cp "$sys" "$PC_SHIM_DIR/lua.pc"
  # build() and the CMake calls read PKG_CONFIG_PATH from the environment, so refresh
  # the exported value after creating the shim rather than before.
  export PKG_CONFIG_PATH="$PKG_CONFIG_SEARCH"
  if ! (( DRY_RUN )); then
    pkg-config --modversion lua >/dev/null 2>&1 \
      || die "generated $PC_SHIM_DIR/lua.pc does not resolve with pkg-config"
    log "using $sys as lua.pc (Lua $(pkg-config --modversion lua))"
  fi
}

# librime's BUILD_DATA option only installs data/preset/*.yaml, which the 1.8.5 tarball
# does not contain; the usable stock files live in data/minimal. Without them rime has
# no default.yaml in its shared data dir and deployment fails before sbsrf is even read.
install_rime_shared_data() {
  log "Installing stock Rime data into $RIME_SHARE_DIR"
  local src="$STATE_DIR/src/librime/extracted/data/minimal" f
  [[ -d "$src" ]] || die "$src missing; build librime first (run without --only?)"

  run sudo mkdir -p "$RIME_SHARE_DIR"
  for f in default.yaml essay.txt symbols.yaml; do
    [[ -f "$src/$f" ]] || die "librime source does not contain data/minimal/$f"
    run sudo install -m 644 "$src/$f" "$RIME_SHARE_DIR/$f"
    record_file "$RIME_SHARE_DIR/$f"
  done
  # A couple of stock schemas so the F4 schema list is never empty if sbsrf is skipped.
  for f in luna_pinyin.dict.yaml luna_pinyin.schema.yaml; do
    if [[ -f "$src/$f" ]]; then
      run sudo install -m 644 "$src/$f" "$RIME_SHARE_DIR/$f"
      record_file "$RIME_SHARE_DIR/$f"
    fi
  done
  if ! (( DRY_RUN )); then
    log "shared data: $(ls -1 "$RIME_SHARE_DIR" | tr '\n' ' ')"
  fi
}

# sbsrf (声笔系列码) is a pure Rime data package: YAML schemas plus lua/ and opencc/
# directories that its scripts and simplifier reference. It installs by being copied
# into fcitx5-rime's user directory -- ~/.local/share/fcitx5/rime -- and deployed.
install_sbsrf() {
  log "Installing 声笔系列码 (sbsrf)"
  local zip="$STATE_DIR/sbsrf.zip" work="$STATE_DIR/sbsrf-unpack"

  if [[ -n "$SBSRF_ZIP" ]]; then
    [[ -s "$SBSRF_ZIP" ]] || die "SBSRF_ZIP=$SBSRF_ZIP is not a readable file"
    zip="$SBSRF_ZIP"
  elif (( ! DRY_RUN )) && [[ ! -s "$zip" ]]; then
    if [[ -z "$PROXY" && -z "$https_proxy" ]]; then
      warn "no --proxy given; the GitHub download will probably fail on this network"
    fi
    run curl -fL --retry 2 --max-time 1800 -o "$zip" "$SBSRF_URL" || die "download failed"
  fi

  # Zip magic rather than an extension check: a truncated or HTML-error download of a
  # 73 MB asset is the usual failure here and unpacking it would half-install schemas.
  if (( ! DRY_RUN )); then
    [[ "$(head -c 2 "$zip" 2>/dev/null)" == 'PK' ]] || die "$zip is not a zip archive"
    rm -rf "$work"; mkdir -p "$work"
    unzip -q "$zip" -d "$work" || die "could not unpack $zip"
    compgen -G "$work/*.yaml" >/dev/null || die "no schema YAML found in $zip"
  fi

  run mkdir -p "$RIME_USER_DIR"
  local f t n=0
  for f in "$work"/*; do
    [[ -e "$f" ]] || continue
    t="$RIME_USER_DIR/$(basename "$f")"
    # A re-run must merge, not nest: `cp -a dir dst/` with dst/dir already present
    # would create dst/dir/dir. Copying dir/. into place overwrites file by file.
    if [[ -d "$f" ]]; then
      run mkdir -p "$t"
      run cp -a "$f/." "$t/"
    else
      run cp -a "$f" "$t"
    fi
    record_file "$t"
    n=$((n+1))
  done
  if (( DRY_RUN )); then
    # The unpack is skipped in a dry run, so describe the archive instead.
    local total
    total=$(unzip -Z1 "$zip" 2>/dev/null | cut -d/ -f1 | sort -u | wc -l || true)
    log "dry run: would copy $total top-level entries from $zip into $RIME_USER_DIR"
  else
    log "installed $n entries into $RIME_USER_DIR"
  fi

  # Deploy now instead of on first use: it compiles every dictionary, which takes
  # minutes and is where a schema/lua incompatibility actually shows up. Running it
  # from the command line also puts errors on our terminal rather than in a log file.
  if [[ -x "$PREFIX/bin/rime_deployer" ]]; then
    log "Running the first rime deployment (this compiles the dictionaries; several minutes)"
    if run "$PREFIX/bin/rime_deployer" --build "$RIME_USER_DIR" "$RIME_SHARE_DIR"; then
      log "rime deployment succeeded"
      (( DRY_RUN )) || SBSRF_DEPLOYED=1
    else
      warn "rime_deployer reported errors. Check $RIME_USER_DIR/build/*.log and
       /tmp/rime.fcitx.ERROR, then re-run: $0 --only rimefe"
    fi
  else
    warn "$PREFIX/bin/rime_deployer not built; schemas are staged but not deployed"
  fi
}

# --------------------------------------------------------------- fcitx4 handoff
# Both frameworks expose the same environment contract (GTK_IM_MODULE=fcitx,
# XMODIFIERS=@im=fcitx), so no env changes are needed. What does need changing is
# the toolkit-side IM module: the fcitx4 .so files sit in the same directories
# GTK/Qt scan, and whichever loads first wins.
handoff() {
  log "Handing over from fcitx 4"
  mkdir -p "$BACKUP_DIR"

  # Move aside the fcitx 4 toolkit-side modules. The Qt one is named
  # libfcitxplatforminputcontextplugin.so, not im-fcitx.so, so match both layouts.
  # fcitx-frontend-qt4 is left untouched: fcitx5-qt is built without Qt 4 and the
  # plugin is inert once the fcitx 4 daemon no longer runs.
  local mods d f
  mods=$(dpkg -L fcitx-frontend-gtk2 fcitx-frontend-gtk3 fcitx-frontend-qt5 2>/dev/null \
         | grep -E '(/immodules/im-fcitx[a-z0-9]*\.so|/platforminputcontexts/.*fcitx.*\.so)$' \
         | grep -v fcitx5 || true)
  for f in $mods; do
    [[ -e "$f" ]] || continue
    d="$BACKUP_DIR/$(basename "$f").$(echo "$f" | md5sum | cut -c1-8)"
    [[ -e "$d" ]] || run sudo cp -a "$f" "$d"
    run sudo mv -T "$f" "$f.fcitx4-disabled"
    record "disabled=$f"
  done

  # fcitx5-gtk installs into $PREFIX/lib/gtk-3.0/im-modules. GTK only loads modules
  # listed in its immodules cache, so rebuild the cache for both toolkit generations.
  for v in 2.0 3.0; do
    if command -v "gtk-query-immodules-$v" >/dev/null 2>&1; then
      run sudo "gtk-query-immodules-$v" --update-cache || true
    fi
  done
  run sudo ldconfig

  # DDE starts fcitx 4 through its own autostart entry (fcitx-helper.desktop here,
  # not upstream's fcitx.desktop), so scan for any entry that execs fcitx 4 rather
  # than assuming a filename. Left alone: fcitx5 entries.
  local a exe b
  for a in /etc/xdg/autostart/*.desktop "$HOME/.config/autostart"/*.desktop; do
    [[ -f "$a" ]] || continue
    exe=$(grep -m1 '^Exec=' "$a" || true)
    case "$exe" in
      *fcitx5*) continue ;;
      *fcitx*)  ;;
      *)        continue ;;
    esac
    b="$BACKUP_DIR/$(basename "$a").$(echo "$a" | md5sum | cut -c1-8)"
    [[ -e "$b" ]] || run sudo cp -a "$a" "$b"
    if grep -q '^Hidden=' "$a"; then
      run sudo sed -i 's/^Hidden=.*/Hidden=true/' "$a"
    else
      run sudo sed -i '$ a\
Hidden=true' "$a"
    fi
    record "autostart=$a backup=$b"
  done
}

write_config() {
  log "Writing user configuration"
  (( DRY_RUN )) && { warn "dry run: skipping writes to $HOME/.config/fcitx5"; return; }
  mkdir -p "$HOME/.config/fcitx5/conf" "$HOME/.config/autostart"

  # keyboard-us plus 拼音, and rime when the Rime branch was built. Ctrl+Shift toggles.
  local default_im=pinyin im_items='
[Groups/0/Items/1]
Name=pinyin
Layout='
  if [[ "$RIME" == ON ]]; then
    im_items="$im_items
[Groups/0/Items/2]
Name=rime
Layout="
    # Make rime the default only once the schemas have actually compiled; a half
    # deployed rime would leave the user with no working Chinese input at all.
    if (( SBSRF_DEPLOYED )); then default_im=rime; fi
  fi

  cat > "$HOME/.config/fcitx5/profile" <<EOF
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=$default_im

[Groups/0/Items/0]
Name=keyboard-us
Layout=$im_items

[GroupOrder]
0=Default
EOF

  cat > "$HOME/.config/fcitx5/conf/pinyin.conf" <<'EOF'
Candidate Count=9
Keystroke Hint=2
Enable Auto Sync=100
EOF

  if [[ "$RIME" == ON ]]; then
    # fcitx5-rime has no user-facing options in 5.0.15 (rimeengine.cpp reads nothing
    # from conf/rime.conf), so the schema list lives entirely in the rime user dir.
    log "rime enabled in the input method profile (default IM: $default_im)"
  fi

  # Autostart fcitx5 for the session. Flags verified against instance.cpp's
  # getopt table ("ru:dDs:hv" + long --replace): -d daemonise, -r take over an
  # existing owner, -D skip launching fcitx5-configtool, which cannot be built here.
  if command -v fcitx5 >/dev/null 2>&1 || [[ -x "$PREFIX/bin/fcitx5" ]]; then
    cat > "$HOME/.config/autostart/fcitx5.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Fcitx 5
Exec=$PREFIX/bin/fcitx5 -d -r -D
Hidden=false
X-GNOME-Autostart-enabled=true
EOF
  fi
}

verify() {
  log "Verification"
  local fail=0
  "$PREFIX/bin/fcitx5" --version 2>/dev/null || { warn "fcitx5 binary not found"; fail=1; }
  if find "$PREFIX/lib" -maxdepth 3 -name '*pinyin*' 2>/dev/null | grep -q .; then
    log "pinyin module present"
  else
    warn "no pinyin module found -- Chinese input will not work"; fail=1
  fi
  log "installed IM modules:"
  ls -1 "$GTK2_DIR" "$GTK3_DIR" "$QT5_DIR/platforminputcontexts" 2>/dev/null | grep -i fcitx || true

  if [[ "$RIME" == ON ]]; then
    log "Rime chain"
    # pkg-config is what fcitx5-rime itself uses to locate librime, so querying the
    # same way proves the frontend will see our build rather than the repo's 1.4.0.
    printf '       librime %s | opencc %s | prefix %s\n' \
      "$(pkg-config --modversion rime 2>/dev/null || echo 'NOT FOUND')" \
      "$(pkg-config --modversion opencc 2>/dev/null || echo 'NOT FOUND')" \
      "$(pkg-config --variable=prefix rime 2>/dev/null || echo '?')"
    pkg-config --atleast-version 1.8.5 rime 2>/dev/null \
      || { warn "librime is not >= 1.8.5; sbsrf's lua scripts will not run"; fail=1; }
    # The addon is installed with PREFIX "" as rime.so, so this does not match
    # librime's own installed librime.so.1.8.5.
    if find "$PREFIX/lib" -maxdepth 3 -name 'rime.so' 2>/dev/null | grep -q .; then
      log "fcitx5-rime addon module installed"
    else
      warn "fcitx5-rime addon (rime.so) not found under $PREFIX/lib"; fail=1
    fi
    if [[ -f "$PREFIX/share/fcitx5/inputmethod/rime.conf" ]]; then
      log "rime input method registered"
    else
      warn "no rime.conf in $PREFIX/share/fcitx5/inputmethod"; fail=1
    fi
    # The lua processor names in sbsrf's schemas resolve at schema load time, so a
    # plugin that did not get merged into librime shows up only in the deploy log.
    if [[ -d "$RIME_USER_DIR/build" ]]; then
      log "deployed schemas: $(ls -1 "$RIME_USER_DIR/build"/*.prism.bin 2>/dev/null | wc -l) prism(s) in $RIME_USER_DIR/build"
    else
      warn "no $RIME_USER_DIR/build -- rime has not deployed anything yet"
    fi
    local elog
    for elog in /tmp/rime.tools.*.ERROR /tmp/rime.fcitx.ERROR; do
      [[ -f "$elog" ]] || continue
      if grep -qiE 'lua|simplifier|unknown|error' "$elog" 2>/dev/null; then
        warn "$elog reports problems; the first lines are:"
        grep -iE 'lua|simplifier|unknown|error' "$elog" | head -5
      fi
    done
  fi

  if (( fail )); then warn "verification reported problems, see above"; else log "fcitx5 looks healthy"; fi
  cat <<'EOF'

Next steps
  1. Log out and back in (fcitx5 must start before applications do).
  2. Confirm with:  fcitx5 --version  and  pgrep -a fcitx5
  3. Ctrl+Space / Ctrl+Shift switches to 拼音.
  4. Roll back at any time:  ./04_setup-fcitx5.sh --rollback

Note: DDE 控制中心's 输入法 panel manages fcitx 4 and will not show fcitx5.
fcitx5-configtool cannot be built here (the repos have no libkirigami-dev), so
configure fcitx5 by editing ~/.config/fcitx5/profile and ~/.config/fcitx5/conf/*.
EOF

  if [[ "$RIME" == ON ]]; then
    cat <<EOF

Rime / 声笔系列码
  - Schemas live in $RIME_USER_DIR (fcitx5-rime's user directory); the stock
    default.yaml/essay.txt/symbols.yaml are in $RIME_SHARE_DIR.
  - F4 or Ctrl+grave opens the 方案选单 to pick a 声笔 schema; after editing any
    YAML, re-deploy with:  $PREFIX/bin/rime_deployer --build \\
        $RIME_USER_DIR $RIME_SHARE_DIR
  - sbsrf needs the librime-lua plugin merged into librime; if candidates come up
    empty, re-read /tmp/rime.tools.*.ERROR for "lua" lines.
  - 简繁/异体 conversion uses the OpenCC built here (see the versions printed above);
    sbsrf's own opencc/es.{txt,json} were copied next to the schemas.
EOF
  fi
}

# --------------------------------------------------------------- rollback
rollback() {
  log "Rolling back"
  [[ -f "$MANIFEST" ]] || die "no manifest at $MANIFEST; nothing to undo"

  # Restore the fcitx 4 toolkit modules we moved aside, driven by the manifest so
  # we only undo exactly what this script renamed.
  local line orig
  while read -r line; do
    orig=${line#disabled=}
    [[ -e "$orig.fcitx4-disabled" ]] || continue
    run sudo mv -T "$orig.fcitx4-disabled" "$orig"
  done < <(grep '^disabled=' "$MANIFEST" || true)

  # Re-enable the fcitx 4 autostart entries that were hidden.
  local line a b
  while IFS= read -r line; do
    a=${line%% backup=*}; a=${a#autostart=}
    b=${line##* backup=}
    if [[ -f "$b" ]]; then run sudo cp -a "$b" "$a"; fi
  done < <(grep '^autostart=' "$MANIFEST" || true)

  # Delete what we installed, newest first so shared dirs collapse cleanly.
  local c
  for c in rimefe librime addons qt gtk opencc libime fcitx5 imdkit fmt; do
    if compgen -G "$STATE_DIR/src/$c/build/install_manifest.txt" >/dev/null; then
      while read -r f; do run sudo rm -f "$f"; done \
        < "$STATE_DIR/src/$c/build/install_manifest.txt"
    fi
  done

  # Paths placed by hand: the stock rime data and the sbsrf schemas, which no
  # install_manifest.txt covers. Only touch paths under our own prefix or the user's
  # home, so a corrupted manifest cannot turn this into a system-wide rm.
  local line p
  while IFS= read -r line; do
    p=${line#installed=}
    case "$p" in
      "$PREFIX"/*|"$HOME"/*) ;;
      *) warn "refusing to delete $p: outside $PREFIX and \$HOME"; continue ;;
    esac
    if [[ -d "$p" ]]; then run sudo rm -rf "$p"; else run sudo rm -f "$p"; fi
  done < <(grep '^installed=' "$MANIFEST" || true)

  # Generated by rime_deployer from the schema files; stale once they are gone.
  if [[ -d "$RIME_USER_DIR/build" ]]; then
    warn "removing the rime staging dir $RIME_USER_DIR/build"
    run rm -rf "$RIME_USER_DIR/build"
  fi

  run sudo ldconfig
  rm -f "$HOME/.config/autostart/fcitx5.desktop"
  warn "kept $HOME/.config/fcitx5 so your dictionary/user data survives"
  log "reboot (or log out and in) to return to fcitx 4"
}

# --------------------------------------------------------------- main
mkdir -p "$STATE_DIR" "$BUILD_DIR"; : > /dev/null
touch "$MANIFEST"

if [[ "$ACTION" == rollback ]]; then rollback; exit 0; fi

preflight
[[ "$ACTION" == preflight ]] && { log "preflight-only mode, stopping"; exit 0; }

# Authenticate once and hold the sudo timestamp alive for the whole build.
# Skipped for --dry-run so a preview needs no privileges at all.
SUDO_KEEPALIVE=""
if (( DRY_RUN )); then
  warn "dry run: no commands that change this system will be executed"
else
  log "Requesting sudo (this script never stores your password)"
  sudo -v || die "sudo unavailable. UOS blocks privileged access until 开发者模式 is enabled."
  ( while sleep 240; do sudo -n true 2>/dev/null || exit; done ) &
  SUDO_KEEPALIVE=$!
  trap '[[ -n "$SUDO_KEEPALIVE" ]] && kill "$SUDO_KEEPALIVE" 2>/dev/null || true' EXIT
fi

install_deps

# PKG_CONFIG_PATH and CMAKE_PREFIX_PATH are exported once, before any build: the
# multiarch libdir is where GNUInstallDirs actually puts our .pc files.
export CMAKE_PREFIX_PATH="$PREFIX"
discover_module_dirs
if [[ "$RIME" == ON ]]; then prepare_lua_pkgconfig; fi

# Flags below are the real cache options for these versions (verified against each
# project's CMakeLists), not generic guesses.
build fmt    "$fmt_URL"    -DFMT_TEST=OFF -DFMT_DOC=OFF
build imdkit "$imdkit_URL" -DUSE_SYSTEM_UTHASH=ON
# Wayland stays off: this is an X11 session and the repo's wayland is 1.21, older
# than what the 5.1.x line would demand. Keyboard/X11 must remain on -- fcitx5
# hard-fails if ENABLE_KEYBOARD is off while ENABLE_X11 is on.
build fcitx5 "$fcitx5_URL" -DENABLE_WAYLAND=OFF -DUSE_SYSTEMD=ON \
                       -DENABLE_XDGAUTOSTART=ON -DENABLE_ENCHANT=ON
build libime "$libime_URL" -DENABLE_DOC=OFF
# opencc before addons: chinese-addons' FindOpenCC asks pkg-config for opencc, and our
# 1.1.9 must be the one it finds (librime 1.8.5 will not compile against the repo's
# 1.0.5 at all -- it includes <opencc/Dict.hpp>, added in OpenCC 1.1.0). ENABLE_DARTS
# is off because the .ocd format it serves needs darts.h, which UOS does not package;
# opencc 1.1.x's shipped configs and sbsrf's es.json use the marisa-backed .ocd2.
build opencc "$opencc_URL" -DUSE_SYSTEM_MARISA=ON -DUSE_SYSTEM_RAPIDJSON=ON \
                       -DUSE_SYSTEM_TCLAP=ON -DENABLE_DARTS=OFF -DENABLE_GTEST=OFF \
                       -DENABLE_BENCHMARK=OFF -DBUILD_PYTHON=OFF -DBUILD_DOCUMENTATION=OFF
build gtk    "$gtk_URL"    -DENABLE_GTK4_IM_MODULE=OFF -DENABLE_GIR=OFF -DENABLE_SNOOPER=OFF \
                       -DGTK2_IM_MODULEDIR="$GTK2_DIR" -DGTK3_IM_MODULEDIR="$GTK3_DIR"
build qt     "$qt_URL"     -DENABLE_QT4=OFF -DENABLE_QT5=ON -DENABLE_QT6=OFF \
                       -DCMAKE_INSTALL_QT5PLUGINDIR="$QT5_DIR"
# GUI/Browser off: they want QtWebEngine/QtWebKit, which are not buildable here.
# OpenCC powers 简繁转换; pass --no-opencc if the repo's opencc 1.0.5 is too old.
build addons "$addons_URL" -DENABLE_GUI=OFF -DENABLE_BROWSER=OFF -DENABLE_OPENCC="$OPENCC" \
                       -DENABLE_CLOUDPINYIN=ON

if in_build_set librime; then
  # The lua plugin is merged into librime (BUILD_MERGED_PLUGINS) rather than loaded
  # from RIME_PLUGINS_DIR, because sbsrf's schemas name processors as
  # lua_processor@*sbxlm.editor -- that module syntax needs librime-lua present, and
  # building it in-tree avoids the external-plugin loader version checks.
  build librime "$librime_URL" --extra "$librime_lua_URL@plugins/lua" \
                       -DBUILD_TEST=OFF -DBUILD_MERGED_PLUGINS=ON -DBUILD_DATA=OFF \
                       -DENABLE_LOGGING=ON -DBOOST_USE_SIGNALS2=ON \
                       -DRIME_DATA_DIR="$RIME_SHARE_DIR"
  install_rime_shared_data
  # RIME_DATA_DIR is defined on the command line, so fcitx5-rime's
  # find_package(RimeData REQUIRED) is skipped -- there is no rime-data package here.
  build rimefe "$rimefe_URL" -DRIME_DATA_DIR="$RIME_SHARE_DIR"
fi

run sudo ldconfig

if [[ "$SBSRF" == ON ]] && in_build_set rimefe; then
  install_sbsrf
fi

handoff
write_config
verify
