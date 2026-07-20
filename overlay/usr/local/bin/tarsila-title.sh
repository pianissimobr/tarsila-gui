#!/bin/bash
# Script do genmon (painel): quando maximizado (bolinha 3), mostra o nome
# da janela ativa no lado esquerdo do top bar. Nos outros estados fica
# vazio. Os botoes de fechar/restaurar ficam em plugins proprios
# (tarsila-close-btn.sh / tarsila-restore-btn.sh).
# Fonte/peso seguem o estilo da barra do Tarsila Store (css/store.css).
#
# Este script e o "lider" do grupo: e o unico que roda xdotool/xprop; os
# seguidores (close-btn/restore-btn) so leem MAX e ID do arquivo de
# estado gravado aqui.
#
# As bolinhas de workspace moram num painel proprio (panel-2) fixo no
# centro da tela, entao o titulo NAO precisa mais medir a propria largura
# (ImageMagick) nem gravar TW/CHANGED_AT para espacador/apagao - esse
# mecanismo todo foi removido. O titulo e truncado para nao invadir a
# area central das bolinhas.
STATE="${XDG_RUNTIME_DIR:-/tmp}/tarsila-topbar-state.txt"
TMP="$STATE.tmp.$$"
MAX_CHARS=60

prev_max=0
if [ -f "$STATE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in MAX) prev_max=$v;; esac
  done < "$STATE"
fi

id=$(xdotool getactivewindow 2>/dev/null)
if [ -n "$id" ] && xprop -id "$id" _NET_WM_STATE 2>/dev/null | grep -q MAXIMIZED; then
  max=1
else
  max=0
fi

if [ "$max" = "1" ]; then
  name=$(xdotool getwindowname "$id" 2>/dev/null)
  # apps nativos do sistema mostram um nome fixo e amigavel no top bar,
  # em vez do titulo tecnico real da janela (que as vezes muda por
  # pagina/arquivo aberto, ex: qpdfview e o configurador). Casado por
  # WM_CLASS (mais estavel que o titulo exibido), nao pelo texto.
  wmclass=$(xprop -id "$id" WM_CLASS 2>/dev/null | sed -n 's/.*"\([^"]*\)", "[^"]*".*/\1/p')
  case "$wmclass" in
    Thunar) name="Arquivos" ;;
    galculator) name="Calculadora" ;;
    tarsila-config) name="Ajustes" ;;
    qpdfview) name="Leitor de PDF" ;;
  esac
  if [ "${#name}" -gt "$MAX_CHARS" ]; then
    name="${name:0:$MAX_CHARS}…"
  fi
  printf 'MAX=1\nID=%s\n' "$id" > "$TMP" && mv -f "$TMP" "$STATE"
  esc_name=$(printf '%s' "$name" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')
  echo "<txt><span font_family='DejaVu Sans' weight='semibold' size='11000'>   $esc_name</span></txt>"
else
  printf 'MAX=0\nID=\n' > "$TMP" && mv -f "$TMP" "$STATE"
  echo "<txt></txt>"
fi

# Cobre maximizacao/restauracao por caminhos fora dos tarsila-goto*
# (arrastar janela, atalho de teclado, devilspie2): quando MAX muda,
# acorda bolinhas e botoes na hora - eles pollam devagar (10s) e sem
# isso so reagiriam no proximo ciclo. Em background para nao atrasar a
# propria saida deste plugin.
if [ "$max" != "$prev_max" ]; then
  (
    for p in genmon-37 genmon-38 genmon-39 genmon-40 genmon-41; do
      xfce4-panel --plugin-event=$p:refresh:bool:true 2>/dev/null
    done
  ) &
fi
