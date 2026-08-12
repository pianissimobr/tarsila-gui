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

  # Estado A orfao (2026-08-02): a janela que estava maximizada sumiu sem
  # que ninguem avisasse. Acontece quando o app e fechado pelo botao dele
  # mesmo -- o caso tipico e o Chromium, que nasce maximizado pelo devilspie
  # e tem o proprio X (a topbar esconde os nossos botoes para ele). Sem isto
  # o modo ficaria "full" para sempre: barra cheia e Dock escondida numa
  # area de trabalho vazia.
  #
  # Usa a lista de janelas ja lida acima -- nenhuma consulta nova ao X. O ID
  # do arquivo e DECIMAL (veio do xdotool); o wmctrl devolve HEX, dai a
  # normalizacao com $((...)).
  if [ "$MAX" = "1" ]; then
    max_id=""
    while IFS='=' read -r k v; do
      case "$k" in ID) max_id=$v;; esac
    done < "$TOPBAR_STATE"
    if [ -n "$max_id" ]; then
      vivo=0
      for i in "${ids[@]}"; do
        if [ "$((i))" = "$((max_id))" ] 2>/dev/null; then vivo=1; break; fi
      done
      # DUAS PASSADAS, NAO UMA (06/08).
      #
      # A guarda dispara ~2 s depois de a barra ir para full, e havia um caso
      # em que ela derrubava um Estado A legitimo: a janela recem-maximizada
      # ainda nao aparecia na lista quando este laco a procurava. O resultado
      # era a barra voltar sozinha para compact com a janela maximizada na
      # tela -- Dock recolhida, botao no meio, exatamente o defeito que se
      # estava cacando.
      #
      # Pedindo duas passadas seguidas com a janela ausente, um quadro de
      # atraso deixa de ser motivo para desfazer nada, e a limpeza do Estado
      # A orfao (o motivo de a guarda existir) continua acontecendo -- so
      # leva um ciclo a mais.
      if [ "$vivo" = 0 ]; then
        orfao_seguidas=$(( ${orfao_seguidas:-0} + 1 ))
      else
        orfao_seguidas=0
      fi
      if [ "${orfao_seguidas:-0}" -ge 2 ]; then
        orfao_seguidas=0
        # 200>&- 9>&- e OBRIGATORIO: o mode.sh sobe a polybar, e a polybar
        # herdaria os descritores deste script -- o lock (fd 200) e o FIFO
        # do sleep (fd 9). Uma polybar viva segurando o lock faz TODO
        # monitor.sh novo morrer calado no "flock -n 200 || exit 0" la em
        # cima, e o monitor nunca mais volta. O proprio mode.sh ja se
        # protege assim do seu lock (201>&-). Diagnosticado com fuser
        # apontando a polybar como dona do tarsila-wincount.lock (02/08).
        setsid -f /usr/local/bin/tarsila-polybar-mode.sh compact \
          >/dev/null 2>&1 200>&- 9>&- || \
          /usr/local/bin/tarsila-polybar-mode.sh compact \
            >/dev/null 2>&1 200>&- 9>&- &
      fi
    fi
  fi

  # wincount: grava e acorda as bolinhas so quando muda
  if [ "$n" != "$prev_n" ]; then
    echo "$n" > "$CACHE.tmp" && mv -f "$CACHE.tmp" "$CACHE"
    for p in genmon-37 genmon-38 genmon-39; do
      [ -f "${XDG_RUNTIME_DIR:-/tmp}/tarsila-openbox.session" ] || xfce4-panel --plugin-event=$p:refresh:bool:true 2>/dev/null
    done
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
