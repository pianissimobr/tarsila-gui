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
SOUNDS=/usr/share/sounds/freedesktop/stereo
SND_MAXIMIZE="$SOUNDS/bell.oga"
SND_RESTORE="$SOUNDS/message.oga"
SND_EMPTY="$SOUNDS/complete.oga"

# instancia unica (o lock cai sozinho quando o processo morre)
exec 200>"$CACHE.lock"
flock -n 200 || exit 0

# fifo para dormir sem forkar /bin/sleep
FIFO="${XDG_RUNTIME_DIR:-/tmp}/tarsila-monitor.fifo"
rm -f "$FIFO"; mkfifo "$FIFO"
exec 9<>"$FIFO"

play_sound() {
  [ -f "$1" ] && (canberra-gtk-play -f "$1" >/dev/null 2>&1 &)
}

prev_n=""
prev_state=1
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

  # wincount: grava e acorda as bolinhas so quando muda
  if [ "$n" != "$prev_n" ]; then
    echo "$n" > "$CACHE.tmp" && mv -f "$CACHE.tmp" "$CACHE"
    for p in genmon-37 genmon-38 genmon-39; do
      xfce4-panel --plugin-event=$p:refresh:bool:true 2>/dev/null
    done
    prev_n="$n"
  fi

  # som nas transicoes
  if [ "$state" != "$prev_state" ]; then
    case "$state" in
      3) play_sound "$SND_MAXIMIZE" ;;
      2) [ "$prev_state" = "3" ] && play_sound "$SND_RESTORE" ;;
      1) play_sound "$SND_EMPTY" ;;
    esac
    prev_state=$state
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

  read -t 0.5 -u 9 _ 2>/dev/null
done
