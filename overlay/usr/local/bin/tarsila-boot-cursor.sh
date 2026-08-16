#!/bin/bash
# Autostart (prioridade alta): mostra o cursor de "carregando" enquanto
# a sessao sobe e devolve a seta normal quando o dock e o painel estao
# de pe - o usuario leigo entende que precisa esperar, em vez de clicar
# num desktop pela metade.
xsetroot -cursor_name watch 2>/dev/null

for _ in $(seq 1 60); do
  # So o Plank. Ate 2026-08-15 exigia-se TAMBEM um xfce4-panel de pe -- e
  # nao ha xfce4-panel nesta sessao, entao a condicao nunca era satisfeita:
  # o laco gastava os 60 ciclos de 0,5 s em TODO boot e o usuario via o
  # cursor de relogio por ~32 s depois de a area de trabalho ja estar pronta.
  if pgrep -u "$USER" -x plank >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
sleep 2
xsetroot -cursor_name left_ptr 2>/dev/null
