#!/bin/bash
# FONTE DE VERDADE DO ESTADO DA TELA: "ha janela maximizada?"
#
# Substitui o tarsila-polybar-mode.sh, que respondia a essa pergunta como
# efeito colateral de reescrever o config da barra, matar o processo polybar
# e relanca-lo -- a operacao mais frequente do sistema e a mais cara.
#
# Aqui nao ha barra. Sobrou a pergunta, e ela e respondida por evento do X.
# Parado, custa zero: nenhum relogio, nenhum subprocesso acordando.
#
# O QUE ELE ESCREVE
#
#   $XDG_RUNTIME_DIR/tarsila-topbar-state.txt   ->  MAX=0|1 / ID=<janela>
#
# Consumidor: o tarsila-dock, que se esconde quando MAX=1. Eram tres --
# tarsila-tela-estados, tarsila-monitor.sh e o floating.lua saíram em
# 17/08/2026.
#
# TAMBEM CUIDA DO TITULO AMIGAVEL (ver a tabela AMIGAVEL, abaixo). Nao e um
# assunto solto: ele veio do tarsila-monitor.sh, que fazia isso varrendo as
# janelas de 2 em 2 segundos para sempre. Os eventos que o monitor procurava
# com essa varredura sao exatamente os que este daemon ja recebe de graca --
# janela nasce, foco muda, titulo muda. Juntar apagou um daemon inteiro e
# 1,2 fork/s em repouso.
#
# O QUE SAIU DAQUI EM 17/08/2026
#
# Uma funcao politica_da_dock() que escrevia hide-mode='dodge-maximized' no
# dconf do Plank a cada troca de estado. O Plank saiu em 16/08 e a Dock em GTK
# nao le dconf: quem a esconde ao maximizar e ela mesma, lendo o arquivo de
# estado que este script escreve. Era uma escrita a um leitor que nao existe.
#
# POR QUE DUAS FONTES DE EVENTO, E NAO UMA
#
# Medido na VM de teste: maximizar uma janela QUE JA ESTA EM FOCO produz
#   _NET_ACTIVE_WINDOW / _NET_CLIENT_LIST da raiz ... 0 eventos
#   _NET_WM_STATE da propria janela ................. 2 eventos
# Ou seja, vigiar so a raiz e ser cego justamente para o evento central deste
# script. A primeira versao disfarcava isso com um "read -t 2", que na pratica
# transformava o daemon numa sondagem de 2 em 2 segundos -- o oposto do que
# ele existe para ser. Agora sao dois xprop -spy:
#
#   raiz   -> troca de foco, janela nasce, janela morre
#   janela -> _NET_WM_STATE da janela ativa, que e onde maximizar aparece
#
# Os dois despejam no mesmo cano. O vigia da janela e reapontado sempre que o
# foco muda; o da raiz e o que avisa que o foco mudou.

set -u
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

RT="${XDG_RUNTIME_DIR:-/tmp}"
STATE="$RT/tarsila-topbar-state.txt"

# Estado anterior, so em memoria: o arquivo so e reescrito quando muda de
# verdade. Ele e vigiado por inotify (Gio.FileMonitor) do outro lado, e
# reescrever com o mesmo conteudo acordaria a Dock a toa.
ultimo=""
ativa=""          # id da janela em foco, maximizada ou nao

maximizada() {   # <id> -> 0 se a janela esta maximizada
  [ -n "${1:-}" ] && [ "$1" != "0" ] || return 1
  xprop -id "$1" _NET_WM_STATE 2>/dev/null | grep -q '_NET_WM_STATE_MAXIMIZED_VERT'
}

# TITULO AMIGAVEL -- veio do tarsila-monitor.sh, que foi removido em 17/08/2026.
#
# Alguns aplicativos poem na barra de titulo uma informacao que nao diz nada ao
# usuario leigo: "alan - Thunar" em vez de "Arquivos", "galculator" em vez de
# "Calculadora". Pior, eles trocam esse titulo sozinhos ao navegar, entao nao
# basta acertar uma vez -- e o motivo de o monitor reaplicar isto.
#
# O nome nao e enfeite: o tarsila-uma-janela procura a janela existente pelo
# TITULO ("^Calculadora$"), entao trocar isto quebra a instancia unica.
#
# Cuidado com a classe: o wmctrl imprime "thunar.Thunar", com t minusculo. O
# case do monitor procurava "Thunar.Thunar" e por isso o Thunar NUNCA foi
# renomeado, enquanto galculator e qpdfview eram. Corrigido aqui.
declare -A AMIGAVEL=(
  [thunar.Thunar]="Arquivos"
  [galculator.Galculator]="Calculadora"
  [qpdfview.qpdfview]="Leitor de PDF"
)

titulos_amigaveis() {
  local id desk classe host titulo alvo
  while read -r id desk classe host titulo; do
    alvo="${AMIGAVEL[$classe]:-}"
    [ -n "$alvo" ] || continue
    [ "$titulo" = "$alvo" ] && continue
    xdotool set_window --name "$alvo" "$id" 2>/dev/null
  done < <(wmctrl -lx 2>/dev/null)
}

