#!/bin/bash
# Autostart (prioridade alta): mostra o cursor de "carregando" enquanto
# a sessao sobe e devolve a seta normal quando o dock e o painel estao
# de pe - o usuario leigo entende que precisa esperar, em vez de clicar
# num desktop pela metade.
xsetroot -cursor_name watch 2>/dev/null

for _ in $(seq 1 60); do
  if pgrep -u "$USER" -x plank >/dev/null 2>&1 \
     && pgrep -u "$USER" -x polybar >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
sleep 2
xsetroot -cursor_name left_ptr 2>/dev/null
