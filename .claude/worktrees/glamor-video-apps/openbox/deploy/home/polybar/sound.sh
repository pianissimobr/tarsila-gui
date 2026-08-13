#!/bin/bash
# Volume: so o icone Font Awesome 4 (sem porcentagem). Le o sink padrao
# do PipeWire (wpctl); scroll ajusta, clique abre pavucontrol.
VOL=$(printf '\xef\x80\xa8')    # volume-up
MUTE=$(printf '\xef\x80\xa6')   # volume-off
line=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null)
if [ -z "$line" ]; then
  pct=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oP '\d+(?=%)' | head -1)
  pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q yes && m=1 || m=0
else
  pct=$(printf '%s' "$line" | awk '{printf "%d", $2*100}')
  printf '%s' "$line" | grep -q MUTED && m=1 || m=0
fi
if [ "${m:-0}" = 1 ] || [ -z "$pct" ]; then
  printf '%%{T3}%s%%{T-}\n' "$MUTE"
else
  printf '%%{T3}%s%%{T-}\n' "$VOL"
fi
