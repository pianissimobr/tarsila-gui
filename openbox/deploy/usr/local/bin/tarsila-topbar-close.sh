#!/bin/bash
# ✕ da topbar (Estado A): fecha a janela e volta ao Estado B.
#
# 2026-08-02 -- alguns programas continuam TRABALHANDO com a janela aberta, e
# fechar do nada joga o trabalho fora. O caso concreto e o OBS: pode estar
# gravando ou transmitindo, e o ✕ encerraria isso sem aviso. Para esses,
# pergunta antes. Para todo o resto, fecha direto como sempre foi -- a
# pergunta so tem valor se for rara.
#
# Nao ha deteccao de "esta gravando agora": o OBS nao publica esse estado de
# um jeito que de para ler de fora sem ligar o servidor WebSocket dele. Por
# isso a regra e por PROGRAMA, e o texto diz "se houver", sem afirmar que ha.
set -uo pipefail
ID="${1:-}"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
trap '' HUP

volta_ao_estado_b() {
  setsid -f /usr/local/bin/tarsila-polybar-mode.sh compact >/dev/null 2>&1 || \
    setsid /usr/local/bin/tarsila-polybar-mode.sh compact >/dev/null 2>&1 &
}

fecha_e_volta() {
  [ -n "$ID" ] && wmctrl -ic "$ID" 2>/dev/null
  volta_ao_estado_b
}

if [ -z "$ID" ]; then
  volta_ao_estado_b
  exit 0
fi

WCLASS=$(xprop -id "$ID" WM_CLASS 2>/dev/null | sed -n 's/.*"\([^"]*\)", "[^"]*".*/\1/p')

# Programas que pedem confirmacao, com o motivo em linguagem de gente.
case "${WCLASS,,}" in
  obs)
    NOME="OBS Studio"
    MOTIVO="Se houver uma gravação ou transmissão em andamento, ela será encerrada."
    ;;
  *)
    # Todo o resto: fecha direto.
    fecha_e_volta
    exit 0
    ;;
esac

yad --title="Fechar $NOME" \
    --window-icon=dialog-warning \
    --image=dialog-warning \
    --text="<b>Deseja mesmo fechar o $NOME?</b>

$MOTIVO" \
    --button="Cancelar:1" \
    --button="Fechar mesmo assim:0" \
    --center --on-top --sticky --borders=14 --width=430 \
    2>/dev/null
RC=$?

if [ "$RC" = 0 ]; then
  fecha_e_volta
fi
# Qualquer outra saida (Cancelar, Esc, fechar o dialogo) e "nao": a janela
# continua aberta e a barra segue no Estado A, sem surpresa.
exit 0
