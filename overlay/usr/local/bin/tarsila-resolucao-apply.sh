#!/bin/bash
# Reaplica no login a resolucao escolhida na tela de Ajustes.
#
# REGRA DE OURO: so aplica se o modo EXISTIR na saida conectada agora.
# Este produto roda em TVs diferentes. Ja se tentou fixar a resolucao no
# boot.config (video=HDMI-A-1:1366x768@60) e isso QUEBRA a box quando ela vai
# para outra TV -- a negociacao automatica por EDID e o comportamento correto.
# Aqui a escolha do usuario e apenas uma PREFERENCIA: se a TV atual oferece
# aquele modo, respeitamos; se nao oferece, saimos calados e fica o negociado.
#
# Roda ANTES do tarsila-wallpaper-apply.sh, que calcula a geometria da barra a
# partir da altura da tela -- se rodasse depois, a barra ficaria dimensionada
# para a resolucao errada.

export DISPLAY="${DISPLAY:-:0}"
CFG="${XDG_CONFIG_HOME:-$HOME/.config}/tarsila/resolucao"

[ -f "$CFG" ] || exit 0
read -r MODO < "$CFG" 2>/dev/null
case "$MODO" in
    ''|*[!0-9x]*) exit 0 ;;   # so aceita algo como 1366x768
esac

# Uma unica leitura do xrandr: os tres usos abaixo (saida, lista de modos e
# modo atual) passam a beber da mesma captura. Era 3x `xrandr --query` -- cada
# um negocia de novo com a GPU, e no login isso pesa junto com o resto que sobe.
XRANDR=$(xrandr --query 2>/dev/null)
[ -n "$XRANDR" ] || exit 0

SAIDA=$(printf '%s\n' "$XRANDR" | awk '/ connected/{print $1; exit}')
[ -n "$SAIDA" ] || exit 0

# O modo esta na lista desta saida?
if ! printf '%s\n' "$XRANDR" | sed -n "/^$SAIDA connected/,/^[^ ]/p" \
     | grep -qE "^[[:space:]]+$MODO[[:space:]]"; then
    exit 0
fi

# Ja esta nele? Nao mexe -- trocar de modo pisca a tela sem necessidade.
ATUAL=$(printf '%s\n' "$XRANDR" | awk -v s="$SAIDA" '$1==s{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+x[0-9]+\+/){split($i,a,"+"); print a[1]; exit}}')
[ "$ATUAL" = "$MODO" ] && exit 0

xrandr --output "$SAIDA" --mode "$MODO" 2>/dev/null
exit 0
