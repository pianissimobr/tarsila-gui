#!/bin/bash
# Gera tarsila-email v2.0.0 (.deb)
set -euo pipefail

PKG=tarsila-email
VER=2.1.0
STAGE="/tmp/${PKG}-deb"
ROOT="$STAGE/opt/tarsila-email"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$STAGE"
mkdir -p "$ROOT"/{bin,lib,ui/css,ui/js} "$STAGE/DEBIAN" \
         "$STAGE/usr/local/bin" "$STAGE/usr/share/tarsila/applications"

install -m 755 "$SCRIPT_DIR/tarsila-email" "$STAGE/usr/local/bin/tarsila-email"
install -m 755 "$SCRIPT_DIR/bin/"*.py "$ROOT/bin/"
install -m 644 "$SCRIPT_DIR/lib/"*.py "$ROOT/lib/"
install -m 644 "$SCRIPT_DIR/ui/index.html" "$ROOT/ui/"
install -m 644 "$SCRIPT_DIR/ui/css/"*.css "$ROOT/ui/css/"
install -m 644 "$SCRIPT_DIR/ui/js/"*.js "$ROOT/ui/js/"
install -m 644 "$SCRIPT_DIR/tarsila-email.desktop" \
    "$STAGE/usr/share/tarsila/applications/tarsila-email.desktop"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: tarsila-email
Version: $VER
Section: mail
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-gdkpixbuf-2.0, fonts-roboto
Recommends: libnotify-bin
Maintainer: Tarsila OS <tarsila@local>
Description: Tarsila Email — Gmail leve com sync IMAP
 App nativo GTK3 (sem WebKit). Sync bidirecional Gmail via IMAP/SMTP.
 Cache SQLite, notificacoes IDLE, UI estilo Gmail.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
rm -f /usr/share/tarsila/applications/configurar-claws.desktop
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

DEB="/tmp/${PKG}_${VER}_all.deb"
dpkg-deb --root-owner-group -b "$STAGE" "$DEB"
echo "Pacote: $DEB"
dpkg -i "$DEB" 2>/dev/null || echo "(instale manualmente: sudo dpkg -i $DEB)"
