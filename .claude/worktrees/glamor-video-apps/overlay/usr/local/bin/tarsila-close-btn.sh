#!/bin/bash
# Botao "fechar" no top bar: so aparece com um app maximizado (bolinha 3).
# Clique fecha a janela ativa. Sempre emite uma tag <img> (mesmo vazia/
# invisivel) - o genmon mantem o ultimo icone renderizado se a saida vier
# sem nenhuma tag.
#
# "Seguidor": le o estado ja calculado por tarsila-title.sh (lider) em vez
# de rodar xdotool/xprop de novo, para acompanhar o lider sem atraso (ver
# comentario em tarsila-title.sh).
CLOSE="$HOME/.cache/tarsila/topbar/close.svg"; [ -f "$CLOSE" ] || CLOSE=/usr/local/share/tarsila/close-padded.svg
BLANK=/usr/local/share/tarsila/invisible.svg
STATE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
MAX=0; ID=""
if [ -f "$STATE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in MAX) MAX=$v;; ID) ID=$v;; esac
  done < "$STATE"
fi
if [ "$MAX" = "1" ] && [ -n "$ID" ]; then
  echo "<img>$CLOSE</img>"
  echo "<click>wmctrl -ic $ID</click>"
else
  echo "<img>$BLANK</img>"
fi
