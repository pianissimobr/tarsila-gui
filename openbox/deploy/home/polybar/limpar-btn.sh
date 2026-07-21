#!/bin/bash
# Botao "Limpar" (topo, direita, antes da linha separadora): SO o icone
# (varinha magica) dentro de um pill AMARELO de cantos arredondados (capsulas
# nerd de altura cheia). Aparece apenas quando ha aplicativo aberto (mesa
# suja); some com a mesa limpa. Clique -> tarsila-limpar.sh (config.ini).
ICON=$(printf '\xef\x83\x90')   # fa-magic (FontAwesome, %{T3})
CL=$(printf '\xee\x82\xb6')     #  capsula esquerda (Symbols Nerd Font, %{T5})
CR=$(printf '\xee\x82\xb4')     #  capsula direita
BG='#f2c21e'; FG='#3a2e00'
emit(){
  n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|polybar|xfce4-panel|xfdesktop' | wc -l)
  if [ "${n:-0}" -gt 0 ]; then
    printf '%%{T5}%%{F%s}%s%%{F-}%%{T-}%%{B%s}%%{F%s} %%{T3}%s%%{T-} %%{B-}%%{T5}%%{F%s}%s%%{F-}%%{T-}\n' \
      "$BG" "$CL" "$BG" "$FG" "$ICON" "$BG" "$CR"
  else
    echo ""
  fi
}
emit
xprop -spy -root _NET_CLIENT_LIST _NET_ACTIVE_WINDOW _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
