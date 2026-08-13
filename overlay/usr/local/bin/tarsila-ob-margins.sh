#!/bin/bash
# Sincroniza a margem superior do Openbox com a altura real do polybar.
# Reforco estatico (rc.xml <margins><top>); o arraste ao vivo e corrigido
# por tarsila-monitor.sh (clamp_below_topbar).
CFG="$HOME/.config/tarsila"
RC="$HOME/.config/openbox/rc.xml"
H=34
[ -f "$CFG/bar-height" ] && read -r H < "$CFG/bar-height"
[ -f "$RC" ] || exit 0
# Ja esta com a margem certa? Nao reconfigurar: openbox --reconfigure
# re-le o rc.xml inteiro e reaplica as regras de todas as janelas. No login
# e na troca de tema em que a altura da barra NAO mudou, isso era trabalho
# (e um reparse visivel) sem necessidade.
atual=$(sed -n 's|.*<top>\([0-9]*\)</top>.*|\1|p' "$RC" | head -1)
[ "$atual" = "$H" ] && exit 0
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
sed -i "s|<top>[0-9]*</top>|<top>${H}</top>|" "$RC"
openbox --reconfigure 2>/dev/null || true
