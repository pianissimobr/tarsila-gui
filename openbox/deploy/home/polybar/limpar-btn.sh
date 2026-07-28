#!/bin/bash
# Botao "Limpar": icone na cor padrao da top bar (igual aos outros).
# O fundo era amarelo, que chamava mais atencao que o proprio relogio. Agora e
# um cinza um tom abaixo do fundo da barra (#EDF1F4): marca que ali ha um
# botao, sem gritar.
ICON=$(printf '\xef\x83\x90')   # fa-magic (FontAwesome, %{T3})
BG='#dbe0e5'
emit(){
  n=$(wmctrl -lx 2>/dev/null | grep -viE 'plank|polybar|xfce4-panel|xfdesktop|tarsila-aviso|tarsila-barra-menu|Dunst|notification' | wc -l)
  if [ "${n:-0}" -gt 0 ]; then
    printf '%%{B%s} %%{T3}%s%%{T-} %%{B-}\n' "$BG" "$ICON"
  else
    echo ""
  fi
}
emit
xprop -spy -root _NET_CLIENT_LIST _NET_ACTIVE_WINDOW _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
