#!/bin/bash
# Sessoes sem xfce4-panel (Openbox/polybar): nada a acordar (polybar e
# event-driven via xprop). Evita o dialog "Falha ao enviar mensagem D-Bus".
[ -f "${XDG_RUNTIME_DIR:-/tmp}/tarsila-openbox.session" ] && exit 0
case "${XDG_CURRENT_DESKTOP:-}" in *Openbox*) exit 0 ;; esac
# Forca a re-execucao imediata dos plugins genmon do top bar, via
# plugin-event do xfce4-panel. Chamado pelos scripts que CAUSAM uma
# mudanca de estado (tarsila-goto1/2/3, tarsila-title, tarsila-wincount).
# Com isso os plugins podem pollar bem devagar (10s, so rede de
# seguranca) sem perder resposta ao clique - antes as bolinhas pollavam a
# cada 100ms (30 processos/s) e isso comia a CPU do hardware modesto.
#
# Ordem importa: o titulo (genmon-36, "lider") roda primeiro e grava
# MAX/ID no arquivo de estado; bolinhas e botoes ("seguidores") leem esse
# arquivo, entao so sao atualizados depois de uma pequena espera.
xfce4-panel --plugin-event=genmon-36:refresh:bool:true 2>/dev/null
sleep 0.3
for p in genmon-37 genmon-38 genmon-39 genmon-40 genmon-41; do
  xfce4-panel --plugin-event=$p:refresh:bool:true 2>/dev/null
done
