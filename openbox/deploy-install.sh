#!/bin/bash
# Instala a sessão Tarsila-Openbox na box, COEXISTINDO com o XFCE.
# Roda como root na box. Ver README.md para o contexto de cada passo.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)/deploy"
U="${1:-alan}"; H="$(getent passwd "$U" | cut -d: -f6)"
[ -n "$H" ] || { echo "Usuário '$U' não existe. Uso: sudo ./deploy-install.sh <usuario>"; exit 1; }

echo "==> deps"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends \
  openbox polybar dunst xsettingsd picom feh \
  inotify-tools fonts-font-awesome fonts-noto-core pavucontrol yad wmctrl xdotool x11-utils

echo "==> arquivos de sistema (usr/, etc/)"
cp -a "$SRC/usr/." /usr/
[ -d "$SRC/etc" ] && cp -a "$SRC/etc/." /etc/
chmod 755 /usr/local/bin/tarsila-ob-* /usr/local/bin/tarsila-limpar.sh 2>/dev/null || true

echo "==> fonte de ícones (cápsulas arredondadas do botão Limpar)"
mkdir -p /usr/share/fonts/nerd
cp -f "$SRC/usr/share/fonts/nerd/"*.ttf /usr/share/fonts/nerd/ 2>/dev/null || true
fc-cache -f >/dev/null 2>&1 || true

echo "==> config do usuário $U"
for d in openbox polybar xsettingsd dunst; do
  mkdir -p "$H/.config/$d"; cp -a "$SRC/home/$d/." "$H/.config/$d/"
done
chmod 755 "$H/.config/openbox/autostart" "$H/.config/polybar/"*.sh
mkdir -p "$H/.config/tarsila"; [ -f "$H/.config/tarsila/tema" ] || echo padrao > "$H/.config/tarsila/tema"
# ~/.xsession força a sessão Openbox em qualquer login (o greeter sem
# accountsservice ignora .dmrc/user-session e cai no XFCE — ver README)
cp -f "$SRC/home/dot-xsession" "$H/.xsession"; chmod +x "$H/.xsession"
grep -q "^allow-user-xsession" /etc/X11/Xsession.options 2>/dev/null || \
  echo "allow-user-xsession" >> /etc/X11/Xsession.options
chown -R "$U:$U" "$H/.config" "$H/.xsession"

echo
echo "OK — Tarsila-Openbox instalada para $U."
echo
echo "IMPORTANTE (hardware Amlogic/Mali-Panfrost): este pacote inclui"
echo "  /etc/X11/xorg.conf.d/10-modeset-panfrost.conf com AccelMethod=none"
echo "  (glamor DESLIGADO) — necessário porque a GPU Mali-G31 segfaulta o"
echo "  Xorg ao abrir janelas com aceleração. Em GPUs estáveis, remova esse"
echo "  arquivo para ter aceleração 2D. Reinicie após instalar."
