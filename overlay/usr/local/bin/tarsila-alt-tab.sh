#!/bin/bash
# Alt+Tab customizado: cicla 1 -> 2 -> 3 -> 1 entre as janelas de
# trabalho que existirem (nao faz nada se nao houver apps abertos).
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-state"
n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|xfce4-panel|xfdesktop' | wc -l)

if [ "$n" -eq 0 ]; then
  exit 0
fi

id=$(xdotool getactivewindow 2>/dev/null)
maximized=0
if [ -n "$id" ] && xprop -id "$id" _NET_WM_STATE 2>/dev/null | grep -q MAXIMIZED; then
  maximized=1
fi
state=$(cat "$STATE_FILE" 2>/dev/null)

if [ "$maximized" -eq 1 ]; then
  current=3
elif [ "$state" = "1" ]; then
  current=1
else
  current=2
fi

next=$((current % 3 + 1))
case "$next" in
  1) /usr/local/bin/tarsila-goto1.sh ;;
  2) /usr/local/bin/tarsila-goto2.sh ;;
  3) /usr/local/bin/tarsila-goto3.sh ;;
esac
