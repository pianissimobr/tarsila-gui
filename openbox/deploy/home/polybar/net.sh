#!/bin/bash
# Indicador de rede: icone Font Awesome 4 (bytes UTF-8), herda a cor do
# texto do tema. Clique abre nm-connection-editor (config.ini).
WIRED=$(printf '\xef\x87\xa6')   # plug (FA4 nao tem ethernet)
WIFI=$(printf '\xef\x87\xab')    # wifi
OFF=$(printf '\xef\x81\x9e')     # ban
st=$(nmcli -t -f TYPE,STATE device 2>/dev/null)
if   echo "$st" | grep -q '^ethernet:connected'; then G=$WIRED
elif echo "$st" | grep -q '^wifi:connected';     then G=$WIFI
else G=$OFF; fi
printf '%%{T3}%s%%{T-}\n' "$G"
