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

LAUNCHERS_DIR="$HOME/.config/plank/dock1/launchers"
[ -d "$LAUNCHERS_DIR" ] || exit 0

# "Ver mais aplicativos" (o item que abre o AppFinder) precisa ficar sempre
# na extremidade direita do dock, com qualquer app fixado pelo usuario
# aparecendo a esquerda dele. Identificamos o item pelo Launcher= (conteudo),
# nao pelo nome do arquivo, para nao depender de numeracao/renomeacao.
VERMAIS_DESKTOP="/usr/share/tarsila/applications/vermais-tarsila.desktop"

items=""
vermais_item=""
for f in "$LAUNCHERS_DIR"/*.dockitem; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  if grep -q "^Launcher=file://$VERMAIS_DESKTOP\$" "$f" 2>/dev/null; then
    vermais_item="$base"
    continue
  fi
  items+="'$base', "
done
[ -n "$vermais_item" ] && items+="'$vermais_item', "
[ -n "$items" ] || exit 0
items="[${items%, }]"

dconf write /net/launchpad/plank/docks/dock1/dock-items "$items"
dconf write /net/launchpad/plank/docks/dock1/theme "'Tarsila'"
dconf write /net/launchpad/plank/docks/dock1/position "'bottom'"
# visivel com janelas flutuantes; some quando maximizado; reaparece na borda
# inferior (pressure-reveal) e some 2s depois que o mouse sai da regiao do dock
dconf write /net/launchpad/plank/docks/dock1/hide-mode "'dodge-maximized'"
dconf write /net/launchpad/plank/docks/dock1/pressure-reveal true
dconf write /net/launchpad/plank/docks/dock1/hide-delay 2000
dconf write /net/launchpad/plank/docks/dock1/unhide-delay 0
dconf write /net/launchpad/plank/docks/dock1/icon-size 52
dconf write /net/launchpad/plank/docks/dock1/pinned-only true
dconf write /net/launchpad/plank/docks/dock1/lock-items true
