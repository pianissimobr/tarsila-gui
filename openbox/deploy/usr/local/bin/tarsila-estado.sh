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
# Consumidores:
#   - tarsila-dock          (esconde a Dock quando MAX=1)
#   - tarsila-monitor.sh    (estado 1/2/3)
#
# O terceiro era o tarsila-tela-estados, removido em 17/08/2026 junto com o
# vetor de abertura. O floating.lua tambem lia este arquivo e parou de ler.
#
# O QUE ELE DECIDE
#
# A politica da Dock, em tres regras:
#   1. maximizou    -> Dock esconde
#   2. desmaximizou -> Dock aparece
#   3. a sessao comeca com ela aparecendo
#
# Quem executa 1 e 2 e o proprio Plank, pelo hide-mode "dodge-maximized" --
# ele enxerga janela maximizada sozinho, e com pressure-reveal a Dock ainda
# sobe quando o cursor encosta na borda de baixo. Aqui so garantimos que o
# modo esteja nesse valor.
#
# O botao da Dock e uma EXCECAO TEMPORARIA: escreve 'none' (forcar visivel)
# ou 'autohide' (forcar escondida) por cima. Este daemon reimpoe
# 'dodge-maximized' em toda troca de estado, o que descarta a escolha manual
# anterior -- a regra combinada: o botao vale ate o proximo maximizar ou
# desmaximizar.
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
DCONF_HIDE=/net/launchpad/plank/docks/dock1/hide-mode

# Estado anterior, so em memoria: o arquivo so e reescrito quando muda de
# verdade. Ele e vigiado por inotify (Gio.FileMonitor) do outro lado, e
# reescrever com o mesmo conteudo acordaria o tela-estados a toa.
ultimo=""
ativa=""          # id da janela em foco, maximizada ou nao

maximizada() {   # <id> -> 0 se a janela esta maximizada
  [ -n "${1:-}" ] && [ "$1" != "0" ] || return 1
  xprop -id "$1" _NET_WM_STATE 2>/dev/null | grep -q '_NET_WM_STATE_MAXIMIZED_VERT'
}

# So mexe no dconf se o valor ja nao for o desejado: o Plank observa a chave
# e se reconfigura a cada escrita, mesmo escrevendo igual.
politica_da_dock() {
  local atual
  atual=$(dconf read "$DCONF_HIDE" 2>/dev/null)
  [ "$atual" = "'dodge-maximized'" ] || \
    dconf write "$DCONF_HIDE" "'dodge-maximized'" 2>/dev/null
}

publica() {
  local id max novo
  id=$(xdotool getactivewindow 2>/dev/null || true)
  [ "${id:-0}" = "0" ] && id=""
  ativa="$id"
  if maximizada "$id"; then max=1; else max=0; id=""; fi
  novo="MAX=$max
ID=$id"
  [ "$novo" = "$ultimo" ] && return 0

  # A troca de estado e o gatilho: e aqui que a escolha manual do botao
  # caduca. Comparar so o MAX (e nao o ID) evita reimpor a politica quando
  # o usuario apenas troca de foco entre duas janelas flutuantes.
  case "$ultimo" in
    "MAX=$max"*) ;;
    *) politica_da_dock ;;
  esac

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
  xprop -spy -id "$id" _NET_WM_STATE >&3 2>/dev/null &
  pid_janela=$!
  return 0
}

# Regra 3: a sessao comeca com a Dock a mostra. Escrito sem passar pelo
# atalho do "so quando muda", porque no arranque nao ha estado anterior.
politica_da_dock
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
