#!/bin/bash
# Instala Tarsila Email v2.1 (app GTK nativo + sync Gmail).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RAIZ="/opt/tarsila-email"

mkdir -p "$RAIZ"/{bin,lib,ui/css,ui/js}
install -m 755 "$SCRIPT_DIR/tarsila-email" /usr/local/bin/tarsila-email
install -m 755 "$SCRIPT_DIR/bin/"*.py "$RAIZ/bin/"
install -m 644 "$SCRIPT_DIR/lib/"*.py "$RAIZ/lib/"
install -m 644 "$SCRIPT_DIR/ui/index.html" "$RAIZ/ui/"
install -m 644 "$SCRIPT_DIR/ui/css/"*.css "$RAIZ/ui/css/"
install -m 644 "$SCRIPT_DIR/ui/js/"*.js "$RAIZ/ui/js/"
install -m 644 "$SCRIPT_DIR/tarsila-email.desktop" /usr/share/tarsila/applications/tarsila-email.desktop

rm -f /usr/share/tarsila/applications/configurar-claws.desktop

fix_plank() {
    local user="$1" dock="$2/launchers"
    [ -d "$dock" ] || return 0
    rm -f "$dock/02-configurar-claws.dockitem"
    cat > "$dock/02-tarsila-email.dockitem" <<'EOF'
[PlankDockItemPreferences]
Launcher=file:///usr/share/tarsila/applications/tarsila-email.desktop
EOF
    chown "$user:$user" "$dock/02-tarsila-email.dockitem" 2>/dev/null || true
    sudo -u "$user" env DISPLAY=:0 XAUTHORITY="/home/$user/.Xauthority" bash -c '
        /usr/local/bin/tarsila-dock-apply.sh 2>/dev/null || true
        pgrep -x plank >/dev/null || nohup plank >/dev/null 2>&1 &
    '
}

fix_plank alan /home/alan/.config/plank/dock1

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo "OK: Tarsila Email v2.1.0 (GTK)"
echo "  /usr/local/bin/tarsila-email"
echo "  $RAIZ/"
