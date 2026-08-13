#!/bin/bash
# Autostart da sessão Openbox: aplica o wallpaper do tema (feh), adapta o
# tamanho dos ícones do Plank à resolução real e sobe a top bar já com a
# geometria/cor certas. Equivale ao tarsila-wallpaper-apply.sh do XFCE,
# mas sem xfconf/xfdesktop.
CFG="$HOME/.config/tarsila"
WP=""; [ -f "$CFG/tema-wallpaper" ] && read -r WP < "$CFG/tema-wallpaper"
[ -n "$WP" ] && [ -f "$WP" ] || WP=/usr/share/backgrounds/tarsila-wallpaper.png
feh --no-fehbg --bg-fill "$WP" 2>/dev/null

H=$(xrandr --query 2>/dev/null | sed -n 's/.* connected \(primary \)\?[0-9]\+x\([0-9]\+\)+.*/\2/p' | head -1)
[ -z "$H" ] && H=768
if   [ "$H" -gt 1600 ]; then PLK=104
elif [ "$H" -gt 900 ];  then PLK=72
else                         PLK=52
fi
cur=$(dconf read /net/launchpad/plank/docks/dock1/icon-size 2>/dev/null)
[ "$cur" != "$PLK" ] && dconf write /net/launchpad/plank/docks/dock1/icon-size "$PLK" 2>/dev/null

# sobe a top bar (lê tema + resolução e exporta TB_*)
/usr/local/bin/tarsila-ob-bar.sh
