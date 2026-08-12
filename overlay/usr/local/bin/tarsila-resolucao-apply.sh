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

SAIDA=$(xrandr --query 2>/dev/null | awk '/ connected/{print $1; exit}')
[ -n "$SAIDA" ] || exit 0

# O modo esta na lista desta saida?
if ! xrandr --query 2>/dev/null | sed -n "/^$SAIDA connected/,/^[^ ]/p" \
     | grep -qE "^[[:space:]]+$MODO[[:space:]]"; then
    exit 0
fi

# Ja esta nele? Nao mexe -- trocar de modo pisca a tela sem necessidade.
ATUAL=$(xrandr --query 2>/dev/null | awk -v s="$SAIDA" '$1==s{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+x[0-9]+\+/){split($i,a,"+"); print a[1]; exit}}')
[ "$ATUAL" = "$MODO" ] && exit 0

xrandr --output "$SAIDA" --mode "$MODO" 2>/dev/null
exit 0
