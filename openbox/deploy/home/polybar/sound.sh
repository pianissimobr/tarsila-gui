#!/bin/bash
# Volume: so o icone Font Awesome 4 (sem porcentagem). Le o sink padrao
# do PipeWire (wpctl); scroll ajusta, clique abre pavucontrol.
VOL=$(printf '\xef\x80\xa8')    # volume-up
MUTE=$(printf '\xef\x80\xa6')   # volume-off
line=$(wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null)
if [ -z "$line" ]; then
  # fallback PulseAudio (pactl)
  pct=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oP '\d+(?=%)' | head -1)
  m=$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -q yes && echo 1 || echo 0)
else
  # uma unica passagem: extrai a porcentagem e a flag de mute do mesmo stdout
  # (antes eram dois processos por ciclo: awk + grep).
  read -r pct m < <(printf '%s' "$line" | awk '{p=int($2*100); m=(index($0,"MUTED")?1:0); printf "%d %d", p, m}')
fi
if [ "${m:-0}" = 1 ] || [ -z "$pct" ]; then
  printf '%%{T3}%s%%{T-}\n' "$MUTE"
else
  printf '%%{T3}%s%%{T-}\n' "$VOL"
fi
