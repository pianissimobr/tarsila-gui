#!/bin/bash
# Vai para a janela de trabalho 2: todos os apps abertos ficam visiveis e
# flutuantes - nenhum escondido, nenhum maximizado.
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-state"
wmctrl -k off
for id in $(wmctrl -lx 2>/dev/null | grep -viE 'plank|xfce4-panel|xfdesktop|polybar' | awk '{print $1}'); do
  wmctrl -ir "$id" -b remove,maximized_vert,maximized_horz
done
uid=$(cat "${XDG_RUNTIME_DIR:-/tmp}/tarsila-undecorated" 2>/dev/null)
if [ -n "$uid" ]; then
  xdotool windowactivate "$uid" 2>/dev/null
  sleep 0.05
  xdotool key --clearmodifiers super+i 2>/dev/null
  rm -f "${XDG_RUNTIME_DIR:-/tmp}/tarsila-undecorated"
fi
echo 2 > "$STATE_FILE"

# Acorda o top bar na hora (bolinhas/botoes pollam devagar - rede de
# seguranca de 10s; ver tarsila-topbar-refresh.sh). Pequena espera para
# o gerenciador de janelas terminar de aplicar o estado.
( sleep 0.2; /usr/local/bin/tarsila-topbar-refresh.sh ) >/dev/null 2>&1 &
