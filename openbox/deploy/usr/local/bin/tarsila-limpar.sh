#!/bin/bash
# "Limpar a Área de Trabalho": fecha TODOS os aplicativos abertos, deixando
# a mesa limpa (substitui a navegacao por "bolinhas"). Pergunta UMA vez num
# dialog central; se o usuario confirmar, fecha de forma decisiva — pede o
# fechamento e, em quem resistir, encerra o processo (agressivo por escolha).
export DISPLAY="${DISPLAY:-:0}"
# O que e "aplicativo aberto" e o que e mobilia do sistema.
#
# Ate 17/08/2026 isto era uma lista de NOMES:
#     grep -viE 'plank|xfdesktop|tarsila-tela-estados'
# Os tres morreram na migracao para a Dock em GTK, e os dois que nasceram --
# tarsila-dock e tarsila-barra -- nao estavam na lista. Resultado: clicar na
# varinha fechava a propria Dock e a barra de indicadores, com wmctrl -ic,
# depois kill e, um segundo depois, kill -9. A mesa ficava limpa DEMAIS. Isso
# valeu desde a migracao, nao so depois da barra.
#
# Agora o corte e por TIPO de janela, nao por nome. Dock e barra sao
# _NET_WM_WINDOW_TYPE_DOCK e o fundo da area de trabalho e _DESKTOP; nenhum dos
# dois e aplicativo do usuario. Assim a proxima peca de mobilia que eu criar ja
# nasce protegida, sem ninguem precisar lembrar de vir aqui.
apps(){
  wmctrl -lx 2>/dev/null | while read -r id _resto; do
    case "$(xprop -id "$id" _NET_WM_WINDOW_TYPE 2>/dev/null)" in
      *_NET_WM_WINDOW_TYPE_DOCK*|*_NET_WM_WINDOW_TYPE_DESKTOP*) continue ;;
    esac
    printf '%s\n' "$id"
  done
}

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
