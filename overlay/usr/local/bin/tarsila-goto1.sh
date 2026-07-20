#!/bin/bash
# Vai para a janela de trabalho 1: fundo limpo (esconde os apps sem fechar).
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-state"
wmctrl -k on
echo 1 > "$STATE_FILE"

# Acorda o top bar na hora (bolinhas/botoes pollam devagar - rede de
# seguranca de 10s; ver tarsila-topbar-refresh.sh). Pequena espera para
# o gerenciador de janelas terminar de aplicar o estado.
( sleep 0.2; /usr/local/bin/tarsila-topbar-refresh.sh ) >/dev/null 2>&1 &
