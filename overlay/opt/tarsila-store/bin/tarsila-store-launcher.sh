#!/bin/bash
# Lança a Tarsila Store como app nativo: sobe o backend (se preciso) e
# abre o Chromium em modo --app apontando para o servidor local.
PORTA=8474
if ! pgrep -f "tarsila-backend.py" > /dev/null; then
    mkdir -p "$HOME/.local/share/tarsila-store"
    # -u: sem buffer - o log recebe as linhas na hora, não só quando o
    # processo morre (o backend.log ficava sempre vazio, 0 bytes)
    nohup python3 -u /opt/tarsila-store/bin/tarsila-backend.py \
        >> "$HOME/.local/share/tarsila-store/backend.log" 2>&1 &
    for _ in $(seq 1 20); do
        curl -sf "http://127.0.0.1:$PORTA/api/instalados" > /dev/null && break
        sleep 0.25
    done
fi
exec chromium --app="http://127.0.0.1:$PORTA" --start-maximized \
     --disable-extensions --no-first-run --disk-cache-size=16777216 2>/dev/null \
  || exec firefox --kiosk "http://127.0.0.1:$PORTA"
