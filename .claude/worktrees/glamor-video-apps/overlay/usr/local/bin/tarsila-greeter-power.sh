#!/bin/bash
# Botao de energia da tela de login: icone branco discreto (estilo top
# bar) no canto superior direito, fundo preto igual ao do greeter. Ao
# clicar, pergunta Desligar/Reiniciar/Voltar. A interface em si e o
# tarsila-greeter-power-gtk.py (PyGObject - o yad nao permite fundo
# preto sem "caixa").
# Chamado pelo greeter-setup-script do lightdm (roda como root, ja com
# DISPLAY/XAUTHORITY da tela do greeter). Ao logar, o session-setup-script
# (tarsila-greeter-power-stop.sh) encerra o icone.
#
# setsid + re-execucao: o lightdm mata o grupo de processos do
# setup-script assim que ele retorna. sleep 3: a sessao do greeter nao
# tem window manager - quem mapeia por ultimo fica por cima, e o cartao
# do greeter mapeia depois deste script comecar.
LOG=/var/tmp/tarsila-greeter-power.log

if [ "${1:-}" != "run" ]; then
  setsid "$0" run < /dev/null > "$LOG" 2>&1 &
  exit 0
fi

exec 200>/run/tarsila-greeter-power.lock
flock -n 200 || exit 0

echo "$(date +%T) iniciando (DISPLAY=$DISPLAY)"
sleep 3
exec python3 /usr/local/bin/tarsila-greeter-power-gtk.py
