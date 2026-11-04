#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$task_root"
version=$(/usr/bin/python3 -c 'from vibekey import __version__; print(__version__)')
arch=all
task_stage=$(mktemp -d)
trap 'rm -rf "$task_stage"' EXIT HUP INT TERM
mkdir -p "$task_stage/DEBIAN" "$task_stage/usr/lib/vibekey" \
    "$task_stage/usr/bin" "$task_stage/usr/lib/systemd/user" \
    "$task_stage/usr/share/applications" "$task_stage/etc/xdg/autostart" \
    "$task_stage/lib/udev/rules.d" "$task_stage/usr/lib/modules-load.d" \
    "$task_stage/usr/share/doc/vibekey"
# Copy only source assets, never caches, environment files or local configs.
mkdir -p "$task_stage/usr/lib/vibekey/vibekey" "$task_stage/usr/lib/vibekey/web"
cp vibekey/*.py "$task_stage/usr/lib/vibekey/vibekey/"
cp web/*.html web/*.css web/*.js web/*.mjs "$task_stage/usr/lib/vibekey/web/"
cp -R web/assets "$task_stage/usr/lib/vibekey/web/"
for program in vibekey vibekey-session vibekey-open vibekey-vinput vibekey-vinput-gui vibekey-voice vibekey-codex vibekey-claude; do
    install -m 755 "packaging/$program" "$task_stage/usr/bin/$program"
done
install -m 644 packaging/vibekey.service "$task_stage/usr/lib/systemd/user/"
install -m 644 packaging/vibekey.desktop packaging/vibekey-codex.desktop packaging/vibekey-claude.desktop "$task_stage/usr/share/applications/"
install -m 644 packaging/vibekey-autostart.desktop "$task_stage/etc/xdg/autostart/"
install -m 644 packaging/70-vibekey.rules "$task_stage/lib/udev/rules.d/"
install -m 644 packaging/vibekey.conf "$task_stage/usr/lib/modules-load.d/"
install -m 755 packaging/postinst "$task_stage/DEBIAN/postinst"
cp README.md THIRD_PARTY.md "$task_stage/usr/share/doc/vibekey/"
install -D -m 644 docs/images/workbench.png "$task_stage/usr/share/doc/vibekey/docs/images/workbench.png"
install -D -m 644 docs/advanced-setup.md "$task_stage/usr/share/doc/vibekey/docs/advanced-setup.md"
install -D -m 644 docs/fcitx5-vinput.md "$task_stage/usr/share/doc/vibekey/docs/fcitx5-vinput.md"
install -D -m 644 docs/desktop-packaging.md "$task_stage/usr/share/doc/vibekey/docs/desktop-packaging.md"
install -D -m 644 docs/auto-follow.md "$task_stage/usr/share/doc/vibekey/docs/auto-follow.md"
install -D -m 644 docs/auto-follow-live-test.json "$task_stage/usr/share/doc/vibekey/docs/auto-follow-live-test.json"
install -D -m 644 docs/ui-parity.md "$task_stage/usr/share/doc/vibekey/docs/ui-parity.md"
mkdir -p "$task_stage/usr/share/doc/vibekey/docs/rea"
cp docs/rea/*.md docs/rea/*.json "$task_stage/usr/share/doc/vibekey/docs/rea/"
install -m 644 LICENSE "$task_stage/usr/share/doc/vibekey/copyright"
cat > "$task_stage/DEBIAN/control" <<EOF
Package: vibekey
Version: $version
Section: utils
Priority: optional
Architecture: $arch
Maintainer: VibeKey Linux contributors <vibekey@localhost>
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, libgtk-3-bin, pulseaudio-utils, wmctrl, x11-utils, xdg-utils, udev, systemd, kmod, adduser
Recommends: gnome-terminal
Description: Ulanzi AU05 userspace driver and local configuration UI
 Python HID and uinput driver, browser configuration interface, gestures,
 profiles, macros and optional speech transcription.
EOF
mkdir -p dist
dpkg-deb --root-owner-group --build "$task_stage" "dist/vibekey_${version}_${arch}.deb"