publica() {
  local id max novo
  # O titulo vem antes do resto: se a janela acabou de nascer, o usuario ve o
  # nome certo desde o primeiro quadro, e nao um "galculator" que vira
  # "Calculadora" meio segundo depois.
  titulos_amigaveis

  id=$(xdotool getactivewindow 2>/dev/null || true)
  [ "${id:-0}" = "0" ] && id=""
  ativa="$id"
  if maximizada "$id"; then max=1; else max=0; id=""; fi
  novo="MAX=$max
ID=$id"
  [ "$novo" = "$ultimo" ] && return 0
  printf '%s\n' "$novo" > "$STATE.tmp" && mv -f "$STATE.tmp" "$STATE"
  ultimo="$novo"
}

# ------------------------------------------------------------------ vigias
# Um cano so, aberto para leitura E escrita no fd 3. Manter a ponta de escrita
# aberta aqui e o que impede o read de ver fim-de-arquivo quando os dois
# xprop morrem ao mesmo tempo -- sem isso o laco giraria a plena carga.
CANO=$(mktemp -u "${TMPDIR:-/tmp}/tarsila-estado.XXXXXX")
mkfifo -m 600 "$CANO" || exit 1
exec 3<>"$CANO"
rm -f "$CANO"          # o inode fica vivo pelo fd; nada sobra no disco

pid_raiz=0
pid_janela=0
alvo=""                # janela que o vigia_janela esta observando agora

# "Nenhum vigia" e representado por pid 0, e para o kill o 0 nao e "ninguem":
# e O GRUPO DE PROCESSOS INTEIRO, este script incluido. Sem estas duas guardas
# o daemon se mata sozinho na primeira troca de foco, e o trap de saida ainda
# reentra em si mesmo ate estourar a pilha. Foi o que aconteceu no primeiro
# teste na VM. Mesma armadilha no kill -0: com pid 0 ele responde "vivo"
# porque o grupo existe, e o vigia morto nunca seria reerguido.
vivo() { [ "${1:-0}" -gt 0 ] 2>/dev/null && kill -0 "$1" 2>/dev/null; }
mata() { [ "${1:-0}" -gt 0 ] 2>/dev/null && kill "$1" 2>/dev/null; return 0; }

encerra() {
  trap - EXIT INT TERM     # sem isto o kill abaixo reentra neste mesmo trap
  mata "$pid_raiz"
  mata "$pid_janela"
  # O `exit` NAO e enfeite. Um handler de TERM que apenas retorna devolve o
  # controle ao laco: o daemon matava os proprios vigias e SEGUIA RODANDO,
  # cego, sem publicar nada e sem morrer. Descoberto em 17/08/2026 tentando
  # reiniciar o daemon -- o `kill` parecia nao funcionar, e o que restava era
  # um processo vivo que ja nao servia para nada. Como o trap foi limpo na
  # linha de cima, este exit nao reentra aqui.
  exit 0
}
trap encerra EXIT INT TERM

sobe_vigia_raiz() {    # idempotente: so levanta se nao estiver de pe
  vivo "$pid_raiz" && return 1
  xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST >&3 2>/dev/null &
  pid_raiz=$!
  return 0
}

sobe_vigia_janela() {  # <id>; reaponta so quando o alvo mudou ou o vigia caiu
  local id="${1:-}"
  if [ "$id" = "$alvo" ] && { [ -z "$id" ] || vivo "$pid_janela"; }; then
    return 1
  fi
  mata "$pid_janela"
  pid_janela=0
  alvo="$id"
  [ -n "$id" ] || return 0
  # _NET_WM_NAME entra junto por causa do titulo amigavel: o Thunar troca o
  # proprio titulo ao navegar de pasta, e isso nao mexe em nada da raiz. Sem
  # esta propriedade aqui, o nome so seria corrigido na proxima troca de foco.
  xprop -spy -id "$id" _NET_WM_STATE _NET_WM_NAME >&3 2>/dev/null &
  pid_janela=$!
  return 0
}

publica
sobe_vigia_raiz
sobe_vigia_janela "$ativa"

while :; do
  # Sem evento, este read dorme indefinidamente -- os 60 s sao apenas uma
  # batida de coracao para reerguer vigia morto. Ela nao chama publica() nem
  # forka nada: kill -0 e builtin. Se algum vigia precisou ser reerguido, ai
  # sim republica, porque nesse intervalo pode ter escapado uma mudanca.
  read -t 60 -u 3 -r _; rc=$?
  if [ "$rc" -eq 0 ]; then
    publica
    sobe_vigia_raiz
    sobe_vigia_janela "$ativa"
  elif [ "$rc" -gt 128 ]; then
    reerguido=0
    sobe_vigia_raiz            && reerguido=1
    sobe_vigia_janela "$ativa" && reerguido=1
    [ "$reerguido" = 1 ] && publica
  else
    # O cano nao pode dar EOF (seguramos a ponta de escrita), entao chegar
    # aqui e erro de verdade. Sair e melhor que girar.
    break
  fi
done
