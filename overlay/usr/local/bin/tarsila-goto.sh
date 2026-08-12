#!/bin/bash
# As tres "janelas de trabalho" da Tarsila -- que nao sao areas de trabalho
# do X, e sim tres estados da mesma area:
#
#   1  fundo limpo:  esconde os apps sem fechar nenhum
#   2  flutuante:    desmaximiza tudo e devolve a barra de titulo   (Estado B)
#   3  maximizado:   maximiza a janela ativa e tira a decoracao     (Estado A)
#
# UM ARQUIVO SO (05/08). Eram tres, e os tres repetiam o mesmo preambulo de
# DISPLAY/XAUTHORITY, o mesmo arquivo de estado, a mesma forma de chamar o
# modo da barra e a mesma chamada morta:
#
#     ( sleep 0.2; /usr/local/bin/tarsila-topbar-refresh.sh ) &
#
# O topbar-refresh existe para acordar plugins genmon do xfce4-panel e sai
# na PRIMEIRA linha quando a sessao e Openbox -- ou seja, em toda troca de
# estado o sistema criava um subshell, dormia 0,2 s e chamava um programa
# que nao fazia nada. Saiu.
#
# Os nomes antigos continuam valendo: tarsila-goto1.sh, tarsila-goto2.sh e
# tarsila-goto3.sh sao links para este arquivo e o destino sai do nome pelo
# qual ele foi chamado (rc.xml, polybar, devilspie2 e Dock apontam para os
# nomes antigos).
set -u
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

RT="${XDG_RUNTIME_DIR:-/tmp}"
STATE_FILE="$RT/tarsila-state"
SEM_DECORACAO="$RT/tarsila-undecorated"

case "$(basename "$0")" in
  *goto1*) ALVO=1 ;;
  *goto2*) ALVO=2 ;;
  *goto3*) ALVO=3 ;;
  *)       ALVO="${1:-2}" ;;
esac

# Grava o estado e so entao muda o modo da barra -- nessa ordem, como era
# nos tres scripts antigos: quem desenha a barra le este arquivo.
# O "-f" bifurca e devolve na hora; o setsid antigo nao o tem, dai o
# segundo caminho.
entra_no_estado() {   # entra_no_estado [<modo da barra> [id]]
  printf '%s\n' "$ALVO" > "$STATE_FILE"
  [ $# -gt 0 ] || return 0
  setsid -f /usr/local/bin/tarsila-polybar-mode.sh "$@" >/dev/null 2>&1 || \
    setsid /usr/local/bin/tarsila-polybar-mode.sh "$@" >/dev/null 2>&1 &
}

case "$ALVO" in
  1)
    wmctrl -k on
    entra_no_estado
    ;;

  2)
    wmctrl -k off
    # A barra de cima e a Dock nao sao janelas de aplicativo: ficam de fora.
    for id in $(wmctrl -lx 2>/dev/null \
                | grep -viE 'plank|xfce4-panel|xfdesktop|polybar|tela-estados' \
                | awk '{print $1}'); do
      wmctrl -ir "$id" -b remove,maximized_vert,maximized_horz
    done
    # Devolve a barra de titulo de quem foi maximizado por aqui. O Openbox
    # so aceita isso pela propria acao (super+i), com a janela ativa.
    uid=$(cat "$SEM_DECORACAO" 2>/dev/null || true)
    if [ -n "$uid" ]; then
      xdotool windowactivate "$uid" 2>/dev/null
      sleep 0.05
      xdotool key --clearmodifiers super+i 2>/dev/null
      rm -f "$SEM_DECORACAO"
    fi
    entra_no_estado compact
    ;;

  3)
    wmctrl -k off
    id=$(xdotool getactivewindow 2>/dev/null || true)
    entra_no_estado full "$id"
    sleep 0.35  # fundo do polybar pinta antes do maximize (07/08)
    if [ -n "$id" ]; then
      wmctrl -ir "$id" -b add,maximized_vert,maximized_horz
      sleep 0.12
      printf '%s\n' "$id" > "$SEM_DECORACAO"
      xdotool key --clearmodifiers super+u
    fi
    ;;

  *)
    echo "uso: $0 [1|2|3]" >&2; exit 1 ;;
esac
