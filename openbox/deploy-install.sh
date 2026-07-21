#!/bin/bash
# Instala a sessão Tarsila-Openbox na box, COEXISTINDO com o XFCE.
# Roda como root na box. Não altera a sessão padrão do alan.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/deploy"
U=alan; H=/home/$U

echo "==> deps"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends \
  openbox polybar dunst xsettingsd picom feh \
  inotify-tools fonts-font-awesome fonts-noto-core pavucontrol >/dev/null 2>&1 || \
apt-get install -y --no-install-recommends \
  openbox polybar dunst xsettingsd picom feh \
  inotify-tools fonts-font-awesome fonts-noto-core pavucontrol

echo "==> arquivos de sistema (usr/)"
cp -a "$SRC/usr/." /usr/
chmod 755 /usr/local/bin/tarsila-ob-* /usr/local/bin/tarsila-ob-session

echo "==> config do usuário $U"
for d in openbox polybar xsettingsd dunst; do
  mkdir -p "$H/.config/$d"
  cp -a "$SRC/home/$d/." "$H/.config/$d/"
done
chmod 755 "$H/.config/openbox/autostart" "$H/.config/polybar/"*.sh
mkdir -p "$H/.config/tarsila"
[ -f "$H/.config/tarsila/tema" ] || echo padrao > "$H/.config/tarsila/tema"
chown -R $U:$U "$H/.config/openbox" "$H/.config/polybar" \
               "$H/.config/xsettingsd" "$H/.config/dunst" "$H/.config/tarsila"

echo "==> fontconfig"
fc-cache -f >/dev/null 2>&1 || true

echo "OK — sessão 'Tarsila (Openbox)' registrada (coexiste com o XFCE)."
echo "   Sessão padrão do $U NÃO foi alterada."
