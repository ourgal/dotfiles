#!/usr/bin/env bash
set -euo pipefail

user="user"
dufs_url="http://192.168.1.110:6500"
chroot_dir="/target"

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

run_debug() {
    printf 'Running as: %s\n' "$(id -un)"
    printf 'OS: %s\n' "$(uname -a)"
    printf 'User: %s\n' "$user"
    printf 'dufs_url: %s\n' "$dufs_url"
}

run_setup() {
    mkdir -p "$chroot_dir/var/lib/deepin/developer-mode"
    chmod 755 "$chroot_dir/var/lib/deepin/developer-mode"
    printf '1\n' > "$chroot_dir/var/lib/deepin/developer-mode/enabled"
    chmod 644 "$chroot_dir/var/lib/deepin/developer-mode/enabled"
}

run_network() {
    cp /etc/resolv.conf "$chroot_dir/etc/resolv.conf"
}

run_apt() {
    cp /etc/apt/auth.conf.d/uos.conf "$chroot_dir/etc/apt/auth.conf.d/uos.conf"
}

run_repo() {
    printf 'deb [trusted=yes] https://ci.deepin.com/repo/obs/linglong:/CI:/release/uos_1070/ ./\n' \
        > "$chroot_dir/etc/apt/sources.list.d/linglong.list"
}

run_pkg() {
    curl -fSL -o "$chroot_dir/tmp/wps.deb" \
        "https://pubwps-wps365-obs.wpscdn.cn/download/Linux/24730/wps-office_12.1.2.24730.AK.preread.sw_644358_arm64.deb"
    chmod 644 "$chroot_dir/tmp/wps.deb"
}

run_font() {
    curl -fSL "$dufs_url/fonts/windows.zip" | \
        bsdtar -xpf - -C "$chroot_dir/usr/share/fonts/"
}

run_user() {
    mkdir -p "$chroot_dir/home/$user/.ssh"
    chmod 755 "$chroot_dir/home/$user/.ssh"
    cp /home/uos/.ssh/authorized_keys "$chroot_dir/home/$user/.ssh/authorized_keys"
    chmod 644 "$chroot_dir/home/$user/.ssh/authorized_keys"
}

run_chroot() {
    cat > "$chroot_dir/script" <<'EOSCRIPT'
set -euo pipefail
apt update
apt install -y com.zjd.gov
apt install -y com.tencent.wechat
apt install -y com.360.browser-stable
apt install -y linglong-bin linglong-installer
apt install -y /tmp/wps.deb
apt install -y awesome
systemctl enable ssh
chown -R zxc:zxc /home/zxc/.ssh
EOSCRIPT
    chmod 644 "$chroot_dir/script"

    [ -d "$chroot_dir" ] || fail 'not a directory'
    [ -d "$chroot_dir/dev" ] || fail 'no /dev in chroot'
    [ -d "$chroot_dir/proc" ] || fail 'no /proc in chroot'
    [ -d "$chroot_dir/sys" ] || fail 'no /sys in chroot'

    for _fs in dev proc sys; do
        mount --rbind "/$_fs" "$chroot_dir/$_fs"
        mount --make-rslave "$chroot_dir/$_fs"
    done

    cleanup() {
        umount -R "$chroot_dir/dev" "$chroot_dir/proc" "$chroot_dir/sys"
    }

    trap cleanup EXIT INT

    LANG=C.UTF-8 chroot "$chroot_dir" /bin/bash /script

    rm -f "$chroot_dir/script"
}

main() {
    local run_all=false

    if [ $# -eq 0 ]; then
        run_all=true
    fi

    for tag in "$@"; do
        case "$tag" in
            debug) run_debug ;;
            setup) run_setup ;;
            network) run_network ;;
            config)
                run_network
                run_apt
                run_user
                ;;
            apt) run_apt ;;
            repo) run_repo ;;
            pkg) run_pkg ;;
            download)
                run_pkg
                run_font
                ;;
            font) run_font ;;
            user) run_user ;;
            chroot) run_chroot ;;
            *)
                fail "unknown tag: $tag"
                ;;
        esac
    done

    if $run_all; then
        run_setup
        run_network
        run_apt
        run_repo
        run_pkg
        run_font
        run_user
        run_chroot
    fi
}

main "$@"
