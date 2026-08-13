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
# NAO fixar o tema aqui: este script roda a CADA login, logo antes do plank
# subir, e gravar 'Tarsila' fixo desfazia a escolha do usuario -- a Dock voltava
# sempre ao tema base escuro. Agora deriva do tema salvo, e assim a cor da Dock
# sobrevive ao reinicio. Mapa igual ao do tarsila-ob-tema-apply.sh.
_tema=padrao; [ -r "$HOME/.config/tarsila/tema" ] && read -r _tema < "$HOME/.config/tarsila/tema"
case "$_tema" in
  maritimo)   _dock=Tarsila-Maritimo ;;
  escuro)     _dock=Tarsila-Escuro ;;
  brasileiro) _dock=Tarsila-Brasileiro ;;
  *)          _dock=Tarsila ;;      # padrao e personalizado
esac
dconf write /net/launchpad/plank/docks/dock1/theme "'$_dock'"
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
dconf write /net/launchpad/plank/docks/dock1/icon-size 52
dconf write /net/launchpad/plank/docks/dock1/pinned-only true
dconf write /net/launchpad/plank/docks/dock1/lock-items true
