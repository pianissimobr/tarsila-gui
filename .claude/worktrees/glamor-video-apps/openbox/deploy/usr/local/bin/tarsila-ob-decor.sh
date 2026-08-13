#!/bin/bash
# Vigia de decoracao (sessao Openbox): quando uma janela esta maximizada
# (estado "bolinha 3"), o titulo/botoes vivem na top bar (polybar), entao a
# janela NAO deve mostrar a propria barra de titulo. Este vigia le o state
# file gravado pelo lider (title.sh) e:
#   MAX=1  -> Undecorate a janela ID
#   MAX=0  -> Decorate de volta a janela que estava sem barra
# Usa as acoes nativas do Openbox via keybinds W-u/W-i (rc.xml) disparados
# por xdotool (o Openbox nao re-le _MOTIF_WM_HINTS ao vivo, mas as acoes
# Undecorate/Decorate funcionam). Event-driven via inotify no state file.
RT="${XDG_RUNTIME_DIR:-/tmp}"; STATE="$RT/tarsila-topbar-state.txt"
prev=""
undec(){ xdotool windowactivate --sync "$1" 2>/dev/null; xdotool key --clearmodifiers super+u 2>/dev/null; }
dec(){   xdotool windowactivate --sync "$1" 2>/dev/null; xdotool key --clearmodifiers super+i 2>/dev/null; }
apply(){
  local MAX=0 ID=""
  if [ -f "$STATE" ]; then MAX=$(sed -n 's/^MAX=//p' "$STATE"); ID=$(sed -n 's/^ID=//p' "$STATE"); fi
  if [ "$MAX" = 1 ] && [ -n "$ID" ]; then
    if [ "$ID" != "$prev" ]; then
      [ -n "$prev" ] && dec "$prev"
      undec "$ID"; prev="$ID"
    fi
  else
    [ -n "$prev" ] && { dec "$prev"; prev=""; }
  fi
}
apply
while inotifywait -q -e close_write "$STATE" >/dev/null 2>&1; do apply; done
