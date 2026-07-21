#!/bin/bash
# "Limpar a Área de Trabalho": fecha TODOS os aplicativos abertos, deixando
# a mesa limpa (substitui a navegacao por "bolinhas"). Pergunta UMA vez num
# dialog central; se o usuario confirmar, fecha de forma decisiva — pede o
# fechamento e, em quem resistir, encerra o processo (agressivo por escolha).
export DISPLAY="${DISPLAY:-:0}"
apps(){ wmctrl -lx 2>/dev/null | grep -viE 'plank|polybar|xfce4-panel|xfdesktop' | awk '{print $1}'; }

wins=$(apps)
[ -z "$wins" ] && exit 0   # mesa ja limpa, nada a fazer

yad --title="Limpar a Área de Trabalho" \
    --window-icon=edit-clear --image=dialog-warning \
    --text="<big><b>Fechar tudo e limpar a área de trabalho?</b></big>

Todos os aplicativos abertos serão fechados.
O que não estiver salvo pode ser perdido." \
    --center --on-top --width=460 --borders=20 --buttons-layout=center \
    --button="Cancelar!gtk-cancel:1" --button="Limpar!edit-clear:0" 2>/dev/null
[ $? -eq 0 ] || exit 0   # cancelou

# 1) pedido de fechamento educado (apps limpos fecham na hora)
for id in $wins; do wmctrl -ic "$id" 2>/dev/null; done
sleep 2.5
# 2) agressivo: encerra quem resistiu
for id in $(apps); do
  pid=$(xprop -id "$id" _NET_WM_PID 2>/dev/null | awk '{print $NF}')
  [ -n "$pid" ] && kill "$pid" 2>/dev/null
done
sleep 1
for id in $(apps); do
  pid=$(xprop -id "$id" _NET_WM_PID 2>/dev/null | awk '{print $NF}')
  [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null
done
