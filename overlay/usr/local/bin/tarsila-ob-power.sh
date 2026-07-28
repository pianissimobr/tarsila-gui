#!/bin/bash
# Menu de energia do top bar (clique no ícone de energia do polybar):
# Desligar / Reiniciar / Sair. Usa yad (já instalado).
yad --title="Energia" --text="O que você deseja fazer?" \
    --center --width=340 --borders=14 --buttons-layout=center \
    --button="Desligar!system-shutdown:2" \
    --button="Reiniciar!system-reboot:3" \
    --button="Sair!system-log-out:4" \
    --button="Cancelar!gtk-cancel:1" 2>/dev/null
case $? in
  2) systemctl poweroff ;;
  3) systemctl reboot ;;
  4) openbox --exit ;;
esac
