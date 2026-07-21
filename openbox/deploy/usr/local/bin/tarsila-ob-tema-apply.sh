#!/bin/bash
# Aplica um tema visual na sessão Openbox: wallpaper (feh) + tema do Plank
# (dconf) + cores da top bar (via tarsila-ob-bar.sh) + persiste a escolha.
# Muito mais simples que a versão XFCE: sem recolor de SVG, sem gtk.css,
# sem xfconf — a cor da barra E do texto é a cor do polybar (TB_BG/TB_FG).
# Interface idêntica: tarsila-ob-tema-apply.sh <tema> [imagem]
set -u
TEMA="${1:-padrao}"; IMAGEM="${2:-}"
WALLDIR=/usr/share/tarsila/wallpapers
PADRAO_WP=/usr/share/backgrounds/tarsila-wallpaper.png
CFG="$HOME/.config/tarsila"; mkdir -p "$CFG"
exec 9>"$CFG/.tema-apply.lock"; flock 9
case "$TEMA" in
  padrao)      WP=$PADRAO_WP;                   DOCK=Tarsila-Gelo ;;
  maritimo)    WP=$WALLDIR/tema-maritimo.png;   DOCK=Tarsila-Maritimo ;;
  escuro)      WP=$WALLDIR/tema-escuro.png;     DOCK=Tarsila-Escuro ;;
  brasileiro)  WP=$WALLDIR/tema-brasileiro.png; DOCK=Tarsila-Brasileiro ;;
  personalizado)
    [ -n "$IMAGEM" ] && [ -f "$IMAGEM" ] || { echo "uso: $0 personalizado <imagem>" >&2; exit 1; }
    mkdir -p "$HOME/.local/share/tarsila"
    WP="$HOME/.local/share/tarsila/wallpaper-pessoal.${IMAGEM##*.}"; cp -f "$IMAGEM" "$WP" ;;
  *) echo "tema desconhecido: $TEMA" >&2; exit 1 ;;
esac
[ "$TEMA" = personalizado ] && DOCK=Tarsila-Gelo
feh --no-fehbg --bg-fill "$WP" 2>/dev/null
dconf write /net/launchpad/plank/docks/dock1/theme "'$DOCK'" 2>/dev/null || true
echo "$TEMA" > "$CFG/tema"; echo "$WP" > "$CFG/tema-wallpaper"
/usr/local/bin/tarsila-ob-bar.sh
