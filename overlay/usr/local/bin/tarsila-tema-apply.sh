#!/bin/bash
# Em sessao Openbox, delega para a versao que fala com polybar/feh (sem
# xfconf/xfce4-panel, que geram o dialog "org.xfce.Panel").
case "${XDG_CURRENT_DESKTOP:-}" in *Openbox*) exec /usr/local/bin/tarsila-ob-tema-apply.sh "$@" ;; esac
# Aplica um tema visual do Tarsila: papel de parede + cor do top bar +
# cor do texto do top bar. Roda como o usuario logado (chamado pela
# pagina Aparencia do Ajustes). Persiste a escolha em ~/.config/tarsila/
# para o tarsila-wallpaper-apply.sh (autostart) manter no proximo login.
#
# Temas: padrao | maritimo | escuro | brasileiro | personalizado <imagem>
# - padrao: visual atual (barra transparente, wallpaper original)
# - maritimo/escuro/brasileiro: wallpaper proprio + barra em cor solida
#   que combina (media do topo da imagem, escurecida) + texto claro
# - personalizado: imagem escolhida pelo usuario + barra gelo + texto
#   escuro (cores do padrao no resto)
set -u
TEMA="${1:-padrao}"
IMAGEM="${2:-}"
WALLDIR=/usr/share/tarsila/wallpapers
PADRAO_WP=/usr/share/backgrounds/tarsila-wallpaper.png
CFG="$HOME/.config/tarsila"
GTKCSS="$HOME/.config/gtk-3.0/gtk.css"
mkdir -p "$CFG" "$HOME/.config/gtk-3.0"

# Serializa aplicacoes de tema: dois cliques proximos rodavam em
# paralelo e o segundo `xfce4-panel -r` pegava o painel no meio do
# reinicio do primeiro - sem painel no D-Bus, o proprio xfce4-panel
# abre o dialogo "Falha ao enviar mensagem D-Bus" na tela do usuario.
exec 9>"$CFG/.tema-apply.lock"
flock 9

case "$TEMA" in
  padrao)
    WP=$PADRAO_WP;                   RGBA="0 0 0 0";               TXT="";        DOCK="Tarsila" ;;
  maritimo)
    WP=$WALLDIR/tema-maritimo.png;   RGBA="0.098 0.263 0.310 1";   TXT="#f2f6f7"; DOCK="Tarsila-Maritimo" ;;
  escuro)
    WP=$WALLDIR/tema-escuro.png;     RGBA="0.063 0.063 0.078 1";   TXT="#e8e8ea"; DOCK="Tarsila-Escuro" ;;
  brasileiro)
    WP=$WALLDIR/tema-brasileiro.png; RGBA="0.106 0.278 0.173 1";   TXT="#f4f7f2"; DOCK="Tarsila-Brasileiro" ;;
  personalizado)
    if [ -z "$IMAGEM" ] || [ ! -f "$IMAGEM" ]; then
      echo "uso: $0 personalizado <imagem>" >&2
      exit 1
    fi
    # copia a imagem: se o usuario apagar o arquivo original (pendrive,
    # Downloads), o papel de parede continua existindo
    mkdir -p "$HOME/.local/share/tarsila"
    WP="$HOME/.local/share/tarsila/wallpaper-pessoal.${IMAGEM##*.}"
    cp -f "$IMAGEM" "$WP"
    RGBA="0.929 0.945 0.957 1";      TXT="#2a2e32"; DOCK="Tarsila-Gelo" ;;
  *)
    echo "tema desconhecido: $TEMA" >&2
    exit 1 ;;
esac

# tarsila-topbar-recolor: recolore os icones do top bar (fechar/restaurar/
# rede) para a cor do texto do tema. padrao usa a cor base #444444, entao
# nao muda; nos temas escuros os icones ficam claros (seguem o texto).
ICONDIR="$HOME/.cache/tarsila/topbar"
mkdir -p "$ICONDIR"
ICONCOL="${TXT:-#444444}"
PAPSYM=/usr/share/icons/Papirus/22x22/symbolic
sed "s/fill:#444444/fill:$ICONCOL/g" /usr/local/share/tarsila/close-padded.svg > "$ICONDIR/close.svg" 2>/dev/null || true
sed "s/fill:#444444/fill:$ICONCOL/g" /usr/local/share/tarsila/restore-square-padded.svg > "$ICONDIR/restore.svg" 2>/dev/null || true
sed "s/color:#444444/color:$ICONCOL/g" "$PAPSYM/devices/network-wired-symbolic.svg" > "$ICONDIR/net-wired.svg" 2>/dev/null || true
sed "s/color:#444444/color:$ICONCOL/g" "$PAPSYM/status/network-wireless-signal-excellent-symbolic.svg" > "$ICONDIR/net-wireless.svg" 2>/dev/null || true
sed "s/color:#444444/color:$ICONCOL/g" "$PAPSYM/status/network-offline-symbolic.svg" > "$ICONDIR/net-off.svg" 2>/dev/null || true
# acorda o genmon de rede p/ pegar a cor nova na hora
xfce4-panel --plugin-event=genmon-44:refresh:bool:true >/dev/null 2>&1 || true
# tarsila-topbar-recolor fim

