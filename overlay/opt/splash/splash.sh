#!/bin/bash
ICON="/opt/splash/ico.png"
MESSAGE="Iniciando o sistema ..."
TIMEOUT=120
DM="lightdm gdm3 sddm lxdm xdm"

# Função para limpar o terminal e mostrar a mensagem de erro final
show_error() {
    clear
    echo -e "\n\n\n\n\e[31mErro: O seu computador não conseguiu carregar os arquivos necessários para a inicialização\e[0m"
}

# Sair de forma limpa quando o DM subir ou ao receber SIGTERM
trap 'kill %1 2>/dev/null; clear; exit 0' SIGTERM SIGINT

# Lança o fbi com a imagem, em background, sem bordas, no console atual (tty1 ou tty7)
# -a: escala a imagem para a tela; -T 1: usa VT1 (ajuste conforme necessário)
# fbi -a -T 1 --noverbose -d /dev/fb0 "$ICON" &   # ATENÇÃO: fbi geralmente precisa de root e do console
# Para iniciar num VT livre, faremos:
openvt -s -- fbi -a --noverbose -d /dev/fb0 "$ICON" &
FBI_PID=$!

# Espera um pouco para o fbi carregar
sleep 1

# Loop principal
dots=0
start=$(date +%s)
while true; do
    # Verifica se o gerenciador de login já iniciou
    for dm in $DM; do
        if pidof "$dm" > /dev/null; then
            kill $FBI_PID 2>/dev/null
            clear
            exit 0
        fi
    done

    # Monta a string com pontos animados
    case $((dots % 3)) in
        0) pts=".";;
        1) pts="..";;
        2) pts="...";;
    esac
    dots=$((dots+1))

    # Limpa a tela (apenas a parte do texto) e desenha com escape codes
    echo -ne "\r\033[K"  # limpa a linha
    # Posiciona o cursor no meio da tela (linha 12, coluna 0)
    tput cup 12 0
    # Centraliza manualmente? Vamos usar colunas
    echo -e "\033[1;37m${MESSAGE}${pts}\033[0m"

    sleep 0.5

    # Timeout: se passou TIMEOUT segundos, mostra erro
    if [ $(( $(date +%s) - start )) -ge $TIMEOUT ]; then
        break
    fi
done

# Se saiu do loop, é timeout -> erro
kill $FBI_PID 2>/dev/null
clear
show_error
# Mantém a tela de erro indefinidamente
while true; do sleep 60; done