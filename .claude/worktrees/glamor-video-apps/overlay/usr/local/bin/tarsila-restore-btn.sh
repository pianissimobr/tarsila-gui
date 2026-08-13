#!/bin/bash
# Botao "restaurar" no top bar: so aparece com um app maximizado (bolinha
# 3). Clique volta para a janela de trabalho 2 (flutuante). Sempre emite
# uma tag <img> (mesmo vazia/invisivel) - o genmon mantem o ultimo icone
# renderizado se a saida vier sem nenhuma tag.
#
# "Seguidor": le o estado ja calculado por tarsila-title.sh (lider) em vez
# de rodar xdotool/xprop de novo, para acompanhar o lider sem atraso (ver
# comentario em tarsila-title.sh).
RESTORE="$HOME/.cache/tarsila/topbar/restore.svg"; [ -f "$RESTORE" ] || RESTORE=/usr/local/share/tarsila/restore-square-padded.svg
BLANK=/usr/local/share/tarsila/invisible.svg
STATE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
MAX=0
if [ -f "$STATE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in MAX) MAX=$v;; esac
  done < "$STATE"
fi
if [ "$MAX" = "1" ]; then
  echo "<img>$RESTORE</img>"
  echo "<click>/usr/local/bin/tarsila-goto2.sh</click>"
else
  echo "<img>$BLANK</img>"
fi