# papel de parede em todas as saidas de video (nomes variam entre boxes)
for out in $(xrandr --query 2>/dev/null | awk '/ connected/{print $1}'); do
  base="/backdrop/screen0/monitor${out}/workspace0"
  xfconf-query -c xfce4-desktop -p "$base/last-image" -n -t string -s "$WP" 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/last-image" -s "$WP" 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/image-style" -n -t int -s 5 2>/dev/null
  xfconf-query -c xfce4-desktop -p "$base/image-style" -s 5 2>/dev/null
done
xfdesktop --reload >/dev/null 2>&1 || true

# cor de fundo dos DOIS paineis (panel-1 = top bar; panel-2 = bolinhas,
# que fica sobreposto ao top bar e precisa da mesma cor)
set -- $RGBA
for p in panel-1 panel-2; do
  xfconf-query -c xfce4-panel -p "/panels/$p/background-style" -n -t uint -s 1 2>/dev/null
  xfconf-query -c xfce4-panel -p "/panels/$p/background-style" -s 1 2>/dev/null
  xfconf-query -c xfce4-panel -p "/panels/$p/background-rgba" --force-array \
      -t double -s "$1" -t double -s "$2" -t double -s "$3" -t double -s "$4" 2>/dev/null \
  || xfconf-query -c xfce4-panel -p "/panels/$p/background-rgba" -n --force-array \
      -t double -s "$1" -t double -s "$2" -t double -s "$3" -t double -s "$4" 2>/dev/null
done

# tema do Dock (Plank) combinando com o top bar - o plank observa a
# chave e recarrega o tema sozinho, sem reiniciar
dconf write /net/launchpad/plank/docks/dock1/theme "'$DOCK'" 2>/dev/null || true

# cor do texto do top bar via bloco gerenciado no gtk.css do usuario
# (o relogio, o titulo do app e os botoes do painel herdam esta cor)
TMPCSS=$(mktemp)
if [ -f "$GTKCSS" ]; then
  sed '/\/\* tarsila-tema inicio \*\//,/\/\* tarsila-tema fim \*\//d' "$GTKCSS" > "$TMPCSS"
else
  : > "$TMPCSS"
fi
if [ -n "$TXT" ]; then
  cat >> "$TMPCSS" <<EOF
/* tarsila-tema inicio */
.xfce4-panel { color: $TXT; }
/* tarsila-tema fim */
EOF
fi

# o reinicio do painel so e necessario se o gtk.css realmente mudou
# (trocar entre dois temas de texto claro, por exemplo, nao muda nada)
PRECISA_RESTART=0
cmp -s "$TMPCSS" "$GTKCSS" 2>/dev/null || PRECISA_RESTART=1
mv -f "$TMPCSS" "$GTKCSS"

# persiste a escolha (lida pelo tarsila-wallpaper-apply.sh no login)
echo "$TEMA" > "$CFG/tema"
echo "$WP" > "$CFG/tema-wallpaper"

if [ "$PRECISA_RESTART" = "1" ]; then
  # so pede o -r com o painel presente e respondendo no D-Bus; sem essa
  # checagem o proprio comando xfce4-panel abre um dialogo de erro
  # ("Falha ao enviar mensagem D-Bus") na tela do usuario leigo
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if dbus-send --session --dest=org.xfce.Panel --print-reply \
         /org/xfce/Panel org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
      xfce4-panel -r >/dev/null 2>&1
      exit 0
    fi
    sleep 0.5
  done
  # painel fora do bus apos a espera: sobe um novo se nao houver processo
  pgrep -u "$USER" -x xfce4-panel >/dev/null 2>&1 || ( setsid xfce4-panel >/dev/null 2>&1 & )
fi
exit 0
