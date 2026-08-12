#!/bin/bash
# Fonte unica do ambiente do polybar: le o tema salvo (cores) e a
# resolucao real (geometria), exporta TB_* e (re)sobe a barra. Chamado no
# login (por tarsila-wallpaper-apply.sh) e ao trocar de tema
# (tarsila-tema-apply.sh).
#
# Ao final sobe em Estado B (compact). Estado A so por goto3 / Chromium.
. /usr/local/lib/tarsila/comum.sh
CFG="$TARSILA_CFG"
TEMA=$(tema_salvo)

case "$TEMA" in
  maritimo)      TB_BG=#194350; TB_FG=#f2f6f7; TB_DIM=#5a7c86 ;;
  escuro)        TB_BG=#101014; TB_FG=#e8e8ea; TB_DIM=#55555c ;;
  brasileiro)    TB_BG=#1B472C; TB_FG=#f4f7f2; TB_DIM=#5f8a70 ;;
  *)             TB_BG=#EDF1F4; TB_FG=#2a2e32; TB_DIM=#9aa4ac ;;
esac
H=$(altura_tela)
TB_DATE=10
if   [ "$H" -gt 1600 ]; then TB_HEIGHT=45; TB_FONT=14; TB_ICON=13; TB_DOT=14; TB_CAP=56
elif [ "$H" -gt 900 ];  then TB_HEIGHT=31; TB_FONT=12; TB_ICON=11; TB_DOT=12; TB_CAP=38
else                         TB_HEIGHT=24; TB_FONT=11; TB_ICON=10; TB_DOT=11; TB_CAP=36
fi
mkdir -p "$CFG"
echo "$TB_HEIGHT" > "$CFG/bar-height"
# A cor solida vai para um arquivo e NAO para a barra: quem a pinta e o
# tarsila-tela-estados, so no Estado A (MAX=1 gravado por mode.sh).
echo "$TB_BG" > "$CFG/bar-bg"
TB_BG=#00000000
/usr/local/bin/tarsila-ob-margins.sh &
export TB_FG TB_DIM

TPL="$HOME/.config/polybar/config.ini"
GEN="$HOME/.config/polybar/config.gen.ini"
sed -e "s/__HEIGHT__/$TB_HEIGHT/g" \
    -e "s/__FONT__/$TB_FONT/g" \
    -e "s/__ICON__/$TB_ICON/g" \
    -e "s/__DOT__/$TB_DOT/g" \
    -e "s/__DATE__/$TB_DATE/g" \
    -e "s/__BG__/$TB_BG/g" \
    -e "s/__FG__/$TB_FG/g" \
    -e "s/__CAP__/$TB_CAP/g" \
    -e "s/__SEP__/$TB_DIM/g" \
    -e "s#__HOME__#$HOME#g" \
    "$TPL" > "$GEN"

polybar-msg cmd quit >/dev/null 2>&1 || true
pkill -x polybar 2>/dev/null || true
sleep 0.2

# Limpa orfaos de sessoes anteriores
pkill -x xprop 2>/dev/null || true
pkill -f "polybar/topbar.sh" 2>/dev/null || true
pkill -f "polybar/title.sh" 2>/dev/null || true
pkill -f "polybar/buttons.sh" 2>/dev/null || true
pkill -f "polybar/dots.sh" 2>/dev/null || true

# O tarsila-polybar-mode.txt foi abandonado em 06/08 (podia mentir e travar a
# troca para "full"). Ninguem o escreve desde entao, entao nao ha o que
# limpar aqui. O "rm -f" que existia neste ponto so mantinha o arquivo
# permanentemente ausente -- e o topbar.sh, que ainda o lia, imprimia um
# erro de shell na barra a cada 2 s por causa disso.
printf "MAX=0\nID=\n" > "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/tarsila-topbar-state.txt"

# Boot = Estado B (compact).
/usr/local/bin/tarsila-polybar-mode.sh compact

# Hitboxes (X Shape Input): sobe em background depois que a barra ja esta no ar.
# Antes rodava via shape-watcher (dbus-monitor de systray, obsoleto desde 02/08).
(sleep 1; /usr/local/bin/tarsila-polybar-hitboxes.py 2>/dev/null || true) &
