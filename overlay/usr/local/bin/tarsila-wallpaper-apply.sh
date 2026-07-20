#!/bin/bash
# Autostart: adapta o visual a resolucao REAL da TV e aplica o wallpaper.
# A tvbox nao troca de resolucao em tempo de execucao - o modo e unico e
# negociado com a TV no boot (720p/768/1080p/4K variam por aparelho),
# entao TUDO que depende de tamanho de tela e recalculado aqui, a cada
# login:
#   1) wallpaper do tema salvo (~/.config/tarsila/tema-wallpaper)
#   2) painel das bolinhas (panel-2) recentralizado no meio da tela
#      (a posicao dele e um X absoluto - fixo, quebraria em outra TV)
#   3) "modo TV grande": barra, icones e dock maiores em telas altas
#      (pixels fixos pensados p/ 768p ficam minusculos em 4K)

# ---- resolucao real ----
GEOM=$(xrandr --query 2>/dev/null \
  | sed -n 's/.* connected \(primary \)\?\([0-9]\+x[0-9]\+\)+.*/\2/p' | head -1)
W=${GEOM%x*}
H=${GEOM#*x}
if [ -z "$W" ] || [ -z "$H" ]; then W=1366; H=768; fi

# ---- 1) wallpaper (respeita o tema escolhido no Ajustes) ----
WALLPAPER=""
if [ -f "$HOME/.config/tarsila/tema-wallpaper" ]; then
  read -r WALLPAPER < "$HOME/.config/tarsila/tema-wallpaper"
fi
[ -n "$WALLPAPER" ] && [ -f "$WALLPAPER" ] || WALLPAPER=/usr/share/backgrounds/tarsila-wallpaper.png

for out in $(xrandr --query 2>/dev/null | awk '/ connected/{print $1}'); do
  base="/backdrop/screen0/monitor${out}/workspace0"
  xfconf-query -c xfce4-desktop -p "$base/last-image" -n -t string -s "$WALLPAPER" 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/last-image" -s "$WALLPAPER" 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/image-style" -n -t int -s 5 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/image-style" -s 5 2>/dev/null
done

# ---- 2) bolinhas no centro exato desta tela ----
# (para o panel-2 flutuante, o x da posicao e o CENTRO da janela)
xfconf-query -c xfce4-panel -p /panels/panel-2/position -s "p=0;x=$((W / 2));y=0" 2>/dev/null

# ---- 3) tamanhos por faixa de altura de tela ----
if   [ "$H" -gt 1600 ]; then PS=52; PI=32; PLK=104   # 4K
elif [ "$H" -gt  900 ]; then PS=36; PI=22; PLK=72    # 1080p/1440p
else                         PS=26; PI=16; PLK=52    # 720p/768 (design base)
fi
for p in panel-1 panel-2; do
  xfconf-query -c xfce4-panel -p "/panels/$p/size" -s "$PS" 2>/dev/null
  xfconf-query -c xfce4-panel -p "/panels/$p/icon-size" -s "$PI" 2>/dev/null
done
atual=$(dconf read /net/launchpad/plank/docks/dock1/icon-size 2>/dev/null)
if [ "$atual" != "$PLK" ]; then
  dconf write /net/launchpad/plank/docks/dock1/icon-size "$PLK" 2>/dev/null
fi

# Em alguns boots o xfdesktop nao redesenha sozinho a tempo (corrida com
# outros autostarts). Forca o redesenho explicitamente como reforco.
sleep 2
xfdesktop --reload >/dev/null 2>&1
