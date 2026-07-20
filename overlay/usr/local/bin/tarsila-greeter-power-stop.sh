#!/bin/bash
# Encerra o botao de energia da tela de login quando um usuario loga.
# Chamado pelo session-setup-script do lightdm. Padroes escolhidos para
# NUNCA casarem com este proprio script (pkill -f com nome solto ja
# matou sessao ssh por auto-casamento; ver memoria do projeto).
pkill -f "yad.*tarsila-greeter-power" 2>/dev/null
pkill -f "[t]arsila-greeter-power-gtk" 2>/dev/null
exit 0
