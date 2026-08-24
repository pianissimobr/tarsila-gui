#!/bin/bash
# Autostart (prioridade alta): mostra o cursor de "carregando" enquanto a
# sessao sobe e devolve a seta normal quando a area de trabalho esta pronta -
# o usuario leigo entende que precisa esperar, em vez de clicar num desktop
# pela metade.
#
# PERGUNTE PELA JANELA, NAO PELO NOME DO PROCESSO.
#
# Este laco ja errou duas vezes pelo mesmo motivo. Ate 15/08/2026 ele exigia um
# xfce4-panel de pe, que nao existe nesta sessao; consertou-se tirando o painel
# e deixando `pgrep -x plank`, e o Plank saiu no dia seguinte. Nos dois casos a
# condicao nunca era satisfeita, o laco gastava os 60 ciclos de 0,5 s em TODO
# boot, e o usuario via a ampulheta por ~32 s DEPOIS de a tela estar pronta --
# exatamente o oposto do que este script existe para fazer.
#
# Agora a pergunta e sobre o que se quer de fato saber: a janela apareceu na
# tela? Um processo pode estar de pe sem ter pintado nada, e o nome do processo
# muda a cada troca de componente. A janela e o fim da espera.
# Pelo NOME da janela, nao pela classe: desde 24/08/2026 a Dock e a barra
# dividem um processo (tarsila-shell), e o GTK carimba nas duas o WM_CLASS do
# processo -- as duas viraram "Tarsila-shell". O titulo e por janela.
pronto() {
  [ -n "$(xdotool search --name '^tarsila-dock$' 2>/dev/null)" ] &&
  [ -n "$(xdotool search --name '^tarsila-barra$' 2>/dev/null)" ]
}

xsetroot -cursor_name watch 2>/dev/null

for _ in $(seq 1 60); do
  pronto && break
  sleep 0.5
done
# As janelas existem; este resto e para os icones terminarem de pintar.
sleep 2
xsetroot -cursor_name left_ptr 2>/dev/null
