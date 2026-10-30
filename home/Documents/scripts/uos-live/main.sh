#!/bin/bash
# Port of playbooks/main.yml (Ansible) to plain bash.
#
# Prepares a mounted UOS system at /target from the live installer:
#   - disable power saving
#   - enable password ssh login and start ssh
#   - change uos password (current password is empty)
#   - ssh-copy-id
#
# Usage:
#   bash main.sh             # run all stages in playbook order
#   bash main.sh chroot      # run only the given stages
# Stages: debug setup network apt pkg font user chroot

set -euo pipefail

TARGET=/target
user=user
dufs_url=http://192.168.0.108:6500
wps_url=https://pubwps-wps365-obs.wpscdn.cn/download/Linux/24730/wps-office_12.1.2.24730.AK.preread.sw_644358_arm64.deb

log() { printf '%s\n' "==> $*"; }
die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

fetch() { # fetch <url> <dest-file>
        if command -v curl >/dev/null 2>&1; then
                curl -fL --retry 3 -o "$2" "$1"
        else
                wget -O "$2" "$1"
        fi
}

stage_debug() { # equivalent of the playbook's ansible_facts dump
        log 'system facts'
        uname -a
        lsblk 2>/dev/null || true
        [ -d "$TARGET" ] && echo "target: $TARGET" || echo "target: MISSING"
}

stage_setup() {
        log 'enabling developer mode'
        mkdir -p "$TARGET/var/lib/deepin/developer-mode"
        chmod 0755 "$TARGET/var/lib/deepin/developer-mode"
        printf '1' > "$TARGET/var/lib/deepin/developer-mode/enabled"
        chmod 0644 "$TARGET/var/lib/deepin/developer-mode/enabled"
}

stage_network() {
        log 'copying resolv.conf'
        mkdir -p "$TARGET/etc"
        cp -p /etc/resolv.conf "$TARGET/etc/resolv.conf"
}

stage_apt() {
        log 'copying apt auth file'
        mkdir -p "$TARGET/etc/apt/auth.conf.d"
        cp -p /etc/apt/auth.conf.d/uos.conf "$TARGET/etc/apt/auth.conf.d/uos.conf"

        log 'adding linglong repo'
        printf '%s\n' 'deb [trusted=yes] https://ci.deepin.com/repo/obs/linglong:/CI:/release/uos_1070/ ./' \
                > "$TARGET/etc/apt/sources.list.d/linglong.list"
}

stage_pkg() {
        log 'downloading wps 365'
        fetch "$wps_url" "$TARGET/tmp/wps.deb"
        chmod 0644 "$TARGET/tmp/wps.deb"
}

stage_font() {
        log 'installing windows fonts'
        # unzip cannot read a zip from stdin, so download to a temp file first
        local zip
        zip=$(mktemp /tmp/windows.XXXXXX.zip)
        fetch "$dufs_url/fonts/windows.zip" "$zip"
        unzip -o "$zip" -d "$TARGET/usr/share/fonts/"
        rm -f "$zip"
}

stage_user() {
        log "installing authorized_keys for $user"
        mkdir -p "$TARGET/home/$user/.ssh"
        chmod 0700 "$TARGET/home/$user/.ssh"
        cp /home/uos/.ssh/authorized_keys "$TARGET/home/$user/.ssh/authorized_keys"
        chmod 0600 "$TARGET/home/$user/.ssh/authorized_keys"
}

stage_chroot() {
        log 'running chroot script'

        [ -d "$TARGET" ] || die 'not a directory'
        [ -d "$TARGET/dev" ] || die 'no /dev in chroot'
        [ -d "$TARGET/proc" ] || die 'no /proc in chroot'
        [ -d "$TARGET/sys" ] || die 'no /sys in chroot'

        cat > "$TARGET/script" <<EOF
set -euo pipefail
apt update
apt install -y com.zjd.gov
apt install -y com.tencent.wechat
apt install -y com.360.browser-stable
apt install -y linglong-bin linglong-installer
apt install -y /tmp/wps.deb
systemctl enable ssh
chown -R $user:$user /home/$user/.ssh
EOF
        chmod 0644 "$TARGET/script"

        for _fs in dev proc sys; do
                mount --rbind "/$_fs" "$TARGET/$_fs"
                mount --make-rslave "$TARGET/$_fs"
        done

        cleanup() {
                umount -R "$TARGET/dev" "$TARGET/proc" "$TARGET/sys"
        }
        trap cleanup EXIT INT

        LANG=C.UTF-8 chroot "$TARGET" /bin/bash /script

        trap - EXIT INT
        cleanup
        rm -f "$TARGET/script"
}

main() {
        [ "$(id -u)" -eq 0 ] || die 'must run as root'
        [ -d "$TARGET" ] || die "no $TARGET: is the target system mounted?"

        local stages=(debug setup network apt pkg font user chroot)
        [ $# -gt 0 ] && stages=("$@")

        local s
        for s in "${stages[@]}"; do
                case "$s" in
                debug)  stage_debug ;;
                setup)  stage_setup ;;
                network) stage_network ;;
                apt)    stage_apt ;;
                pkg)    stage_pkg ;;
                font)   stage_font ;;
                user)   stage_user ;;
                chroot) stage_chroot ;;
                *)      die "unknown stage: $s" ;;
                esac
        done
}

main "$@"
