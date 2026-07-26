#!/bin/bash
# Sobe o picom da sessão Openbox (xrender + cantos arredondados).
# NÃO usar picom.conf (GLX) nesta box — congela a sessão (~45% CPU).
CONF=/usr/share/tarsila/picom-xrender.conf
pkill -x picom 2>/dev/null || true
sleep 0.2
if [ -f "$CONF" ]; then
  picom -b --config "$CONF" 2>/dev/null || \
    picom -b --backend xrender --no-use-damage --config /dev/null 2>/dev/null || true
else
  picom -b --backend xrender --no-use-damage --config /dev/null 2>/dev/null || true
fi
