#!/bin/bash
# Autostart: reaplica ordem/tema/comportamento do dock (Plank) via dconf
# ANTES do Plank abrir (ver autostart/plank.desktop, que roda este script e
# so entao da "exec plank"). Necessario porque o Plank pode reinicializar
# as proprias preferencias com os padroes de fabrica em certos cenarios de
# primeira execucao, sobrescrevendo o que foi gravado por fora durante o
# provisionamento (mesma classe de problema ja visto com o wallpaper -
# ver tarsila-wallpaper-apply.sh). Reforcar aqui, a cada login, torna a
# ordem correta independente disso acontecer de novo.
set -euo pipefail
. /usr/local/lib/tarsila/comum.sh

LAUNCHERS_DIR="$HOME/.config/plank/dock1/launchers"
[ -d "$LAUNCHERS_DIR" ] || exit 0

# A ORDEM DA DOCK, EM DOIS BLOCOS
#
#   [ aplicativos ]  [ Ver mais ]
#
# "Ver mais aplicativos" fecha a fila e e sempre o ultimo item.
#
# Entre 15/08 e 17/08/2026 havia um terceiro bloco na extremidade direita: os
# seis indicadores (volume, rede, calendario, sistema, limpar, energia), que
# tinham descido para ca quando a polybar foi removida. Em 16/08 a barra de
# cima voltou, em GTK, com os mesmos seis -- e ninguem tirou os da Dock. Ficaram
# duplicados por um dia: seis icones ocupando a Dock, que e justamente onde
# falta espaco, para fazer o que a barra ja faz dois centimetros acima.
#
# O bloco fixo e identificado pelo Launcher= (conteudo), nao pelo nome do
# arquivo, para nao depender de numeracao nem de renomeacao.
APPS_DIR="/usr/share/tarsila/applications"
VERMAIS_DESKTOP="$APPS_DIR/vermais-tarsila.desktop"

item_de() {   # <nome-base do .desktop> -> nome do .dockitem que aponta pra ele
  local alvo="$1" f
  for f in "$LAUNCHERS_DIR"/*.dockitem; do
    [ -e "$f" ] || continue
    grep -q "^Launcher=file://$APPS_DIR/$alvo\.desktop\$" "$f" 2>/dev/null \
      && { basename "$f"; return 0; }
  done
  return 1
}

# Tudo que nao e o Ver mais entra no primeiro bloco, na ordem
# alfabetica dos arquivos (que e a ordem numerica do prefixo 01-, 02-...).
fixos=" "
b=$(item_de "vermais-tarsila" || true); vermais_item="${b:-}"
[ -n "$vermais_item" ] && fixos+="$vermais_item "

items=""
for f in "$LAUNCHERS_DIR"/*.dockitem; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  case "$fixos" in *" $base "*) continue ;; esac
  items+="'$base', "
done
[ -n "$vermais_item" ] && items+="'$vermais_item', "
[ -n "$items" ] || exit 0
items="[${items%, }]"

dconf write /net/launchpad/plank/docks/dock1/dock-items "$items"
# NAO fixar o tema aqui: este script roda a CADA login, logo antes do plank
# subir, e gravar 'Tarsila' fixo desfazia a escolha do usuario -- a Dock voltava
# sempre ao tema base escuro. Agora deriva do tema salvo, e assim a cor da Dock
# sobrevive ao reinicio. Mapa igual ao do tarsila-ob-tema-apply.sh.
# O mapa tema -> tema da Dock mora no comum.sh: era o mesmo case escrito
# aqui e no tarsila-tema-apply.sh (05/08).
dconf write /net/launchpad/plank/docks/dock1/theme "'$(dock_do_tema "$(tema_salvo)")'"
dconf write /net/launchpad/plank/docks/dock1/position "'bottom'"
# visivel com janelas flutuantes; some quando maximizado; reaparece na borda
# inferior (pressure-reveal) e some depois que o mouse sai da regiao do dock.
# O hide-delay era 2000: a Dock ficava 2s por cima da janela recem-maximizada
# antes de sair. Em 0 ela sai junto com o maximizar -- a espera so atrapalhava
# quem maximizou justamente para ganhar tela.
dconf write /net/launchpad/plank/docks/dock1/hide-mode "'dodge-maximized'"
dconf write /net/launchpad/plank/docks/dock1/pressure-reveal true
dconf write /net/launchpad/plank/docks/dock1/hide-delay 0
dconf write /net/launchpad/plank/docks/dock1/unhide-delay 0
# Tamanho pela resolucao, nao 52 fixo. Este script roda a cada login logo
# antes do Plank; o 52 escrito aqui desfazia o valor que o
# tarsila-wallpaper-apply.sh calcula da altura da tela -- numa TV de 1080p
# ou 4K o icone voltava sozinho ao tamanho pensado para 768p (05/08).
dconf write /net/launchpad/plank/docks/dock1/icon-size "$(icone_dock)"
dconf write /net/launchpad/plank/docks/dock1/pinned-only true
dconf write /net/launchpad/plank/docks/dock1/lock-items true
