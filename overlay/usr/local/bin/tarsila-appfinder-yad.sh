#!/bin/bash
export NO_AT_BRIDGE=1
set -uo pipefail

CURATED_DIR="/usr/share/tarsila/applications"
GAMES_DIR="/usr/share/tarsila/games"
ICONS_DIR="/usr/share/tarsila/icons"
VERMAIS_DESKTOP="$CURATED_DIR/vermais-tarsila.desktop"
DOCK_DCONF_KEY="/net/launchpad/plank/docks/dock1/dock-items"
WHITELIST="/opt/tarsila-store/whitelist.txt"
PKG_HELPER="/opt/tarsila-store/bin/tarsila-pkg"
NATIVES_FILE="/usr/share/tarsila/native-apps.txt"
DOCK_MANAGER="/usr/local/bin/tarsila-dock-manager"
ICON_HELPER="/usr/local/bin/tarsila-icon-cache"
ICON_SIZE=48
# Tamanho com que a janela abre -- o que o usuario deixou ao ajustar na mao.
JANELA_LARG=405
JANELA_ALT=500
# Onde o pe da janela fica em relacao ao topo da janela da Dock. O valor veio
# de MEDIR a posicao que o usuario escolheu na mao (ele posicionou, eu derivei):
# o pe cai 29px dentro da faixa do Plank, que ali ainda e area transparente
# acima dos icones -- por isso encosta sem cobrir nada.
DESCE_ATE=29
# O yad PEDE uma posicao, mas o gerenciador de janelas soma a barra de titulo e
# a borda antes de desenhar: pedindo 185 a janela nasceu em 218. Descontamos
# isso ao pedir, para ela ja nascer no lugar em vez de aparecer e pular.
# Nao sao coordenadas de tela -- e a espessura da decoracao que o gerenciador
# acrescenta, propriedade do tema da janela. Medido: +8 na horizontal, +64 na
# vertical (a barra de titulo mais as bordas).
COMPENSA_X=8
COMPENSA_Y=64


# Onde abrir: encostada no fim da Dock, subindo a partir dela, como um menu que
# sai do proprio botao "Ver mais". Em vez de chutar a largura da Dock (o Plank
# ocupa a tela inteira, mas so pinta o pedaco do meio), medimos a janela DELE e
# vemos ate onde ela esta pintada. Assim o calculo continua certo se o usuario
# acrescentar icones ou mudar o tamanho deles.
posicao_junto_da_dock() {
    local plank px py pw ph
    plank=$(xdotool search --class plank 2>/dev/null | while read -r w; do
                eval "$(xdotool getwindowgeometry --shell "$w" 2>/dev/null)"
                [ "${WIDTH:-0}" -gt 1000 ] && echo "$w"
            done | head -n1)
    [ -n "$plank" ] || return 1
    eval "$(xdotool getwindowgeometry --shell "$plank" 2>/dev/null)" || return 1
    px=$X; py=$Y
    import -window "$plank" "$TMP_DIR/dock.png" 2>/dev/null || return 1
    python3 - "$TMP_DIR/dock.png" "$px" "$py" "$JANELA_LARG" "$JANELA_ALT" \
             "$DESCE_ATE" <<'PY'
import sys
from PIL import Image

arq, px, py, larg, alt, desce = sys.argv[1:7]
px, py, larg, alt, desce = map(int, (px, py, larg, alt, desce))
im = Image.open(arq).convert("RGB")
w, h = im.size
p = im.load()
canto = p[2, 2]                      # canto transparente/vazio da janela

def pintado(c):
    return sum(abs(a - b) for a, b in zip(c, canto)) > 30

meio = h // 2
xs = [x for x in range(w) if pintado(p[x, meio])]
if not xs:
    raise SystemExit(1)
# So a medida horizontal vem dos pixels. A vertical NAO: 'import -window'
# entrega a janela do Plank ja composta com o papel de parede, que tem
# gradiente, entao comparar com o canto acusa "pintado" onde ha so fundo.
# Para o eixo Y basta o topo da propria janela do Plank, que e exato.
direita = px + xs[-1]                # onde a Dock termina, na tela
print("%d %d" % (direita - larg, py - alt + desce))
PY
}



