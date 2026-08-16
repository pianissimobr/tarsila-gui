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

# A ORDEM DA DOCK, EM TRES BLOCOS
#
#   [ aplicativos ]  [ Ver mais ]  [ indicadores ]
#
# Os indicadores (volume, rede, calendario, sistema, limpar, energia) sao o
# que morava no canto superior direito da barra de cima. Eles ficam na
# extremidade direita porque e onde ja estavam -- o usuario procura status no
# mesmo canto de antes, so que embaixo.
#
# "Ver mais aplicativos" fecha o bloco de aplicativos. Ate aqui ele era o
# ultimo item de todos; deixou de ser quando os indicadores chegaram, porque
# ele pertence ao grupo dos aplicativos, nao ao de status.
#
# Os dois blocos fixos sao identificados pelo Launcher= (conteudo), nao pelo
# nome do arquivo, para nao depender de numeracao nem de renomeacao.
APPS_DIR="/usr/share/tarsila/applications"
VERMAIS_DESKTOP="$APPS_DIR/vermais-tarsila.desktop"
INDICADORES="volume rede calendario sistema limpar energia"

item_de() {   # <nome-base do .desktop> -> nome do .dockitem que aponta pra ele
  local alvo="$1" f
  for f in "$LAUNCHERS_DIR"/*.dockitem; do
    [ -e "$f" ] || continue
    grep -q "^Launcher=file://$APPS_DIR/$alvo\.desktop\$" "$f" 2>/dev/null \
      && { basename "$f"; return 0; }
  done
  return 1
}

# Tudo que nao e Ver mais nem indicador entra no primeiro bloco, na ordem
# alfabetica dos arquivos (que e a ordem numerica do prefixo 01-, 02-...).
fixos=" "
for ind in $INDICADORES; do
  b=$(item_de "$ind-tarsila" || true); [ -n "$b" ] && fixos+="$b "
done
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
for ind in $INDICADORES; do
  b=$(item_de "$ind-tarsila" || true); [ -n "$b" ] && items+="'$b', "
done
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
