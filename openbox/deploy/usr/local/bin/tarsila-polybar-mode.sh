#!/usr/bin/env bash
# Topbar Estado A (full) | Estado B (compact) — só por evento explícito.
#
#   A / full    → largura 100%, fundo cinza (tela-estados via MAX=1),
#                 modules-left = topbar
#   B / compact → faixa à direita até o relógio, transparente (MAX=0),
#                 modules-left vazio
#
# Quem chama:
#   B→A: tarsila-goto3.sh (maximize) | devilspie Chromium
#   A→B: tarsila-goto2.sh (desmaximizar) | tarsila-topbar-close.sh (✕)
#   boot: tarsila-ob-bar.sh → compact
#
# Uso: tarsila-polybar-mode.sh full|compact [WINDOW_ID]
set -euo pipefail
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
trap '' HUP

MODE="${1:-}"
WIN_ID="${2:-}"
GEN="${XDG_CONFIG_HOME:-$HOME/.config}/polybar/config.gen.ini"
MODE_FILE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-polybar-mode.txt"
TOP="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/tarsila-polybar-mode.lock"
CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/tarsila"
WW_CACHE="$CFG_DIR/bar-compact-glyph"
WW_PNG="$CFG_DIR/.bar-compact-glyph.png"
mkdir -p "$CFG_DIR" 2>/dev/null || true

case "$MODE" in
  full|A) MODE=full ;;
  compact|B) MODE=compact ;;
  *) echo "uso: $0 full|compact [WINDOW_ID]" >&2; exit 2 ;;
esac

[ -f "$GEN" ] || exit 0

exec 201>"$LOCK"
flock -w 8 201 || exit 1

# QUAL E O MODO DE VERDADE (06/08)
#
# Ate aqui isto vinha do MODE_FILE, um arquivo de texto -- e o arquivo pode
# mentir. Ele e escrito ANTES do trabalho (linha "printf ... >MODE_FILE" mais
# abaixo) e reescrito depois; se o script morrer no meio -- morto, SIGPIPE,
# flock estourando os 8 s, polybar que nao volta -- fica gravado "full" com a
# barra ainda em compact. E como o desvio logo abaixo confia nesse arquivo,
# TODO pedido de "full" seguinte sai fora sem fazer nada.
#
# Sintoma exato, medido em 06/08: o Chromium maximiza, o Plank se recolhe
# (ele reage a janela maximizada de verdade), e a barra e o botao da Dock
# ficam onde estavam -- o botao parado no meio da tela. Uma vez funciona,
# outra nao, dependendo de o arquivo ter ficado sujo antes.
#
# Agora a pergunta e feita a quem manda: o config que da forma a barra, mais
# a barra estar no ar. Se nao houver polybar rodando, nao ha modo nenhum e o
# trabalho e feito de qualquer jeito.
prev=""
if pgrep -x polybar >/dev/null 2>&1; then
  if grep -qE '^modules-left[[:space:]]*=[[:space:]]*[a-z]' "$GEN"; then
    prev=full
  else
    prev=compact
  fi
fi

write_top() {
  if [ "$MODE" = "full" ]; then
    local id="$WIN_ID"
    if [ -z "$id" ] && [ -f "$TOP" ]; then
      id=$(sed -n 's/^ID=//p' "$TOP" | head -1)
    fi
    if [ -z "$id" ]; then
      id=$(xdotool getactivewindow 2>/dev/null || true)
    fi
    printf 'MAX=1\nID=%s\n' "$id" >"$TOP"
  else
    printf 'MAX=0\nID=\n' >"$TOP"
  fi
}

# Mesmo estado: só atualiza ID no A (ex.: Chromium de novo) sem reiniciar.
if [ "$prev" = "$MODE" ]; then
  write_top
  exit 0
fi

write_top

sw=$(xdpyinfo 2>/dev/null | awk '/dimensions:/{print $2}' | cut -d x -f1)
[ -n "$sw" ] || sw=1366

compact_w() {
  local ww w
  # A largura do glifo "▼" e uma constante (so depende da fonte, que nao
  # muda entre toggles). Medir com pango-view + identify (ImageMagick) a cada
  # alternancia full/compact era desperdicio: dois processos pesados por
  # clique de maximizar/desmaximizar. Mede-se UMA vez e guarda em cache.
  ww=$(cat "$WW_CACHE" 2>/dev/null)
  if [ -z "$ww" ]; then
    if command -v pango-view >/dev/null 2>&1 && command -v identify >/dev/null 2>&1; then
      pango-view --font="DejaVu Sans 12" -q -t "▼" --output="$WW_PNG" 2>/dev/null \
        && ww=$(identify -format "%w" "$WW_PNG" 2>/dev/null)
      rm -f "$WW_PNG" 2>/dev/null || true
    fi
    if [ -n "$ww" ]; then
      printf '%s' "$ww" > "$WW_CACHE" 2>/dev/null || true
    else
      ww=14
    fi
  fi
  # date + ▼ + limpar + sound + netw + power + pads
  w=$((70 + ww + 14 + 36 + 42 + 36 + 36 + 28))
  [ "$w" -lt 240 ] && w=240
  [ "$w" -gt "$sw" ] && w=$sw
  echo "$w"
}

if [ "$MODE" = "full" ]; then
  WIDTH="100%"
  OFFSET="0"
  LEFT="topbar"
else
  WIDTH="$(compact_w)"
  OFFSET=$((sw - WIDTH))
  [ "$OFFSET" -lt 0 ] && OFFSET=0
  LEFT=""
fi

awk -v w="$WIDTH" -v ox="$OFFSET" -v left="$LEFT" '
  BEGIN { inbar=0 }
  /^\[bar\/tarsila\]/ { inbar=1 }
  inbar && /^width[[:space:]]*=/ { print "width = " w; next }
  inbar && /^offset-x[[:space:]]*=/ { print "offset-x = " ox; next }
  inbar && /^modules-left[[:space:]]*=/ { print "modules-left = " left; next }
  /^\[/ && $0 !~ /^\[bar\/tarsila\]/ { inbar=0 }
  { print }
' "$GEN" >"$GEN.tmp" && mv -f "$GEN.tmp" "$GEN"

write_top

polybar-msg cmd quit >/dev/null 2>&1 || true
pkill -x polybar >/dev/null 2>&1 || true
for _ in 1 2 3 4 5 6; do
  pgrep -x polybar >/dev/null 2>&1 || break
  pkill -x polybar >/dev/null 2>&1 || true
  sleep 0.12
done
sleep 0.15
nohup polybar -q -c "$GEN" tarsila </dev/null >/dev/null 2>&1 201>&- &
disown || true
sleep 0.45
if ! pgrep -x polybar >/dev/null 2>&1; then
  sleep 0.3
  nohup polybar -q -c "$GEN" tarsila </dev/null >/dev/null 2>&1 201>&- &
  disown || true
  sleep 0.4
fi
write_top
