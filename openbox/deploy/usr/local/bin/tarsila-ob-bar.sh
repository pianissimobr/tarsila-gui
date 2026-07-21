#!/bin/bash
# Fonte única do ambiente do polybar: lê o tema salvo (cores) e a
# resolução real (geometria), exporta TB_* e (re)sobe a barra. Chamado no
# login (por tarsila-ob-wallpaper-apply.sh) e ao trocar de tema
# (tarsila-ob-tema-apply.sh). Substitui o mecanismo xfconf de cor/tamanho
# de painel do XFCE.
CFG="$HOME/.config/tarsila"
TEMA=padrao; [ -f "$CFG/tema" ] && read -r TEMA < "$CFG/tema"
case "$TEMA" in
  maritimo)      TB_BG=#194350; TB_FG=#f2f6f7; TB_DIM=#5a7c86 ;;
  escuro)        TB_BG=#101014; TB_FG=#e8e8ea; TB_DIM=#55555c ;;
  brasileiro)    TB_BG=#1B472C; TB_FG=#f4f7f2; TB_DIM=#5f8a70 ;;
  personalizado) TB_BG=#EDF1F4; TB_FG=#2a2e32; TB_DIM=#9aa4ac ;;
  *)             TB_BG=#EDF1F4; TB_FG=#2a2e32; TB_DIM=#9aa4ac ;;
esac
H=$(xrandr --query 2>/dev/null | sed -n 's/.* connected \(primary \)\?[0-9]\+x\([0-9]\+\)+.*/\2/p' | head -1)
[ -z "$H" ] && H=768
if   [ "$H" -gt 1600 ]; then TB_HEIGHT=64; TB_FONT=20; TB_ICON=18; TB_DOT=22
elif [ "$H" -gt 900 ];  then TB_HEIGHT=44; TB_FONT=14; TB_ICON=13; TB_DOT=16
else                         TB_HEIGHT=34; TB_FONT=11; TB_ICON=11; TB_DOT=13
fi
# cores dos pontos (aceso/apagado) vão por ambiente para o dots.sh
export TB_FG TB_DIM
# gera o config efetivo a partir do template (polybar 3.7 não expande
# ${env:...} dentro do arquivo, então resolvemos aqui com sed)
TPL="$HOME/.config/polybar/config.ini"
GEN="$HOME/.config/polybar/config.gen.ini"
sed -e "s/__HEIGHT__/$TB_HEIGHT/g" \
    -e "s/__FONT__/$TB_FONT/g" \
    -e "s/__ICON__/$TB_ICON/g" \
    -e "s/__DOT__/$TB_DOT/g" \
    -e "s/__BG__/$TB_BG/g" \
    -e "s/__FG__/$TB_FG/g" \
    -e "s#__HOME__#$HOME#g" \
    "$TPL" > "$GEN"
polybar-msg cmd quit >/dev/null 2>&1
sleep 0.3
polybar -c "$GEN" tarsila >/tmp/polybar-tarsila.log 2>&1 &
