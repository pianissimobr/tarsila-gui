#!/bin/bash
# Indicador de rede: icone Font Awesome 4 (bytes UTF-8), herda a cor do
# texto do tema. Clique abre nm-connection-editor (config.ini).
# Cabo = globo (rede/internet); wifi = antenas; sem rede = ban.
#
# Event-driven: em vez de rodar 'nmcli' a cada 5s (polling, acordando a CPU
# da TV Box 12x/min sem necessidade), o 'nmcli monitor' fica residente e so
# reavalia quando o NetworkManager avisa mudanca (conectou/desconectou).
# Cai para polling suave caso o monitor nao exista ou morra.
WIRED=$(printf '\xef\x82\xac')   # globe
WIFI=$(printf '\xef\x87\xab')    # wifi
OFF=$(printf '\xef\x81\x9e')     # ban

icon() {
  local st
  st=$(nmcli -t -f TYPE,STATE device 2>/dev/null)
  case "$st" in
    *ethernet:connected*) G=$WIRED ;;
    *wifi:connected*)     G=$WIFI ;;
    *)                    G=$OFF ;;
  esac
  printf '%%{T3}%s%%{T-}\n' "$G"
}

icon
if nmcli monitor 2>/dev/null | while IFS= read -r _; do icon; done; then
  exit 0
fi
# fallback: monitor indisponivel/encerrado -> polling suave
while true; do sleep 5; icon; done
