#!/bin/bash
# Lança a Tarsila Store como app nativo: sobe o backend (se preciso) e
# abre o Chromium em modo --app apontando para o servidor local.
PORTA=8474
NOSSO=0

if ! pgrep -f "tarsila-backend.py" > /dev/null; then
    mkdir -p "$HOME/.local/share/tarsila-store"
    # -u: sem buffer - o log recebe as linhas na hora, não só quando o
    # processo morre (o backend.log ficava sempre vazio, 0 bytes)
    #
    # 9>&- : a trava de "uma janela só" (tarsila-uma-janela) vive no descritor
    # 9 deste processo. Sem fechá-la aqui, o backend a herda e a mantém viva
    # DEPOIS que a janela fecha -- e a Store não abre mais, em silêncio.
    # Aconteceu: o backend ficou 3 horas segurando a trava com a loja fechada.
    nohup python3 -u /opt/tarsila-store/bin/tarsila-backend.py \
        >> "$HOME/.local/share/tarsila-store/backend.log" 2>&1 9>&- &
    NOSSO=$!
    for _ in $(seq 1 20); do
        curl -sf "http://127.0.0.1:$PORTA/api/instalados" > /dev/null && break
        sleep 0.25
    done
fi

# Sem "exec": este shell precisa continuar vivo para (1) segurar a trava de
# "uma janela só" enquanto a loja estiver aberta, que é o tempo certo, e (2)
# encerrar o backend quando ela fechar.
#
# O navegador vai para SEGUNDO PLANO de propósito. Esperar por ele não serve:
# o processo do Chromium só termina quando a última janela dele fecha -- se o
# usuário tiver o navegador aberto em outra janela, ficaríamos presos aqui
# para sempre. E se ele já estiver rodando, o comando volta na hora, porque
# apenas pede a janela à instância existente. Nos dois casos quem diz a
# verdade é a JANELA, não o processo.
( chromium --app="http://127.0.0.1:$PORTA" --start-maximized \
      --disable-extensions --no-first-run --disk-cache-size=16777216 2>/dev/null \
  || firefox --kiosk "http://127.0.0.1:$PORTA" ) &

if command -v xdotool >/dev/null 2>&1; then
    # --onlyvisible e obrigatorio: sem ele o xdotool acha tambem janelas ja
    # fechadas que o Chromium ainda nao destruiu, e a espera nunca terminava.
    janela(){ xdotool search --onlyvisible --name "Tarsila Store" 2>/dev/null | head -1; }
    for _ in $(seq 1 60); do
        [ -n "$(janela)" ] && break
        sleep 0.5
    done
    while [ -n "$(janela)" ]; do
        sleep 2
    done
fi

# Encerra o backend que NÓS subimos. Ele só serve a esta janela; antes ficava
# rodando para sempre, segurando 11,5 MB e a porta 8474 -- e, pior, a trava de
# "uma janela só", o que fazia a loja nunca mais abrir.
[ "$NOSSO" != 0 ] && kill "$NOSSO" 2>/dev/null
exit 0
