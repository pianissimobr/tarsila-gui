#!/bin/bash
# Autostart: daemon residente UNICO da sessao. Substitui os antigos
# tarsila-wincount.sh, tarsila-window-sound.sh e tarsila-rename-windows.sh
# (3 loops separados, cada um com seus proprios wmctrl/xdotool/xprop por
# ciclo) por um loop so, com UMA chamada `wmctrl -lx` por ciclo - neste
# hardware modesto cada processo forkado custa caro, entao a economia e
# relevante (de ~15-20 forks/s para ~2/s em regime).
#
# Responsabilidades por ciclo (0,5s):
#  1. WINCOUNT: cacheia a contagem de janelas de apps em
#     $XDG_RUNTIME_DIR/tarsila-wincount e, quando ela MUDA, acorda as
#     bolinhas do top bar via plugin-event (elas pollam devagar - 10s -
#     e dependem deste aviso para reagir na hora).
#  2. SOM: toca um som nas transicoes de estado 1 (vazio) / 2
#     (flutuante) / 3 (maximizado). O estado 3 vem de MAX= no arquivo
#     tarsila-topbar-state.txt (gravado pelo tarsila-title.sh, o
#     "lider"), em vez de consultar xdotool/xprop por conta propria.
#  3. TITULO AMIGAVEL: forca titulo fixo na decoracao nativa (xfwm4)
#     de apps nativos (Thunar->Arquivos etc.), reaplicando so quando o
#     titulo atual esta errado (o wmctrl -lx ja traz o titulo, entao a
#     checagem nao custa fork nenhum; o xdotool so roda na correcao).
#  4. PRIORIDADE: renice +10 nas janelas fora de foco - so quando o
#     conjunto de janelas ou o foco muda, nao a cada ciclo.
#
# O sleep do ciclo usa `read -t` num FIFO (builtin do bash, sem fork de
# /bin/sleep a cada volta).

CACHE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-wincount"
TOPBAR_STATE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
# instancia unica (o lock cai sozinho quando o processo morre)
exec 200>"$CACHE.lock"
flock -n 200 || exit 0

# fifo para dormir sem forkar /bin/sleep
FIFO="${XDG_RUNTIME_DIR:-/tmp}/tarsila-monitor.fifo"
rm -f "$FIFO"; mkfifo "$FIFO"
exec 9<>"$FIFO"

prev_n=""
prev_win_sig=""

while true; do
  n=0
  win_sig=""
  active=""

  # uma unica consulta ao X; os campos do wmctrl -lx sao:
  # id desktop wm_class host titulo...
  ids=()
  while read -r id desk wmclass host title; do
    case "$wmclass" in
      *[Pp]lank*|*xfce4-panel*|*xfdesktop*|"") continue ;;
    esac
    n=$((n + 1))
    ids+=("$id")
    win_sig+="$id "
    # titulo amigavel de apps nativos (estado nao maximizado): apps como
    # Thunar/qpdfview trocam o proprio titulo por pasta/arquivo aberto,
    # por isso a correcao e reaplicada sempre que sair do desejado
    target=""
    case "$wmclass" in
      Thunar.Thunar) target="Arquivos" ;;
      galculator.Galculator) target="Calculadora" ;;
      qpdfview.qpdfview) target="Leitor de PDF" ;;
    esac
    if [ -n "$target" ] && [ "$title" != "$target" ]; then
      xdotool set_window --name "$target" "$id" 2>/dev/null
    fi
  done < <(wmctrl -lx 2>/dev/null)

  # estado 1/2/3 (mesma semantica das bolinhas): MAX vem do lider
  MAX=0
  if [ -f "$TOPBAR_STATE" ]; then
    while IFS='=' read -r k v; do
      case "$k" in MAX) MAX=$v;; esac
    done < "$TOPBAR_STATE"
  fi
  if [ "$n" -eq 0 ]; then
    state=1
  elif [ "$MAX" = "1" ]; then
    state=3
  else
    state=2
  fi

  # A GUARDA DO "ESTADO A ORFAO" SAIU DAQUI (2026-08-15).
  #
  # Ela existia porque o estado da tela era escrito por um script que so
  # rodava quando alguem clicava (tarsila-polybar-mode.sh): se a janela
  # maximizada sumisse sem passar por ele -- o Chromium fechado pelo proprio
  # X e o caso tipico --, o modo ficava "full" para sempre, com a barra cheia
  # e a Dock escondida numa area de trabalho vazia. Este laco cacava esse
  # descompasso comparando o ID gravado com a lista de janelas viva, e
  # precisou de duas passadas seguidas para nao derrubar um Estado A legitimo.
  #
  # O tarsila-estado.sh nao tem esse buraco: ele dorme num xprop -spy de
  # _NET_CLIENT_LIST, entao a janela que some E o evento que o acorda. Nao ha
  # descompasso a consertar, e some junto o "200>&- 9>&-" que este trecho
  # precisava para nao entregar o lock e o FIFO deste script para a polybar.

  # wincount: grava e acorda as bolinhas so quando muda
  if [ "$n" != "$prev_n" ]; then
    echo "$n" > "$CACHE.tmp" && mv -f "$CACHE.tmp" "$CACHE"
    # Aqui havia um laco que acordava tres plugins genmon do xfce4-panel,
    # protegido por um arquivo-sentinela que o autostart cria. Na sessao
    # Openbox a sentinela sempre existe, entao o laco nunca chegou a rodar --
    # era codigo morto guardado por uma guarda que nunca falhava. Nao ha mais
    # painel do XFCE nem bolinhas a acordar. Quem lia este contador era o
    # tarsila-tela-estados, removido em 17/08/2026 junto com o vetor: hoje
    # NINGUEM le este arquivo. Ele continua sendo gravado enquanto nao se
    # decide se algo volta a precisar dele -- ver docs/DIAGNOSTICO-BIN.md.
    prev_n="$n"
  fi

  # renice das janelas fora de foco - so quando janelas/foco mudam
  if [ -n "$win_sig" ]; then
    active=$(xdotool getactivewindow 2>/dev/null)
    win_sig+="@$active"
  fi
  if [ "$win_sig" != "$prev_win_sig" ]; then
    for id in "${ids[@]}"; do
      # ids do wmctrl (0x0120000a) e do xdotool (decimal) diferem
      [ -n "$active" ] && [ "$((id))" = "$active" ] && continue
      pid=$(xdotool getwindowpid "$id" 2>/dev/null) || continue
      renice -n 10 -p "$pid" >/dev/null 2>&1
    done
    prev_win_sig="$win_sig"
  fi

  # 2s, nao 0,5s (2026-08-02): cada volta custa um "wmctrl -lx" e um
  # "xdotool getactivewindow" -- a 0,5s isso sozinho era ~5 forks/s numa box
  # fraca. A 2s cai para ~1,2/s. O preco e a latencia: som de janela e
  # deteccao do Estado A orfao podem demorar ate 2s. Se o som ficar
  # "atrasado" demais no uso real, este numero e o unico lugar a mexer.
  read -t 2 -u 9 _ 2>/dev/null
done
