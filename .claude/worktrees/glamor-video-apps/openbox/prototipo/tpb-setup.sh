#!/bin/bash
# Cria o protótipo da top bar Tarsila em polybar (rodando sob Openbox),
# reaproveitando os state files e os tarsila-goto*.sh existentes.
set -e
D=/home/alan/.config/tpb
mkdir -p "$D"

# ---------- config.ini ----------
cat > "$D/config.ini" <<'CFG'
[colors]
bg = #194350
fg = #ffffff
dim = #5a7c86

[bar/tarsila]
width = 100%
height = 34
background = ${colors.bg}
foreground = ${colors.fg}
font-0 = DejaVu Sans:size=11;3
font-1 = DejaVu Sans:style=Bold:size=11;3
font-2 = Noto Sans Symbols2:size=13;3
modules-left = title buttons
modules-center = dots
modules-right = sound netw date power
tray-position = right
tray-maxsize = 18
padding-right = 2
module-margin = 2
enable-ipc = true

[module/title]
type = custom/script
exec = /home/alan/.config/tpb/title.sh
tail = true

[module/buttons]
type = custom/script
exec = /home/alan/.config/tpb/buttons.sh
tail = true

[module/dots]
type = custom/script
exec = /home/alan/.config/tpb/dots.sh
tail = true

[module/sound]
type = internal/pulseaudio
format-volume = <label-volume>
label-volume = %{T3}♪%{T-} %percentage%%
label-muted = %{T3}♪%{T-} —

[module/netw]
type = custom/script
exec = /home/alan/.config/tpb/net.sh
interval = 5
click-left = nm-connection-editor

[module/date]
type = internal/date
interval = 10
date = %H:%M
date-alt = %a %d/%m
label = %date%

[module/power]
type = custom/text
label = %{T3}⏻%{T-}
click-left = openbox --exit
CFG

# ---------- title.sh (LÍDER: computa MAX/ID e grava o state file) ----------
cat > "$D/title.sh" <<'SH'
#!/bin/bash
export DISPLAY=:0
RT="${XDG_RUNTIME_DIR:-/tmp}"; STATE="$RT/tarsila-topbar-state.txt"
emit(){
  id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$id" ] && xprop -id "$id" _NET_WM_STATE 2>/dev/null | grep -q MAXIMIZED; then
    name=$(xdotool getwindowname "$id" 2>/dev/null)
    wmclass=$(xprop -id "$id" WM_CLASS 2>/dev/null | sed -n 's/.*"\([^"]*\)", "[^"]*".*/\1/p')
    case "$wmclass" in
      Thunar) name=Arquivos;; galculator) name=Calculadora;;
      tarsila-config) name=Ajustes;; qpdfview) name="Leitor de PDF";;
    esac
    [ ${#name} -gt 60 ] && name="${name:0:60}…"
    printf 'MAX=1\nID=%s\n' "$id" > "$STATE"
    echo "%{T2}   $name%{T-}"
  else
    printf 'MAX=0\nID=\n' > "$STATE"
    echo " "
  fi
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
SH

# ---------- dots.sh (SEGUIDOR: lê state + wincount + workspace lógico) ----------
cat > "$D/dots.sh" <<'SH'
#!/bin/bash
export DISPLAY=:0
RT="${XDG_RUNTIME_DIR:-/tmp}"
STATE="$RT/tarsila-topbar-state.txt"; LOG="$RT/tarsila-state"; WC="$RT/tarsila-wincount"
ON="#ffffff"; OFF="#5a7c86"
emit(){
  MAX=0; [ -f "$STATE" ] && MAX=$(sed -n 's/^MAX=//p' "$STATE")
  n=""; [ -f "$WC" ] && read -r n < "$WC"
  [ -z "$n" ] && n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|polybar|xfdesktop' | wc -l)
  st=""; [ -f "$LOG" ] && read -r st < "$LOG"
  d1=$OFF; d2=$OFF; d3=$OFF
  if [ "${n:-0}" -eq 0 ] || { [ "$MAX" = 0 ] && [ "$st" = 1 ]; }; then d1=$ON; fi
  if [ "${n:-0}" -gt 0 ] && [ "$MAX" = 0 ] && [ "$st" != 1 ]; then d2=$ON; fi
  if [ "${n:-0}" -gt 0 ] && [ "$MAX" = 1 ]; then d3=$ON; fi
  echo "%{A1:/usr/local/bin/tarsila-goto1.sh:}%{F$d1}●%{F-}%{A} %{A1:/usr/local/bin/tarsila-goto2.sh:}%{F$d2}●%{F-}%{A} %{A1:/usr/local/bin/tarsila-goto3.sh:}%{F$d3}●%{F-}%{A}"
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
SH

# ---------- buttons.sh (SEGUIDOR: fechar/restaurar só com MAX=1) ----------
cat > "$D/buttons.sh" <<'SH'
#!/bin/bash
export DISPLAY=:0
RT="${XDG_RUNTIME_DIR:-/tmp}"; STATE="$RT/tarsila-topbar-state.txt"
emit(){
  MAX=0; ID=""
  if [ -f "$STATE" ]; then MAX=$(sed -n 's/^MAX=//p' "$STATE"); ID=$(sed -n 's/^ID=//p' "$STATE"); fi
  if [ "$MAX" = 1 ] && [ -n "$ID" ]; then
    echo "%{A1:wmctrl -ic $ID:}✕%{A}   %{A1:/usr/local/bin/tarsila-goto2.sh:}▭%{A}"
  else
    echo " "
  fi
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
SH

# ---------- net.sh ----------
cat > "$D/net.sh" <<'SH'
#!/bin/bash
st=$(nmcli -t -f TYPE,STATE device 2>/dev/null)
if echo "$st" | grep -qE '^(ethernet|wifi):connected'; then
  echo "%{F#8fd18f}●%{F-}"
else
  echo "%{F#d18f8f}●%{F-}"
fi
SH

# ---------- run.sh (sobe a sessão Openbox+polybar de teste) ----------
cat > "$D/run.sh" <<'SH'
#!/bin/bash
export DISPLAY=:0 XDG_RUNTIME_DIR=/run/user/1003 XDG_SESSION_TYPE=x11
eval "$(dbus-launch --sh-syntax)"; export DBUS_SESSION_BUS_ADDRESS
touch "$XDG_RUNTIME_DIR/tarsila-state" "$XDG_RUNTIME_DIR/tarsila-topbar-state.txt"
echo 2 > "$XDG_RUNTIME_DIR/tarsila-state"
openbox & sleep 1.5
nitrogen --restore >/dev/null 2>&1 &
plank >/dev/null 2>&1 &
polybar -c /home/alan/.config/tpb/config.ini tarsila >/tmp/polybar.log 2>&1 &
sleep 2
xterm -T "Bloco de Notas de Teste" -geometry 80x24+120+120 >/dev/null 2>&1 &
wait
SH

chmod +x "$D"/*.sh
chown -R alan:alan "$D"
echo "SETUP OK: $(ls "$D")"
