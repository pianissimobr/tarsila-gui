#!/bin/bash
# Indicador de rede no top bar (genmon). O icone e recolorido por
# tarsila-tema-apply.sh em ~/.cache/tarsila/topbar/ e segue a cor do tema
# (mesmo tom do icone de som). Substitui o icone lavado do nm-applet.
IC="$HOME/.cache/tarsila/topbar"
st=$(nmcli -t -f TYPE,STATE device 2>/dev/null)
if echo "$st" | grep -q '^ethernet:connected'; then
  ICON="$IC/net-wired.svg"; TIP="Rede cabeada conectada"
elif echo "$st" | grep -q '^wifi:connected'; then
  ICON="$IC/net-wireless.svg"; TIP="Wi-Fi conectado"
else
  ICON="$IC/net-off.svg"; TIP="Sem conexao de rede"
fi
[ -f "$ICON" ] || ICON=/usr/share/icons/Papirus/22x22/symbolic/devices/network-wired-symbolic.svg
echo "<img>$ICON</img>"
echo "<tool>$TIP</tool>"
echo "<click>nm-connection-editor</click>"
