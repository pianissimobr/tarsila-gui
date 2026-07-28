#!/bin/bash
# Icone de energia (Font Awesome 4 power-off, bytes UTF-8). Clique abre o
# menu Desligar/Reiniciar/Sair (tarsila-ob-power.sh, no config.ini).
printf '%%{T3}%s%%{T-}\n' "$(printf '\xef\x80\x91')"
