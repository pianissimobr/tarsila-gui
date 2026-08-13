#!/bin/bash
# SEGUIDOR: 3 bolinhas de workspace lógico. Lê o estado calculado pelo
# líder (MAX), o wincount do tarsila-monitor e o workspace lógico (1/2/3).
# Clique reaproveita os tarsila-goto*.sh existentes (sem alteração).
# Cores vêm do tema via env (TB_FG aceso, TB_DIM apagado).
RT="${XDG_RUNTIME_DIR:-/tmp}"
STATE="$RT/tarsila-topbar-state.txt"; LOG="$RT/tarsila-state"; WC="$RT/tarsila-wincount"
ON="${TB_FG:-#ffffff}"; OFF="${TB_DIM:-#5a7c86}"
dot(){ printf '%%{A1:%s:}%%{T4}%%{F%s}●%%{F-}%%{T-}%%{A}' "$1" "$2"; }
emit(){
  MAX=0; [ -f "$STATE" ] && MAX=$(sed -n 's/^MAX=//p' "$STATE")
  n=""; [ -f "$WC" ] && read -r n < "$WC"
  [ -z "$n" ] && n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|polybar|xfdesktop' | wc -l)
  st=""; [ -f "$LOG" ] && read -r st < "$LOG"
  c1=$OFF; c2=$OFF; c3=$OFF
  if [ "${n:-0}" -eq 0 ] || { [ "$MAX" = 0 ] && [ "$st" = 1 ]; }; then c1=$ON; fi
  if [ "${n:-0}" -gt 0 ] && [ "$MAX" = 0 ] && [ "$st" != 1 ]; then c2=$ON; fi
  if [ "${n:-0}" -gt 0 ] && [ "$MAX" = 1 ]; then c3=$ON; fi
  printf '%s %s %s\n' \
    "$(dot /usr/local/bin/tarsila-goto1.sh "$c1")" \
    "$(dot /usr/local/bin/tarsila-goto2.sh "$c2")" \
    "$(dot /usr/local/bin/tarsila-goto3.sh "$c3")"
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
