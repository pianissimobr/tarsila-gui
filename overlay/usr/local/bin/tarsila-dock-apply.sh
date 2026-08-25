#!/bin/bash
# Autostart: grava a ORDEM da Dock, e so isso.
#
# Roda a cada login, logo antes da Dock subir. O nome e a heranca sao do tempo
# do Plank -- ele reinicializava as proprias preferencias em certos cenarios de
# primeira execucao, e este script existia para reimpor tudo por fora. Do "tudo"
# sobrou uma chave; ver o bloco no fim do arquivo.
set -euo pipefail

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

# NOVE ESCRITAS DE DCONF SAIRAM DAQUI EM 17/08/2026
#
# Este script gravava, alem da ordem acima: theme, position, hide-mode,
# pressure-reveal, hide-delay, unhide-delay, icon-size, pinned-only e
# lock-items. Todas eram preferencias do PLANK, que saiu em 16/08.
#
# A Dock em GTK nao le dconf. A cor esta no codigo, o tamanho do icone sai da
# altura da tela e da quantidade de itens (metricas() no tarsila-dock), e
# esconder-se ao maximizar ela decide sozinha, lendo tarsila-topbar-state.txt.
# Eram nove escritas por login para ninguem.
#
# A UNICA que ficou e dock-items, e mesmo essa nao e lida pela Dock -- que
# ordena pelo nome do arquivo .dockitem -- e sim pelo tarsila-dock-manager,
# para mostrar a ordem atual na janela "Gerenciar Dock".
#
# CONSEQUENCIA CONHECIDA, ainda em aberto: com a escrita de `theme` fora, trocar
# o tema no painel de Ajustes nao muda mais a cor da Dock. Ja nao mudava -- a
# Dock nunca leu essa chave --, mas agora esta explicito. Para a cor voltar a
# obedecer ao tema, quem tem de mudar e o tarsila-dock, lendo tema_salvo() como
# a tarsila-barra faz. Ver docs/historico/DIAGNOSTICO-BIN.md, defeito 5.
