#!/bin/bash
# Vai para a janela de trabalho 3: app ativo maximizado.
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-state"
wmctrl -k off
id=$(xdotool getactivewindow 2>/dev/null)
if [ -n "$id" ]; then
  wmctrl -ir "$id" -b add,maximized_vert,maximized_horz
  sleep 0.12
  echo "$id" > "${XDG_RUNTIME_DIR:-/tmp}/tarsila-undecorated"
  xdotool key --clearmodifiers super+u
fi
echo 3 > "$STATE_FILE"

# Acorda o top bar na hora (bolinhas/botoes pollam devagar - rede de
# seguranca de 10s; ver tarsila-topbar-refresh.sh). Pequena espera para
# o gerenciador de janelas terminar de aplicar o estado.
( sleep 0.2; /usr/local/bin/tarsila-topbar-refresh.sh ) >/dev/null 2>&1 &
