#!/bin/bash
# Janela de trabalho 2: todos os apps abertos, flutuantes - nenhum
# escondido. Bloqueada (sem clique) se nao houver nenhum app aberto.
# As bolinhas moram num painel proprio (panel-2) fixo no centro da tela
# (ver tarsila-dot1.sh) - sem "apagao" de transicao.
DOTS=/usr/local/share/tarsila
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-state"
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

state=""
[ -f "$STATE_FILE" ] && read -r state < "$STATE_FILE"

if [ "$MAX" -eq 0 ] && [ "$state" != "1" ]; then
  echo "<img>$DOTS/dot-on.svg</img>"
else
  echo "<img>$DOTS/dot-off.svg</img>"
fi
echo "<click>/usr/local/bin/tarsila-goto2.sh</click>"
