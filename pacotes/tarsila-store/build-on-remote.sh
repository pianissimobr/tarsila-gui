#!/bin/bash
# Gera e instala tarsila-store v3.0.0 (GTK3 + WebKit2, sem Chromium)
# Executar no alvo: bash build-on-remote.sh
set -euo pipefail

PKG=tarsila-store
VER=3.0.0
STAGE="/tmp/${PKG}-deb-v3"
ROOT="$STAGE/opt/tarsila-store"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

rm -rf "$STAGE"
mkdir -p "$ROOT"/bin "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/etc/sudoers.d"

cp -a /opt/tarsila-store/loja "$ROOT/"
cp -a /opt/tarsila-store/bin/tarsila-atalho-criar "$ROOT/bin/"
cp -a /opt/tarsila-store/bin/tarsila-backend.py "$ROOT/bin/"
cp -a /opt/tarsila-store/bin/tarsila-deb-gui.py "$ROOT/bin/"
cp -a /opt/tarsila-store/bin/tarsila-deb-instalar "$ROOT/bin/"
cp -a /opt/tarsila-store/bin/tarsila-pkg "$ROOT/bin/"
cp /opt/tarsila-store/tarsila-store-handler.sh "$ROOT/"
cp /opt/tarsila-store/whitelist.txt "$ROOT/"

install -m 755 "$SCRIPT_DIR/tarsila-store.py" "$ROOT/bin/tarsila-store.py"
ln -sf tarsila-store.py "$ROOT/bin/tarsila-store"
ln -sf tarsila-store.py "$ROOT/bin/tarsila-store-launcher.sh"

sed -i 's/loading="lazy" decoding="async"/loading="eager" decoding="sync" data-tarsila-ok="1"/' \
  "$ROOT/loja/js/store.js" 2>/dev/null || true

ln -sf /opt/tarsila-store/bin/tarsila-store "$STAGE/usr/bin/tarsila-store"

cat > "$STAGE/usr/share/applications/tarsila-store.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Tarsila Store
GenericName=Loja de Aplicativos
Comment=Instale apps e jogos com um clique
Exec=/usr/local/bin/tarsila-abrindo /usr/local/bin/tarsila-uma-janela store "Tarsila Store" /usr/bin/tarsila-store
Icon=tarsila-store
Categories=System;PackageManager;
Terminal=false
StartupNotify=true
StartupWMClass=tarsila-store
EOF

cat > "$STAGE/usr/share/applications/tarsila-protocol.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Tarsila Store Handler
Comment=Instala pacotes solicitados pela Tarsila Store
Exec=$ROOT/tarsila-store-handler.sh %u
MimeType=x-scheme-handler/tarsila;
NoDisplay=true
Terminal=false
EOF

for sz in 48 64 128 256 512; do
  src="/usr/share/icons/hicolor/${sz}x${sz}/apps/tarsila-store.png"
  [ -f "$src" ] || continue
  mkdir -p "$STAGE/usr/share/icons/hicolor/${sz}x${sz}/apps"
  cp "$src" "$STAGE/usr/share/icons/hicolor/${sz}x${sz}/apps/"
done

cat > "$STAGE/etc/sudoers.d/tarsila-store" <<'EOF'
ALL ALL=(root) NOPASSWD: /opt/tarsila-store/bin/tarsila-pkg
EOF
chmod 440 "$STAGE/etc/sudoers.d/tarsila-store"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: tarsila-store
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: libnotify-bin
Maintainer: Tarsila OS <tarsila@local>
Description: Loja de aplicativos Tarsila (app nativo GTK+WebKit)
 Aplicativo independente: exibe a loja via WebKit2GTK, sem Chromium.
 HTML/CSS/JS em /opt/tarsila-store/loja/, backend Python na porta 8474.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
fi
mkdir -p /usr/share/tarsila/applications
cp /usr/share/applications/tarsila-store.desktop /usr/share/tarsila/applications/
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

apt-get install -y --no-install-recommends \
  python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0

DEB="/tmp/${PKG}_${VER}_all.deb"
dpkg-deb --root-owner-group -b "$STAGE" "$DEB"
echo "Pacote: $DEB"
dpkg -i "$DEB"
echo "OK: $(dpkg -l tarsila-store | tail -1)"
python3 -c 'import gi; gi.require_version("WebKit2","4.1"); from gi.repository import WebKit2; print("WebKit2 OK")'
