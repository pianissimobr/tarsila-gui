#!/bin/bash
# Fonte única do ambiente do polybar: lê o tema salvo (cores) e a
# resolução real (geometria), exporta TB_* e (re)sobe a barra. Chamado no
# login (por tarsila-ob-wallpaper-apply.sh) e ao trocar de tema
# (tarsila-ob-tema-apply.sh). Substitui o mecanismo xfconf de cor/tamanho
# de painel do XFCE.
CFG="$HOME/.config/tarsila"
TEMA=padrao; [ -f "$CFG/tema" ] && read -r TEMA < "$CFG/tema"
# A barra voltou a acompanhar o tema, menos no padrao (2026-07-28).
#
# Em 26/07 ela tinha sido fixada na cor clara do padrao, porque abriga o titulo
# da janela ativa e os botoes de fechar/restaurar, e esse conjunto destoava
# sobre teal, verde ou preto. O que mudou desde entao: sem janela maximizada a
# barra ficou TRANSPARENTE, e os escritos passaram a cair direto sobre o papel
# de parede. Nos temas escuros, texto escuro sobre papel escuro nao se le.
#
# Por isso os outros temas recebem fonte clara. E o fundo tem de acompanhar:
# quando ha janela maximizada o retangulo solido volta, e fonte clara sobre
# fundo claro seria igualmente ilegivel. O padrao fica exatamente como estava.
case "$TEMA" in
  maritimo)      TB_BG=#194350; TB_FG=#f2f6f7; TB_DIM=#5a7c86 ;;
  escuro)        TB_BG=#101014; TB_FG=#e8e8ea; TB_DIM=#55555c ;;
  brasileiro)    TB_BG=#1B472C; TB_FG=#f4f7f2; TB_DIM=#5f8a70 ;;
  *)             TB_BG=#EDF1F4; TB_FG=#2a2e32; TB_DIM=#9aa4ac ;;
esac
H=$(xrandr --query 2>/dev/null | sed -n 's/.* connected \(primary \)\?[0-9]\+x\([0-9]\+\)+.*/\2/p' | head -1)
[ -z "$H" ] && H=768
if   [ "$H" -gt 1600 ]; then TB_HEIGHT=64; TB_FONT=20; TB_ICON=18; TB_DOT=22; TB_CAP=56
elif [ "$H" -gt 900 ];  then TB_HEIGHT=44; TB_FONT=14; TB_ICON=13; TB_DOT=16; TB_CAP=38
else                         TB_HEIGHT=34; TB_FONT=11; TB_ICON=11; TB_DOT=13; TB_CAP=40
fi
mkdir -p "$CFG"
echo "$TB_HEIGHT" > "$CFG/bar-height"
# A cor solida vai para um arquivo e NAO para a barra: quem a pinta agora e o
# tarsila-tela-estados, e so quando ha janela maximizada. Sem nada maximizado
# a barra fica transparente e os icones flutuam sobre o papel de parede.
echo "$TB_BG" > "$CFG/bar-bg"
TB_BG=#00000000
/usr/local/bin/tarsila-ob-margins.sh &
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
    -e "s/__CAP__/$TB_CAP/g" \
    -e "s/__SEP__/$TB_DIM/g" \
    -e "s#__HOME__#$HOME#g" \
    "$TPL" > "$GEN"
polybar-msg cmd quit >/dev/null 2>&1
sleep 0.3
# O nome do mes no relogio sai pelo idioma do processo, e o polybar nao
# herdava nenhum: mostrava "28 de July" num sistema em portugues. O LC_TIME
# vem do idioma escolhido pelo usuario em /etc/default/locale, entao trocar o
# idioma do sistema continua trocando o mes junto.
LC_TIME=$(. /etc/default/locale 2>/dev/null; echo "${LC_TIME:-${LANG:-pt_BR.UTF-8}}")
export LC_TIME
polybar -c "$GEN" tarsila >/tmp/polybar-tarsila.log 2>&1 &
