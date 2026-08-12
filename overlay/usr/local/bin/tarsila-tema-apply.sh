#!/bin/bash
# Aplica um tema visual: papel de parede + tema da Dock + cores da barra de
# cima, e grava a escolha para o proximo login. Chamado pela pagina
# Aparencia do Ajustes.
#
#     tarsila-tema-apply.sh padrao | maritimo | escuro | brasileiro
#     tarsila-tema-apply.sh personalizado <imagem>
#
# UM ARQUIVO SO (05/08). Existiam dois, com o mesmo nome de comando por
# fora: este, herdado do XFCE (xfconf-query, gtk.css, "xfce4-panel -r",
# recolor de SVG -- 140 linhas), e o tarsila-ob-tema-apply.sh, escrito para
# a sessao Openbox. A primeira linha do antigo desviava para o outro:
#
#     case "${XDG_CURRENT_DESKTOP:-}" in *Openbox*) exec ...ob-tema... ;; esac
#
# Esse desvio dependia de uma variavel de ambiente que esta sessao nao
# exporta. O proprio sistema ja sabia que nao dava para confiar nela -- o
# autostart do Openbox cria um arquivo-marcador em XDG_RUNTIME_DIR com o
# comentario "guard robusto ...; nao depende de env" --, e o
# tarsila-topbar-refresh.sh checava as duas coisas. Aqui, se o desvio nao
# pegasse, o Ajustes rodava o caminho do XFCE dentro do Openbox: xfconf sem
# xfconf, e um "xfce4-panel -r" que sobe um painel do XFCE por cima da area
# de trabalho.
#
# O caminho do XFCE nao existe mais: nao ha sessao XFCE nesta imagem. O
# nome antigo tarsila-ob-tema-apply.sh continua valendo (link para este
# arquivo).
set -u
. /usr/local/lib/tarsila/comum.sh

TEMA="${1:-padrao}"
IMAGEM="${2:-}"
mkdir -p "$TARSILA_CFG"

# ARMADILHA JA PAGA: sem o -w o flock espera para sempre, e sem fechar o
# descritor nos filhos o polybar -- que e de vida longa e nasce la embaixo,
# no tarsila-ob-bar.sh -- HERDA o fd 9 e segura a tranca enquanto viver.
# Sintoma: a primeira troca de tema funcionava e todas as seguintes ficavam
# penduradas. Por isso: espera limitada aqui, e 9>&- na chamada da barra.
exec 9>"$TARSILA_CFG/.tema-apply.lock"
flock -w 10 9 || echo "aviso: outra aplicacao de tema em curso; seguindo" >&2

case "$TEMA" in
  padrao|maritimo|escuro|brasileiro)
    WP=$(wallpaper_do_tema "$TEMA")
    ;;
  personalizado)
    [ -n "$IMAGEM" ] && [ -f "$IMAGEM" ] || { echo "uso: $0 personalizado <imagem>" >&2; exit 1; }
    # Copia a imagem: se o usuario apagar o original (pendrive, Downloads),
    # o papel de parede continua existindo.
    mkdir -p "$HOME/.local/share/tarsila"
    WP="$HOME/.local/share/tarsila/wallpaper-pessoal.${IMAGEM##*.}"
    cp -f "$IMAGEM" "$WP"
    ;;
  *)
    echo "tema desconhecido: $TEMA" >&2; exit 1 ;;
esac

pinta_fundo "$WP" || echo "aviso: nao consegui pintar o papel de parede" >&2

# O Plank observa esta chave e recarrega o tema sozinho, sem reiniciar.
dconf write /net/launchpad/plank/docks/dock1/theme "'$(dock_do_tema "$TEMA")'" 2>/dev/null || true

printf '%s\n' "$TEMA" > "$TARSILA_CFG/tema"
printf '%s\n' "$WP"   > "$TARSILA_CFG/tema-wallpaper"

# 9>&- : nao deixa o polybar herdar a tranca (ver comentario acima).
/usr/local/bin/tarsila-ob-bar.sh 9>&-