# Apps nativos do sistema (Arquivos, Configuração, Store, Terminal,
# Lixeira): ficam sempre na Dock e fora desta grade - gerenciados so
# pela posicao no Gerenciar Dock.
declare -A native_desktops
if [ -f "$NATIVES_FILE" ]; then
    while IFS= read -r nb; do
        [ -n "$nb" ] && native_desktops["$CURATED_DIR/$nb"]=1
    done < "$NATIVES_FILE"
fi

# Detecta usuário real
if [ -n "${SUDO_USER:-}" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$(whoami)"
fi
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
DOCK_CONFIG="$REAL_HOME/.config/plank/dock1/launchers/"
mkdir -p "$DOCK_CONFIG" 2>/dev/null || true

# Carrega apps curados
declare -A curated_apps
for f in "$CURATED_DIR"/*.desktop; do
    [ -e "$f" ] || continue
    name=$(sed -n 's/^Name=//p' "$f" | head -n1)
    [ -n "$name" ] && curated_apps["$name"]="$f"
done

# Os jogos moram numa pasta so deles. Antes o botao "Jogos" da Dock era o
# gerenciador de arquivos abrindo essa pasta: o usuario via arquivos .desktop
# soltos, nao uma tela de jogos. Agora sao a segunda aba desta janela.
declare -A game_apps
for f in "$GAMES_DIR"/*.desktop; do
    [ -e "$f" ] || continue
    name=$(sed -n 's/^Name=//p' "$f" | head -n1)
    [ -n "$name" ] && game_apps["$name"]="$f"
done

# Mapa unico para procurar o escolhido: os botoes (Executar, Desinstalar)
# ficam na janela de fora e valem para as duas abas, entao a busca pelo
# caminho gravado precisa enxergar aplicativos e jogos juntos.
declare -A todos_apps aba_de
for name in "${!curated_apps[@]}"; do
    todos_apps["$name"]="${curated_apps[$name]}"
    aba_de["$name"]="apps"
done
for name in "${!game_apps[@]}"; do
    todos_apps["$name"]="${game_apps[$name]}"
    aba_de["$name"]="jogos"
done

if [ ${#todos_apps[@]} -eq 0 ]; then
    yad --info --center --title="Aplicativos instalados" \
        --text="Nenhum aplicativo encontrado em:\n$CURATED_DIR" \
        --width=400 --height=100
    exit 0
fi

# Reescreve a ordem do dock no Plank ao vivo (sem precisar relogar),
# sempre deixando "Ver mais aplicativos" por último.
sync_dock_order() {
    command -v dconf &>/dev/null || return 0
    local f base items="" vermais_item=""
    for f in "$DOCK_CONFIG"/*.dockitem; do
        [ -e "$f" ] || continue
        base=$(basename "$f")
        if grep -q "^Launcher=file://$VERMAIS_DESKTOP\$" "$f" 2>/dev/null; then
            vermais_item="$base"
            continue
        fi
        items+="'$base', "
    done
    [ -n "$vermais_item" ] && items+="'$vermais_item', "
    [ -n "$items" ] || return 0
    items="[${items%, }]"
    dconf write "$DOCK_DCONF_KEY" "$items" 2>/dev/null || true
}

# O Plank desta versão só carrega itens novos de forma confiável ao
# iniciar (a descoberta ao vivo via inotify tem o bug do Launcher=
# vazio, ver pin_to_dock, e além disso o ícone não aparece na tela até
# reiniciar). Por isso, depois de qualquer mudança no dock, reiniciamos
# o Plank para refletir o estado correto imediatamente.
restart_plank() {
    command -v plank &>/dev/null || return 0
    pkill -x plank 2>/dev/null
    sleep 0.3
    if [ -x /usr/local/bin/tarsila-dock-apply.sh ]; then
        /usr/local/bin/tarsila-dock-apply.sh 2>/dev/null
    fi
    nohup plank >/dev/null 2>&1 &
    disown
}

uninstall_app() {
    local app_name="$1"
    local desktop_file="${todos_apps[$app_name]}"
    local exec_line exec_cmd exec_path package_name=""

    exec_line=$(sed -n 's/^Exec=//p' "$desktop_file" | head -n1)
    exec_cmd=${exec_line%% *}

    # Atalhos web (chromium --app=URL) não são um pacote próprio:
    # resolver pelo Exec= apontaria para o navegador, e "desinstalar"
    # a Agenda removeria o Chromium inteiro.
    if [[ "$exec_line" == *"--app="* ]]; then
        yad --info --center --fixed --title="Desinstalar" \
            --text="'$app_name' é um atalho do sistema e não pode ser desinstalado por aqui." \
            --width=380
        return 0
    fi

    if grep -q "^X-Package=" "$desktop_file" 2>/dev/null; then
        package_name=$(sed -n 's/^X-Package=//p' "$desktop_file" | head -n1)
    elif [ -n "$exec_cmd" ]; then
        # dpkg -S com caminho completo é uma busca exata; com o nome
        # solto seria busca por substring e podia acertar outro pacote.
        exec_path=$(command -v "$exec_cmd" 2>/dev/null || true)
        if [ -n "$exec_path" ]; then
            package_name=$(dpkg -S "$exec_path" 2>/dev/null | cut -d: -f1 | head -n1)
        fi
    fi

    # A desinstalação passa pelo tarsila-pkg (sudo NOPASSWD + whitelist).
    # "sudo apt remove" direto não funciona para o usuário comum: não há
    # NOPASSWD para apt e, rodando sem terminal, a senha nunca é pedida.
    if [ -z "$package_name" ] || ! grep -qxF "$package_name" "$WHITELIST" 2>/dev/null; then
        yad --info --center --fixed --title="Desinstalar" \
            --text="'$app_name' faz parte do sistema e não pode ser desinstalado." \
            --width=380
        return 0
    fi

    if ! yad --question --center --fixed --title="Desinstalar" \
             --text="Deseja realmente desinstalar '$app_name'?" \
             --width=400; then
        return 0
    fi
    # Tira o app da grade imediatamente (a janela reabre em seguida ja
    # sem ele; a remocao real continua em segundo plano). Se falhar, a
    # notificacao avisa e o app volta na proxima abertura do AppFinder.
    rm -f "$TMP_DIR/${aba_de[$app_name]}/${app_name}.desktop"
    (
        if sudo -n "$PKG_HELPER" remove "$package_name" >/dev/null 2>&1; then
            find "$DOCK_CONFIG" -name "*.dockitem" 2>/dev/null | while read -r dockitem; do
                if grep -q "$(basename "$desktop_file")" "$dockitem" 2>/dev/null; then
                    rm -f "$dockitem"
                fi
            done
            sync_dock_order
            restart_plank
            if command -v notify-send &>/dev/null; then
                notify-send "Desinstalação concluída" "'$app_name' foi removido."
            fi
        else
            if command -v notify-send &>/dev/null; then
                notify-send "Desinstalação falhou" "Não foi possível remover '$app_name'."
            fi
        fi
    ) &
    yad --info --center --fixed --title="Desinstalando" \
        --text="A desinstalação de '$app_name' está em andamento em segundo plano." \
        --timeout=3
    return 0
}

# Preparação: criar diretório com arquivos .desktop para o YAD --icons
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT
SELECTION_FILE="$TMP_DIR/.selected"
# Chave que liga as abas a janela-caderno do yad.
YAD_KEY=$$

# O yad --icons desta versão não reporta de forma confiável o item
# selecionado quando ha varios botoes customizados na mesma janela
# (apenas o ultimo botao da lista responde a cliques nesse modo).
# Por isso cada .desktop gerado aqui, ao ser ativado (duplo clique),
# apenas grava o caminho do app original em SELECTION_FILE em vez de
# executa-lo direto - as acoes reais (Executar/Fixar/Desinstalar) sao
# escolhidas depois, num dialogo comum (nao-icones), onde os botoes
# funcionam normalmente em qualquer posicao.
mkdir -p "$TMP_DIR/wrappers" "$TMP_DIR/apps" "$TMP_DIR/jogos"

# Fase 1: resolve o ícone de cada app e monta o lote do cache de
# ícones. O yad 0.40 não redimensiona ícones que já vêm grandes
# (SVG/256px, ex.: MyPaint e Orage estouravam a grade); por isso todo
# ícone é pré-renderizado em PNG de ICON_SIZE px pelo tarsila-icon-cache
# (Python/GTK, que resolve nome de tema e redimensiona) num cache
# persistente por usuário - só ícones novos são renderizados de novo.
ICON_CACHE="$REAL_HOME/.cache/tarsila/icons$ICON_SIZE"
mkdir -p "$ICON_CACHE" 2>/dev/null || true
ICON_BATCH="$TMP_DIR/.icon-batch"
declare -A tile_icon_spec tile_icon_png
for name in "${!todos_apps[@]}"; do
    desktop_file="${todos_apps[$name]}"
    # "Ver mais aplicativos" é o próprio botão que abre esta tela - não
    # faz sentido listá-lo como uma opção dentro dela mesma. Apps
    # nativos também ficam de fora (sempre na Dock, ver native-apps.txt).
    [ "$desktop_file" = "$VERMAIS_DESKTOP" ] && continue
    [ -n "${native_desktops[$desktop_file]:-}" ] && continue
    icon=$(grep '^Icon=' "$desktop_file" | head -n1 | cut -d= -f2)
    if [ -z "$icon" ]; then
        icon="application-x-executable"
    elif [[ ! "$icon" =~ ^/ ]]; then
        # Se não for absoluto, procura primeiro na pasta de ícones do
        # Tarsila; se não achar, mantém o nome como está (em vez de
        # cair para um genérico) - é um nome de ícone de tema (ex.:
        # x-office-document, application-pdf) que o tema de ícones do
        # sistema (Papirus) resolve sozinho.
        if [ -f "$ICONS_DIR/${icon}.png" ]; then
            icon="$ICONS_DIR/${icon}.png"
        elif [ -f "$ICONS_DIR/${icon}.svg" ]; then
            icon="$ICONS_DIR/${icon}.svg"
        fi
    fi
    tile_icon_spec["$name"]="$icon"
    cached="$ICON_CACHE/$(printf '%s' "$icon" | md5sum | cut -d' ' -f1).png"
    tile_icon_png["$name"]="$cached"
    if [ ! -s "$cached" ] || { [[ "$icon" == /* ]] && [ "$icon" -nt "$cached" ]; }; then
        printf '%s\t%s\t%d\n' "$icon" "$cached" "$ICON_SIZE" >> "$ICON_BATCH"
    fi
done
if [ -s "$ICON_BATCH" ] && [ -x "$ICON_HELPER" ]; then
    "$ICON_HELPER" < "$ICON_BATCH" >/dev/null 2>&1 || true
fi

# Fase 2: gera os .desktop da grade, usando o PNG normalizado quando o
# cache deu certo (senão cai no ícone original, como antes).
wrapper_i=0
for name in "${!tile_icon_spec[@]}"; do
    desktop_file="${todos_apps[$name]}"
    icon="${tile_icon_spec[$name]}"
    [ -s "${tile_icon_png[$name]}" ] && icon="${tile_icon_png[$name]}"
    # Script wrapper dedicado: evita as regras de citação do campo
    # Exec= do formato .desktop (diferentes das do shell), que quebravam
    # ao embutir aspas/variáveis direto na linha Exec.
    wrapper_i=$((wrapper_i + 1))
    wrapper="$TMP_DIR/wrappers/$wrapper_i.sh"
    cat > "$wrapper" << EOF
#!/bin/sh
printf '%s' "$desktop_file" > "$SELECTION_FILE"
EOF
    chmod +x "$wrapper"
    # Cria arquivo .desktop no TMP_DIR
    cat > "$TMP_DIR/${aba_de[$name]}/${name}.desktop" << EOF
[Desktop Entry]
Name=$name
Exec=$wrapper
Icon=$icon
Type=Application
EOF
    chmod +x "$TMP_DIR/${aba_de[$name]}/${name}.desktop"
done

# Loop principal. O toque num app grava a seleção em SELECTION_FILE
# (ver comentário dos wrappers acima) e o item fica marcado; a ação vem
# dos botões da própria janela - não há mais diálogo intermediário.
# A janela só se encerra de vez no X/Esc ou ao Executar um app;
# Desinstalar e Gerenciar Dock voltam para ela (o "continue" reabre a
# grade na mesma hora, já relendo o TMP_DIR - por isso um app
# desinstalado some da grade ao voltar).
while true; do
    rm -f "$SELECTION_FILE"

    # Duas abas na mesma janela. Um menu de selecao nao caberia aqui: a
    # grade de icones do yad ocupa a janela inteira, entao a escolha teria de
    # virar um dialogo ANTES da grade - uma pergunta a mais toda vez que se
    # abre a tela. A aba nao custa passo nenhum.
    # Cada aba e um yad "plugado" na janela-caderno; os botoes ficam na janela
    # de fora e servem as duas, porque a escolha ja e gravada em
    # SELECTION_FILE pelos wrappers (ver comentario acima).
    yad --plug=$YAD_KEY --tabnum=1 --icons --read-dir="$TMP_DIR/apps" \
        --sort-by-name --icon-size=48 --item-width=100 \
        --icon-theme=Papirus --single-click 2>/dev/null &
    plug_apps=$!
    yad --plug=$YAD_KEY --tabnum=2 --icons --read-dir="$TMP_DIR/jogos" \
        --sort-by-name --icon-size=48 --item-width=100 \
        --icon-theme=Papirus --single-click 2>/dev/null &
    plug_jogos=$!
    sleep 1                 # as abas precisam existir antes da janela-caderno

    # --fixed trava o tamanho: sem isso a janela abriria redimensionavel e com
    # botao de maximizar, que nao fazem sentido numa grade de icones -- e o
    # usuario pediu os dois fora. O yad marca min=max nas dicas de tamanho e o
    # Openbox, vendo isso, ja esconde o botao e recusa o arrasto das bordas.
    POS=$(posicao_junto_da_dock 2>/dev/null)
    if [ -n "$POS" ]; then
        set -- $POS
        # --geometry em vez de --posx/--posy: o yad aplica a posicao DEPOIS de
        # mostrar a janela, e da o pulinho que se ve ao abrir. A geometria e
        # lida pelo GTK antes de exibir, entao a janela ja nasce no lugar --
        # e o que faz a Lixeira (programa nosso, que move antes de mostrar)
        # nao piscar.
        LUGAR="--geometry=${JANELA_LARG}x${JANELA_ALT}+$(( $1 - COMPENSA_X ))+$(( $2 - COMPENSA_Y ))"
    else
        LUGAR="--center"          # sem Dock visivel, volta ao meio da tela
    fi

    yad --notebook --key=$YAD_KEY \
        --tab="Aplicativos" \
        --tab="Jogos" \
        --fixed \
        $LUGAR \
        --title="Aplicativos Instalados" \
        --width=$JANELA_LARG --height=$JANELA_ALT \
        --button="Executar:0" \
        --button="Desinstalar:2" \
        --button="Gerenciar Dock:5" 2>/dev/null
    yad_rc=$?
    kill $plug_apps $plug_jogos 2>/dev/null

    case $yad_rc in
        5) # Gerenciar Dock - ao fechar, volta para a grade
            if [ -x "$DOCK_MANAGER" ]; then
                "$DOCK_MANAGER" 2>/dev/null
            fi
            continue
            ;;
        0|2) # Executar/Desinstalar - precisam de um app escolhido
            ;;
        *) # X ou Esc - unico jeito de sair
            exit 0
            ;;
    esac

    if [ ! -s "$SELECTION_FILE" ]; then
        yad --info --center --fixed --title="Escolha um aplicativo" \
            --text="Toque primeiro em um aplicativo da lista\ne depois no botão desejado." \
            --timeout=3
        continue
    fi

    # Identifica o app escolhido a partir do caminho gravado
    desktop_path="$(cat "$SELECTION_FILE")"
    app_name=""
    for key in "${!todos_apps[@]}"; do
        if [ "${todos_apps[$key]}" == "$desktop_path" ]; then
            app_name="$key"
            break
        fi
    done
    if [ -z "$app_name" ]; then
        yad --warning --center --fixed --title="Erro" \
            --text="Aplicativo não encontrado." \
            --timeout=2
        continue
    fi

    if [ "$yad_rc" = "0" ]; then
        # Executar - sem "exec": assim o trap ainda limpa o TMP_DIR
        gio launch "${todos_apps[$app_name]}" >/dev/null 2>&1 &
        disown
        exit 0
    fi

    # Desinstalar (a janela reabre em seguida, sem o app se confirmado)
    uninstall_app "$app_name"
done
