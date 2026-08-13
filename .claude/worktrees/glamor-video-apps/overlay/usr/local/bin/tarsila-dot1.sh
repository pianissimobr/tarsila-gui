#!/bin/bash
# Janela de trabalho 1: fundo limpo, sem apps. Sempre clicavel.
# As bolinhas moram num painel proprio (panel-2), flutuante e fixo no
# centro da tela - o conteudo do top bar (titulo/botoes, panel-1) nao
# influencia mais a posicao delas, entao o "apagao" de transicao e a
# compensacao por espacador deixaram de existir.
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
state=""
[ -f "$STATE_FILE" ] && read -r state < "$STATE_FILE"

if [ "$n" -eq 0 ] || { [ "$MAX" -eq 0 ] && [ "$state" = "1" ]; }; then
  echo "<img>$DOTS/dot-on.svg</img>"
else
  echo "<img>$DOTS/dot-off.svg</img>"
fi
echo "<click>/usr/local/bin/tarsila-goto1.sh</click>"
