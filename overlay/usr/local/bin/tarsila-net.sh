#!/bin/bash
# Indicador de rede no top bar (genmon). TRÊS estados, guiados por "tem
# internet de verdade?" (CONNECTIVITY do NetworkManager — ele já monitora,
# custo zero p/ nós):
#   1) sem internet          -> "x" (tom mais claro)
#   2) internet pelo cabo    -> ícone RJ45
#   3) internet pelo Wi-Fi   -> ícone de sinal proporcional (%)
# Clique abre a janela "Conexões de rede" (seção Wi-Fi).
IC="$HOME/.cache/tarsila/topbar"
PAP=/usr/share/icons/Papirus/22x22/symbolic

st=$(nmcli -t -f TYPE,STATE device 2>/dev/null)
conn=$(nmcli -t -f CONNECTIVITY general status 2>/dev/null | tr -d '\n')

eth_up=0; wifi_up=0
echo "$st" | grep -q '^ethernet:connected' && eth_up=1
echo "$st" | grep -q '^wifi:connected'     && wifi_up=1

pick() {  # $1 = nome base; usa o recolorido do tema, senão o do Papirus
  if [ -f "$IC/$1.svg" ]; then echo "$IC/$1.svg"
  elif [ -f "$PAP/status/$1-symbolic.svg" ]; then echo "$PAP/status/$1-symbolic.svg"
  elif [ -f "$PAP/devices/$1-symbolic.svg" ]; then echo "$PAP/devices/$1-symbolic.svg"
  else echo "$PAP/status/network-offline-symbolic.svg"; fi
}

if [ "$conn" != "full" ]; then
  # conectado ou não, sem internet de verdade -> X claro
  ICON=$(pick net-off); [ -f "$ICON" ] || ICON="$PAP/status/network-offline-symbolic.svg"
  if [ "$eth_up" = 1 ] || [ "$wifi_up" = 1 ]; then TIP="Conectado, mas sem internet"; else TIP="Sem conexão de rede"; fi
elif [ "$eth_up" = 1 ]; then
  ICON=$(pick net-wired); TIP="Internet pelo cabo de rede"
elif [ "$wifi_up" = 1 ]; then
  sig=$(nmcli -t -f IN-USE,SIGNAL device wifi list 2>/dev/null | awk -F: '$1=="*"{print $2; exit}')
  [ -z "$sig" ] && sig=0
  if   [ "$sig" -ge 70 ]; then base=network-wireless-signal-excellent
  elif [ "$sig" -ge 45 ]; then base=network-wireless-signal-good
  elif [ "$sig" -ge 20 ]; then base=network-wireless-signal-ok
  else                        base=network-wireless-signal-weak; fi
  # cache do tema usa nomes curtos (net-wifi-*), senão cai no Papirus
  case "$base" in
    *excellent) ICON=$(pick net-wifi-4) ;;
    *good)      ICON=$(pick net-wifi-3) ;;
    *ok)        ICON=$(pick net-wifi-2) ;;
    *)          ICON=$(pick net-wifi-1) ;;
  esac
  [ -f "$ICON" ] || ICON="$PAP/status/$base-symbolic.svg"
  TIP="Wi-Fi conectado · sinal ${sig}%"
else
  ICON=$(pick net-off); TIP="Sem conexão de rede"
fi

[ -f "$ICON" ] || ICON="$PAP/status/network-offline-symbolic.svg"
echo "<img>$ICON</img>"
echo "<tool>$TIP</tool>"
echo "<click>/usr/local/bin/tarsila-wifi</click>"
