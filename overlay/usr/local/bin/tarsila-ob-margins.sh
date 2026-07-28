#!/bin/bash
# Sincroniza a margem superior do Openbox com a altura real do polybar.
# Reforco estatico (rc.xml <margins><top>); o arraste ao vivo e corrigido
# por tarsila-monitor.sh (clamp_below_topbar).
CFG="$HOME/.config/tarsila"
RC="$HOME/.config/openbox/rc.xml"
H=34
[ -f "$CFG/bar-height" ] && read -r H < "$CFG/bar-height"
[ -f "$RC" ] || exit 0
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
sed -i "s|<top>[0-9]*</top>|<top>${H}</top>|" "$RC"
openbox --reconfigure 2>/dev/null || true
