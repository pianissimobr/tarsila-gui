#!/bin/bash
# Aplica os ajustes de teclado e mouse escolhidos na tela de Ajustes.
#
# POR QUE ISTO EXISTE: no XFCE quem guardava e reaplicava velocidade do
# ponteiro e repeticao de tecla era o xfsettingsd, lendo o xfconf. Esta sessao
# e Openbox e nao roda o xfsettingsd -- roda o xsettingsd, que so cuida de
# tema/fonte/cursor e nao tem chave para entrada. O `xset` aplica na hora mas
# NAO persiste: some no logout. Entao a escolha fica num arquivo por ajuste em
# ~/.config/tarsila/ (mesmo padrao de descanso-minutos, bar-height e tema) e
# este script a reaplica no login.
#
# Chamado pelo ~/.config/openbox/autostart.

export DISPLAY="${DISPLAY:-:0}"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/tarsila"

ler() {  # ler <arquivo> <padrao>
    local v
    [ -f "$CFG/$1" ] && read -r v < "$CFG/$1" 2>/dev/null
    case "$v" in
        ''|*[!0-9]*) echo "$2" ;;
        *)           echo "$v" ;;
    esac
}

# --- Velocidade do ponteiro -------------------------------------------------
# A tela grava 1..10. O xset quer aceleracao e limiar; o limiar fica fixo em 4
# (padrao do X) e so a aceleracao varia, que e o que o usuario percebe.
VEL=$(ler mouse-velocidade 2)
[ "$VEL" -lt 1 ] && VEL=1
[ "$VEL" -gt 10 ] && VEL=10
xset m "$VEL" 4 2>/dev/null

# --- Repeticao de tecla -----------------------------------------------------
# Guardamos a ESPERA em milissegundos (quanto tempo segurando a tecla ate ela
# comecar a repetir). Numero maior = mais tolerante a quem tem a mao tremida e
# demora a soltar. A taxa fica fixa em 25/s.
ESPERA=$(ler teclado-repeticao 600)
[ "$ESPERA" -lt 200 ] && ESPERA=200
[ "$ESPERA" -gt 2000 ] && ESPERA=2000
xset r rate "$ESPERA" 25 2>/dev/null

# --- Teclas de aderencia ----------------------------------------------------
# Desligado por padrao: o atalho de 5x Shift liga sozinho sem querer e deixa o
# teclado "grudado", e o leigo nao entende o que houve nem como sair.
# O "exp 1 =a" impede o X de reativar sozinho depois de um tempo.
if [ "$(ler teclas-aderencia 0)" = "1" ]; then
    xkbset a 2>/dev/null
    xkbset exp 1 a 2>/dev/null
else
    xkbset -a 2>/dev/null
    xkbset exp 1 =a 2>/dev/null
fi

exit 0
