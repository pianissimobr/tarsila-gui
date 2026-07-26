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
# O lock impede duas aplicacoes simultaneas. ARMADILHA: sem o -w ele espera
# PARA SEMPRE, e sem fechar o fd nos filhos o polybar (que e de vida longa e
# nasce do tarsila-ob-bar.sh la embaixo) HERDA o fd 9 e segura o lock enquanto
# viver. Resultado do bug: a 1a troca de tema funcionava e todas as seguintes
# ficavam penduradas. Por isso: espera limitada aqui e 9>&- na chamada do bar.
exec 9>"$CFG/.tema-apply.lock"
flock -w 10 9 || echo "aviso: outra aplicacao de tema em curso; seguindo" >&2
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
# 9>&- : nao deixa o polybar herdar o lock (ver comentario acima)
/usr/local/bin/tarsila-ob-bar.sh 9>&-
