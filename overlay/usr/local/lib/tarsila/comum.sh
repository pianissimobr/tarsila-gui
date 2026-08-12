# Biblioteca comum dos scripts de aparencia. E "sourced", nao executada:
#     . /usr/local/lib/tarsila/comum.sh
#
# POR QUE EXISTE
#
# O mesmo punhado de decisoes estava escrito em varios arquivos ao mesmo
# tempo -- e onde ha copia, ha divergencia. As que existiam de fato:
#
#   * o mapa tema -> tema da Dock, em tarsila-tema-apply.sh e em
#     tarsila-dock-apply.sh;
#   * o tamanho do icone da Dock por altura de tela, em
#     tarsila-wallpaper-apply.sh (calculado) e em tarsila-dock-apply.sh
#     (52 fixo, escrito a cada login DEPOIS do calculado -- numa TV de
#     1080p ou 4K o icone voltava ao tamanho de 768p sozinho);
#   * a leitura da altura da tela, em tres arquivos;
#   * a pintura do papel de parede, em dois.
#
# Aqui cada uma dessas decisoes existe uma vez so.
#
# Nada neste arquivo escreve na tela ou no disco por conta propria: sao
# funcoes puras (perguntas) mais uma que pinta o fundo quando chamada.

TARSILA_CFG="${XDG_CONFIG_HOME:-$HOME/.config}/tarsila"
TARSILA_WALLDIR=/usr/share/tarsila/wallpapers
TARSILA_WALLPAPER_PADRAO=/usr/share/backgrounds/tarsila-wallpaper.png

# Tema escolhido pelo usuario na pagina Aparencia do Ajustes.
tema_salvo() {
    local t=""
    [ -r "$TARSILA_CFG/tema" ] && read -r t < "$TARSILA_CFG/tema"
    printf '%s\n' "${t:-padrao}"
}

# Imagem que acompanha cada tema. O "personalizado" nao aparece aqui de
# proposito: a imagem dele e um arquivo do usuario, e quem sabe qual e o
# tema-wallpaper gravado (ver wallpaper_salvo).
wallpaper_do_tema() {
    case "$1" in
        maritimo)   printf '%s\n' "$TARSILA_WALLDIR/tema-maritimo.png" ;;
        escuro)     printf '%s\n' "$TARSILA_WALLDIR/tema-escuro.png" ;;
        brasileiro) printf '%s\n' "$TARSILA_WALLDIR/tema-brasileiro.png" ;;
        *)          printf '%s\n' "$TARSILA_WALLPAPER_PADRAO" ;;
    esac
}

# O papel de parede em vigor: o que foi gravado na ultima troca de tema.
# Se o arquivo sumiu (imagem pessoal que estava num pendrive), volta ao
# padrao em vez de deixar a tela sem fundo.
wallpaper_salvo() {
    local wp=""
    [ -r "$TARSILA_CFG/tema-wallpaper" ] && read -r wp < "$TARSILA_CFG/tema-wallpaper"
    [ -n "$wp" ] && [ -f "$wp" ] || wp="$TARSILA_WALLPAPER_PADRAO"
    printf '%s\n' "$wp"
}

# Tema do Plank que combina com o tema do sistema.
#
# O "personalizado" fica no Tarsila (azul-marinho) junto com o padrao: a
# Dock clara ficava bonita com a area de trabalho limpa, mas com varias
# janelas abertas se confundia com elas e sumia no meio da tela.
dock_do_tema() {
    case "$1" in
        maritimo)   printf 'Tarsila-Maritimo\n' ;;
        escuro)     printf 'Tarsila-Escuro\n' ;;
        brasileiro) printf 'Tarsila-Brasileiro\n' ;;
        *)          printf 'Tarsila\n' ;;
    esac
}

# Altura real da tela. A tvbox nao troca de resolucao em tempo de execucao
# -- o modo e negociado com a TV no boot e varia por aparelho (720p, 768,
# 1080p, 4K) --, entao tudo que depende de tamanho de tela se recalcula no
# login. 768 e o desenho base, usado quando o xrandr nao responde.
altura_tela() {
    local h=""
    h=$(xrandr --query 2>/dev/null \
        | sed -n 's/.* connected \(primary \)\?[0-9]\+x\([0-9]\+\)+.*/\2/p' | head -1)
    printf '%s\n' "${h:-768}"
}

# Tamanho do icone da Dock para a altura de tela. Pixels pensados para 768p
# ficam minusculos em 4K.
icone_dock() {
    local h="${1:-}"
    [ -n "$h" ] || h=$(altura_tela)
    if   [ "$h" -gt 1600 ]; then printf '104\n'
    elif [ "$h" -gt  900 ]; then printf '72\n'
    else                         printf '52\n'
    fi
}

# PINTA O PAPEL DE PAREDE
#
# Era uma linha solta, repetida em dois scripts:
#
#     feh --no-fehbg --bg-fill "$WP" 2>/dev/null
#
# e o feh NAO esta instalado nesta imagem (o dpkg nao conhece o pacote).
# Com o erro mandado para /dev/null, trocar de tema gravava a escolha,
# trocava a cor da barra e da Dock -- e nao pintava fundo nenhum, calado.
#
# A tvbox nao tem internet para instalar nada, entao a ordem aqui e: usar o
# feh se ele existir (e o que roda na TV de referencia) e, se nao, o
# ImageMagick, que JA esta instalado (convert + display). O convert
# redimensiona cobrindo a tela e recorta o excesso -- o equivalente do
# --bg-fill. Ultimo recurso: cor solida, para nunca ficar com o xadrez
# cinza do X na cara do usuario.
#
# Devolve 0 se pintou.
pinta_fundo() {
    local wp="$1" geom="" tmp=""
    [ -n "$wp" ] && [ -f "$wp" ] || return 1

    if command -v feh >/dev/null 2>&1; then
        feh --no-fehbg --bg-fill "$wp" 2>/dev/null && return 0
    fi
    if command -v xwallpaper >/dev/null 2>&1; then
        xwallpaper --zoom "$wp" 2>/dev/null && return 0
    fi
    if command -v hsetroot >/dev/null 2>&1; then
        hsetroot -fill "$wp" 2>/dev/null && return 0
    fi
    if command -v convert >/dev/null 2>&1 && command -v display >/dev/null 2>&1; then
        geom=$(xrandr --query 2>/dev/null \
               | sed -n 's/.* connected \(primary \)\?\([0-9]\+x[0-9]\+\)+.*/\2/p' | head -1)
        [ -n "$geom" ] || geom=1366x768
        tmp=$(mktemp --suffix=.png 2>/dev/null) || return 1
        if convert "$wp" -resize "${geom}^" -gravity center -extent "$geom" "$tmp" 2>/dev/null; then
            # QUEM DECIDE AQUI E O CONVERT, NAO O DISPLAY.
            #
            # Medido nesta imagem: com um gerenciador de janelas no ar, o
            # "display -window root" pinta a raiz certinho e mesmo assim SAI
            # COM 1, sem escrever nada no erro padrao; sem gerenciador, sai 0.
            # Confiar nesse codigo de saida fazia a funcao achar que tinha
            # falhado e cair na cor solida por cima do papel de parede que ela
            # acabara de pintar. O convert, esse sim, falha de verdade quando
            # a imagem nao presta -- e e ele quem le o arquivo.
            display -window root "$tmp" >/dev/null 2>&1
            rm -f "$tmp"
            return 0
        fi
        rm -f "$tmp"
    fi
    command -v xsetroot >/dev/null 2>&1 && xsetroot -solid '#1f2530' 2>/dev/null
    return 1
}
