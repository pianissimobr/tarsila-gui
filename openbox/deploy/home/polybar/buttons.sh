#!/bin/bash
# SEGUIDOR: botoes fechar/restaurar. So aparecem com MAX=1 (bolinha 3).
# Icones Font Awesome 4 (bytes UTF-8): times (f00d), compress (f066).
RT="${XDG_RUNTIME_DIR:-/tmp}"; STATE="$RT/tarsila-topbar-state.txt"
CLOSE=$(printf '\xef\x80\x8d')
RESTORE=$(printf '\xef\x81\xa6')
emit(){
  MAX=0; ID=""
  if [ -f "$STATE" ]; then MAX=$(sed -n 's/^MAX=//p' "$STATE"); ID=$(sed -n 's/^ID=//p' "$STATE"); fi
  if [ "$MAX" = 1 ] && [ -n "$ID" ]; then
    printf '%%{A1:wmctrl -ic %s:}%%{T3}%s%%{T-}%%{A}   %%{A1:/usr/local/bin/tarsila-goto2.sh:}%%{T3}%s%%{T-}%%{A}\n' "$ID" "$CLOSE" "$RESTORE"
  else
    echo " "
  fi
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
