#!/bin/bash
# Após soltar botão esquerdo: se o topo está sob a top bar E a borda
# esquerda encosta num módulo da polybar (relógio, ícones…), desce no Y.

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
HITBOXES="$RUNTIME/tarsila-polybar-hitboxes.txt"
DRAG_WIN="$RUNTIME/tarsila-clamp-drag-win.txt"
BAR_CFG="$HOME/.config/tarsila/bar-height"

bar_h=34
[ -f "$BAR_CFG" ] && read -r bar_h < "$BAR_CFG"

W=""
[ -f "$DRAG_WIN" ] && read -r W < "$DRAG_WIN"
[ -z "$W" ] && W=$(xdotool getactivewindow 2>/dev/null)
[ -z "$W" ] && exit 0

# Ignora decoração da sessão / barra / dock
cls=$(xprop -id "$W" WM_CLASS 2>/dev/null)
case "$cls" in
  *polybar*|*Polybar*|*Plank*|*plank*|*tarsila-tela-estados*|*xfdesktop*|*Desktop*|*Openbox*)
    exit 0 ;;
esac

xprop -id "$W" _NET_WM_STATE 2>/dev/null | grep -q MAXIMIZED && exit 0

geom=$(xdotool getwindowgeometry --shell "$W" 2>/dev/null) || exit 0
eval "$geom"

ext=$(xprop -id "$W" _NET_FRAME_EXTENTS 2>/dev/null | grep -oE '[0-9]+, [0-9]+, [0-9]+, [0-9]+')
ml=$(echo "$ext" | awk -F', ' '{print $1}')
mr=$(echo "$ext" | awk -F', ' '{print $2}')
mt=$(echo "$ext" | awk -F', ' '{print $3}')
: "${ml:=0}"; : "${mr:=0}"; : "${mt:=0}"

top_frame=$((Y - mt))

# Topo ainda não invadiu a faixa da top bar
[ "$top_frame" -lt "$bar_h" ] || exit 0

# Borda esquerda do FRAME visível (client X menos a margem de decoração
# à esquerda) — usar $X puro subestima o quanto a janela já invadiu a
# hitbox quando o tema tem borda/moldura.
left_edge=$((X - ml))

[ -f "$HITBOXES" ] || exit 0

overlap=0
while read -r a b c d e; do
  case "$a" in
    ''|'#'*) continue ;;
  esac
  hx=$a; hw=$c
  he=$((hx + hw))
  # Só a borda esquerda encostando na área recortada do módulo
  if [ "$left_edge" -ge "$hx" ] && [ "$left_edge" -lt "$he" ]; then
    overlap=1
    break
  fi
done < "$HITBOXES"

[ "$overlap" -eq 1 ] || exit 0

sobra=$((top_frame - bar_h))
xdotool windowmove "$W" "$X" $((Y - sobra)) 2>/dev/null
