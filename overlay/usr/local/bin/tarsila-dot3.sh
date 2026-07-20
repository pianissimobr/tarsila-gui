#!/bin/bash
# Janela de trabalho 3: app selecionado maximizado. Bloqueada (sem
# clique) se nao houver nenhum app aberto.
# As bolinhas moram num painel proprio (panel-2) fixo no centro da tela
# (ver tarsila-dot1.sh) - sem "apagao" de transicao.
DOTS=/usr/local/share/tarsila
TOPBAR_STATE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
WINCOUNT_CACHE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-wincount"

MAX=0
if [ -f "$TOPBAR_STATE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in MAX) MAX=$v;; esac
  done < "$TOPBAR_STATE"
fi

n=""
[ -f "$WINCOUNT_CACHE" ] && read -r n < "$WINCOUNT_CACHE"
[ -z "$n" ] && n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|xfce4-panel|xfdesktop' | wc -l)

if [ "$n" -eq 0 ]; then
  echo "<img>$DOTS/dot-off.svg</img>"
  exit 0
fi

if [ "$MAX" -eq 1 ]; then
  echo "<img>$DOTS/dot-on.svg</img>"
else
  echo "<img>$DOTS/dot-off.svg</img>"
fi
echo "<click>/usr/local/bin/tarsila-goto3.sh</click>"
