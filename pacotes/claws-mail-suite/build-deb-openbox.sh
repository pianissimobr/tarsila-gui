#!/bin/bash
# ======================================================================
# build-deb-openbox.sh
#   Gera .deb do "claws-mail-suite" com Claws Mail EMBUTIDO (offline),
#   assistente grafico e integracao com OPENBOX (menu.xml + autostart).
#
# USO
#   ./build-deb-openbox.sh                     # arch/distro do host (nativo)
#   ./build-deb-openbox.sh arm64               # cross para arm64
#   ./build-deb-openbox.sh --mode none         # metapacote leve (usa internet)
#   ./build-deb-openbox.sh --mode full arm64   # offline total (grande)
#   ./build-deb-openbox.sh --distro raspbian:bookworm armhf
#   ./build-deb-openbox.sh --pkgs "claws-mail claws-mail-pgpmime"
#
# MODOS
#   auto (padrao) claws-mail + deps, sem priority required/important
#   full          tudo recursivo (inclui libc6 etc)
#   none          nao embute nada (Depends: claws-mail)
#
# Host precisa: dpkg-dev, apt, gzip  (opcional: apt-utils, wget)
# ======================================================================
set -euo pipefail

PKG_NAME="claws-mail-suite"
PKG_VERSION="4.0"
PKG_MAINTAINER="Seu Nome <email@exemplo.com>"
TARGET_PKGS=(claws-mail)
MODE="auto"; DISTRO_SPEC=""; MIRROR=""; ARCHES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --mode)   MODE="$2"; shift 2 ;;
    --distro) DISTRO_SPEC="$2"; shift 2 ;;
    --mirror) MIRROR="$2"; shift 2 ;;
    --pkgs)   IFS=' ' read -r -a TARGET_PKGS <<< "$2"; shift 2 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    -*) echo "opcao desconhecida: $1"; exit 1 ;;
    *)  ARCHES+=("$1"); shift ;;
  esac
done

need=(dpkg-deb gzip)
[ "$MODE" != none ] && need+=(apt-get apt-cache dpkg-scanpackages)
for t in "${need[@]}"; do
  command -v "$t" >/dev/null 2>&1 || { echo "ERRO: falta '$t' (apt install dpkg-dev apt-utils)"; exit 1; }
done

# shellcheck disable=SC1091
. /etc/os-release
[ ${#ARCHES[@]} -eq 0 ] && ARCHES=("$(dpkg --print-architecture)")
if [ -z "$DISTRO_SPEC" ]; then
  case "${ID:-debian}" in
    raspbian) DISTRO_SPEC="raspbian:${VERSION_CODENAME:-bookworm}" ;;
    ubuntu)   DISTRO_SPEC="ubuntu:${VERSION_CODENAME:-noble}" ;;
    *)        DISTRO_SPEC="debian:${VERSION_CODENAME:-bookworm}" ;;
  esac
fi
D_ID="${DISTRO_SPEC%%:*}"; SUITE="${DISTRO_SPEC##*:}"

keyring_de() {
  local k
  for k in "/usr/share/keyrings/$1-archive-keyring.gpg" \
           "/usr/share/keyrings/$1-archive-keyring.asc" \
           "/etc/apt/trusted.gpg.d/$1-archive-keyring.gpg"; do
    [ -f "$k" ] && { echo "$k"; return 0; }
  done
  return 1
}

escrever_sources() {            # $1=arquivo  $2=arch
  local f="$1" arch="$2" kr opt m sec
  case "$D_ID" in
    ubuntu)
      m="${MIRROR:-http://ports.ubuntu.com/ubuntu-ports}"
      if kr=$(keyring_de ubuntu); then opt="[arch=$arch signed-by=$kr]"
      else opt="[arch=$arch trusted=yes]"; fi
      printf 'deb %s %s %s main universe\n'          "$opt" "$m" "$SUITE"          >  "$f"
      printf 'deb %s %s %s-updates main universe\n'  "$opt" "$m" "$SUITE"          >> "$f"
      printf 'deb %s %s %s-security main universe\n' "$opt" "$m" "$SUITE"          >> "$f" ;;
    raspbian)
      m="${MIRROR:-http://raspbian.raspberrypi.com/raspbian}"
      if kr=$(keyring_de raspbian); then opt="[arch=$arch signed-by=$kr]"
      else opt="[arch=$arch trusted=yes]"; fi
      printf 'deb %s %s %s main contrib\n' "$opt" "$m" "$SUITE" > "$f"
      if kr=$(keyring_de raspberrypi); then
        printf 'deb [arch=%s signed-by=%s] http://archive.raspberrypi.com/debian %s main\n' \
               "$arch" "$kr" "$SUITE" >> "$f"
      fi ;;
    *)
      m="${MIRROR:-http://deb.debian.org/debian}"
      sec="http://security.debian.org/debian-security"
      if kr=$(keyring_de debian); then opt="[arch=$arch signed-by=$kr]"
      else opt="[arch=$arch trusted=yes]"; fi
      printf 'deb %s %s %s main\n'          "$opt" "$m"   "$SUITE" >  "$f"
      printf 'deb %s %s %s-updates main\n'  "$opt" "$m"   "$SUITE" >> "$f"
      printf 'deb %s %s %s-security main\n' "$opt" "$sec" "$SUITE" >> "$f" ;;
  esac
  grep -q 'trusted=yes' "$f" && echo "   AVISO: keyring '$D_ID' ausente -> trusted=yes (sem GPG)"
  return 0
}

PAYLOAD=$(mktemp -d); trap 'rm -rf "$PAYLOAD"' EXIT

# ======================================================================
#  A) ASSISTENTE GRAFICO (compativel com Openbox / WM minimo)
# ======================================================================
cat > "$PAYLOAD/configurar-claws" << '__FIM_ASSISTENTE__'
#!/bin/bash
# Assistente Claws Mail — Gmail/Outlook/IMAP, adaptado a Openbox.
set -uo pipefail

APP_TITLE="Assistente Claws Mail"
CLAWS_DIR="$HOME/.claws-mail"
ACCOUNTRC="$CLAWS_DIR/accountrc"
FOLDERLIST="$CLAWS_DIR/folderlist.xml"
MBOX="Mailbox"; MDIR="$HOME/Mail"
BKP="$CLAWS_DIR/backups-assistente"
SEP=$'\x1f'

command -v yad >/dev/null 2>&1 && GUI=yad || GUI=zenity
if [ "$GUI" = yad ]; then YOPT=(--center --on-top); else YOPT=(); fi

info(){ "$GUI" "${YOPT[@]}" --info     --title="$APP_TITLE" --width=470 --text="$1" >/dev/null 2>&1 || true; }
erro(){ "$GUI" "${YOPT[@]}" --error    --title="$APP_TITLE" --width=470 --text="$1" >/dev/null 2>&1 || true; }
perg(){ "$GUI" "${YOPT[@]}" --question --title="$APP_TITLE" --width=470 --text="$1" >/dev/null 2>&1; }

clip(){
  if   command -v wl-copy >/dev/null 2>&1; then printf '%s' "$1" | wl-copy 2>/dev/null
  elif command -v xclip   >/dev/null 2>&1; then printf '%s' "$1" | xclip -selection clipboard 2>/dev/null
  elif command -v xsel    >/dev/null 2>&1; then printf '%s' "$1" | xsel  --clipboard --input 2>/dev/null
  fi
}

# ---------------- COMPAT OPENBOX -------------------------------------
tem_agente_polkit(){
  pgrep -f 'polkit-(gnome|mate|kde|xfce|lxqt)-authentication-agent|lxpolkit|polkit-agent-helper' \
    >/dev/null 2>&1
}
terminal_de(){
  local t
  for t in x-terminal-emulator lxterminal xfce4-terminal mate-terminal tilix \
           konsole gnome-terminal alacritty kitty urxvt uxterm xterm; do
    command -v "$t" >/dev/null 2>&1 && { echo "$t"; return 0; }
  done
  return 1
}
# escalar_root <cmd...> : pkexec(com agente) > sudo -n > terminal > dialogo
escalar_root(){
  local T pw
  [ "$(id -u)" -eq 0 ] && { "$@"; return $?; }
  if command -v pkexec >/dev/null 2>&1 && tem_agente_polkit; then pkexec "$@"; return $?; fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then sudo "$@"; return $?; fi
  if T=$(terminal_de) && command -v sudo >/dev/null 2>&1; then
    "$T" -e "sh -c 'sudo $*; echo; printf \"Pressione Enter para fechar...\"; read _'" \
      >/dev/null 2>&1
    return 0
  fi
  pw=$("$GUI" "${YOPT[@]}" --entry --hide-text --title="$APP_TITLE" \
       --text="Senha de administrador (sudo):" 2>/dev/null) || return 1
  printf '%s\n' "$pw" | sudo -S -p '' "$@"
}
garantir_mime_navegador(){
  command -v xdg-mime >/dev/null 2>&1 || return 0
  [ -n "$(xdg-mime query default x-scheme-handler/https 2>/dev/null)" ] && return 0
  local d
  for d in firefox firefox-esr chromium chromium-browser epiphany-browser \
           midori falkon netsurf-gtk; do
    [ -f "/usr/share/applications/$d.desktop" ] || continue
    xdg-mime default "$d.desktop" x-scheme-handler/http x-scheme-handler/https \
      text/html 2>/dev/null
    return 0
  done
  return 0
}
# ---------------- janela do navegador (tela de login) -----------------
# O devilspie2 do Tarsila (floating.lua) maximiza e tira a decoracao de
# toda janela com WM_CLASS "Chromium". A pagina de senha de aplicativo
# caia nessa regra: abria em tela cheia, sem barra de titulo, cobrindo
# este assistente. Abrimos com --class=Tarsila-login (classe que o
# devilspie2 nao toca) e geometria propria. Se o Chromium ja estiver
# aberto, quem cria a janela e a instancia existente e os flags sao
# ignorados; por isso ajustar_janela_login encolhe a janela nova.
LOGIN_CLASS="Tarsila-login"

# Coluna da esquerda reservada ao assistente: o navegador e ancorado a
# DIREITA dela para os dois ficarem lado a lado. Antes o navegador abria
# por cima do assistente e o usuario perdia as instrucoes de vista.
COL_ASSISTENTE=520                 # 490 da largura do yad + margem

geometria_login(){                 # ecoa "LARGURA ALTURA X Y"
  local sw=1366 sh=768 l a x y g
  if command -v xdotool >/dev/null 2>&1; then
    g=$(xdotool getdisplaygeometry 2>/dev/null)
    [ -n "$g" ] && { sw=${g%% *}; sh=${g##* }; }
  fi
  l=$(( sw - COL_ASSISTENTE - 30 ))
  [ "$l" -gt 1100 ] && l=1100; [ "$l" -lt 640 ] && l=640
  a=$(( sh - 120 )); [ "$a" -gt 760 ] && a=760; [ "$a" -lt 480 ] && a=480
  x=$(( sw - l - 12 )); [ "$x" -lt 0 ] && x=0
  y=$(( (sh - a) / 2 ))
  [ "$y" -lt 40 ] && y=40          # abaixo da barra superior do Tarsila
  echo "$l $a $x $y"
}

# Roda em segundo plano: espera a janela que o navegador abriu e a
# encolhe. So mexe em janela que NAO existia antes da chamada, e nunca
# nas do proprio assistente, do Claws ou do shell (painel/dock/desktop).
ajustar_janela_login(){            # $1=ids antes  $2=L $3=A $4=X $5=Y
  local antes="$1" l="$2" a="$3" x="$4" y="$5" i id cls resto novo=""
  command -v wmctrl >/dev/null 2>&1 || return 0
  for i in $(seq 1 60); do
    sleep 1
    while read -r id _ cls resto; do
      case "$cls" in
        *Yad|*Xfdesktop|*Xfce4-panel|*Plank|*Tarsila-*|*laws-mail) continue ;;
      esac
      case " $antes " in *" $id "*) continue ;; esac
      novo="$id"
    done < <(wmctrl -lx 2>/dev/null)
    [ -n "$novo" ] || continue
    wmctrl -i -r "$novo" -b remove,maximized_vert,maximized_horz >/dev/null 2>&1
    wmctrl -i -r "$novo" -e "0,$x,$y,$l,$a" >/dev/null 2>&1
    return 0
  done
}

abrir_url(){
  local u="$1" b l a x y antes
  garantir_mime_navegador
  read -r l a x y <<< "$(geometria_login)"
  antes=$(wmctrl -lx 2>/dev/null | cut -d" " -f1 | tr "\n" " ")
  ajustar_janela_login "$antes" "$l" "$a" "$x" "$y" &

  # A partir daqui as telas do assistente param de abrir centralizadas e
  # ficam encostadas na esquerda, na coluna que o navegador nao ocupa:
  # o usuario le a instrucao e o formulario COM o login visivel ao lado.
  [ "$GUI" = yad ] && YOPT=(--posx=12 --posy=96 --on-top)

  if [ -n "${BROWSER:-}" ] && command -v "${BROWSER%% *}" >/dev/null 2>&1; then
    setsid $BROWSER "$u" >/dev/null 2>&1 & sleep 1; return 0
  fi
  # Chromium direto (padrao do Tarsila): unico que aceita classe e
  # tamanho por linha de comando de forma confiavel.
  for b in chromium chromium-browser; do
    command -v "$b" >/dev/null 2>&1 || continue
    setsid "$b" --class="$LOGIN_CLASS" --window-size="$l,$a" \
      --window-position="$x,$y" --no-first-run \
      --hide-crash-restore-bubble "$u" >/dev/null 2>&1 &
    sleep 1; return 0
  done
  # NUNCA envolver em "timeout": ele sinaliza o process group inteiro e
  # derrubava o navegador 8s depois de abrir, no meio do login.
  if command -v xdg-open >/dev/null 2>&1; then
    setsid xdg-open "$u" >/dev/null 2>&1 & sleep 1; return 0
  fi
  for b in gio exo-open x-www-browser sensible-browser firefox firefox-esr \
           epiphany-browser midori surf netsurf-gtk dillo; do
    command -v "$b" >/dev/null 2>&1 || continue
    if [ "$b" = gio ]; then setsid gio open "$u" >/dev/null 2>&1 &
    else setsid "$b" "$u" >/dev/null 2>&1 & fi
    sleep 1; return 0
  done
  clip "$u"
  "$GUI" "${YOPT[@]}" --entry --title="$APP_TITLE" \
    --text="Nenhum navegador detectado.\nEndereco copiado; abra manualmente:" \
    --entry-text="$u" >/dev/null 2>&1
  return 1
}

# ---------------- instalacao do Claws (offline se embutido) -----------
instalar_claws(){
  command -v claws-mail-instalar-offline >/dev/null 2>&1 || {
    erro "Instalador nao encontrado."; return 1; }
  if { command -v pkexec >/dev/null 2>&1 && tem_agente_polkit; } || \
     { command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; }; then
    ( escalar_root claws-mail-instalar-offline ) 2>&1 | \
      "$GUI" "${YOPT[@]}" --progress --pulsate --auto-close --no-cancel \
        --title="$APP_TITLE" --text="Instalando Claws Mail..." >/dev/null 2>&1
  else
    escalar_root claws-mail-instalar-offline
    info "Se a instalacao terminou na janela do terminal, clique em OK."
  fi
}

if ! command -v claws-mail >/dev/null 2>&1; then
  if perg "O Claws Mail ainda nao esta instalado.\n\nEle vem <b>embutido neste pacote</b> — instalacao <b>offline</b>, sem internet.\n\nInstalar agora?"; then
    instalar_claws
  fi
  command -v claws-mail >/dev/null 2>&1 || {
    erro "Nao concluido.\nTente no terminal:\n<tt>sudo claws-mail-instalar-offline</tt>"; exit 1; }
fi

# ---------------- senha no formato legado do Claws --------------------
# XOR ciclico com "passkey0" + base64; o Claws migra p/ passwordstorerc.
passcrypt(){
  local pw="$1" k="passkey0" i a b x n hex="" LC_ALL=C
  command -v xxd >/dev/null 2>&1 || return 1
  n=${#pw}; [ "$n" -eq 0 ] && return 1
  for (( i=0; i<n; i++ )); do
    printf -v a '%d' "'${pw:$i:1}"
    printf -v b '%d' "'${k:$(( i % 8 )):1}"
    x=$(( a ^ b ))
    [ "$x" -eq 0 ] && return 1        # byte nulo quebraria o accountrc
    hex+=$(printf '%02x' "$x")
  done
  printf '%s' "$hex" | xxd -r -p 2>/dev/null | base64 -w0
}

tem_contas(){ [ -s "$ACCOUNTRC" ] && grep -q '^\[Account: ' "$ACCOUNTRC"; }
prox_id(){
  local m=0 n
  while read -r n; do [ "$n" -gt "$m" ] && m=$n; done \
    < <(grep -o '^\[Account: [0-9]*' "$ACCOUNTRC" 2>/dev/null | grep -o '[0-9]*')
  echo $(( m + 1 ))
}
backup(){ [ -f "$1" ] && { mkdir -p "$BKP"; cp -f "$1" "$BKP/$(basename "$1").$(date +%Y%m%d-%H%M%S)"; }; return 0; }
limpar_legado(){ grep -q '^\[Default\]' "$ACCOUNTRC" 2>/dev/null && { backup "$ACCOUNTRC"; : > "$ACCOUNTRC"; }; return 0; }
mailbox(){
  mkdir -p "$MDIR"/inbox "$MDIR"/outbox "$MDIR"/draft "$MDIR"/queue "$MDIR"/trash
  [ -f "$FOLDERLIST" ] && return 0
  cat > "$FOLDERLIST" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<folderlist>
  <folder type="mh" name="$MBOX" path="$(basename "$MDIR")" collapsed="0" sort="0">
    <folderitem type="inbox"  name="inbox"  path="inbox"  mtime="0" new="0" unread="0" total="0" />
    <folderitem type="outbox" name="outbox" path="outbox" mtime="0" new="0" unread="0" total="0" />
    <folderitem type="draft"  name="draft"  path="draft"  mtime="0" new="0" unread="0" total="0" />
    <folderitem type="queue"  name="queue"  path="queue"  mtime="0" new="0" unread="0" total="0" />
    <folderitem type="trash"  name="trash"  path="trash"  mtime="0" new="0" unread="0" total="0" />
  </folder>
</folderlist>
EOL
}
fechar(){
  pgrep -x claws-mail >/dev/null 2>&1 || return 0
  perg "O Claws Mail esta aberto e sobrescreve a configuracao ao sair.\n\nFechar agora?" \
    && claws-mail --exit >/dev/null 2>&1
  local i
  for i in $(seq 1 20); do pgrep -x claws-mail >/dev/null 2>&1 || return 0; sleep 0.5; done
  erro "Feche o Claws Mail e rode o assistente novamente."; exit 1
}
# Versao sem perguntas do fechar(), para a interface grafica: o Claws
# sobrescreve o accountrc ao sair, entao precisa estar fechado antes de
# gravarmos a conta.
fechar_silencioso(){
  pgrep -x claws-mail >/dev/null 2>&1 || return 0
  claws-mail --exit >/dev/null 2>&1
  local i
  for i in $(seq 1 20); do
    pgrep -x claws-mail >/dev/null 2>&1 || return 0
    sleep 0.5
  done
  return 0
}
grava(){
  local rot="$1" nom="$2" mail="$3" pw="$4" im="$5" ip="$6" is="$7" sm="$8" sp="$9" ss="${10}"
  local id def=0 enc
  mkdir -p "$CLAWS_DIR"; limpar_legado; mailbox; backup "$ACCOUNTRC"
  tem_contas || def=1
  id=$(prox_id)
  enc=$(passcrypt "$pw") || enc=""
  { [ -s "$ACCOUNTRC" ] && echo ""
    cat << EOL
[Account: $id]
account_name=$rot ($mail)
is_default=$def
name=$nom
address=$mail
protocol=3
receive_server=$im
smtp_server=$sm
user_id=$mail
password=$enc
inbox=#mh/$MBOX/inbox
local_inbox=#mh/$MBOX/inbox
imap_auth_method=0
ssl_imap=$is
ssl_smtp=$ss
use_nonblocking_ssl=1
set_imapport=1
imapport=$ip
set_smtpport=1
smtpport=$sp
use_smtp_auth=1
smtp_auth_method=0
imap_subsonly=1
filter_on_receive=1
signature_type=0
sig_sep=--
EOL
  } >> "$ACCOUNTRC"
  chmod 600 "$ACCOUNTRC"
  [ -n "$enc" ]
}
form(){
  local rot="$1" dica="$2"
  if [ "$GUI" = yad ]; then
    yad "${YOPT[@]}" --form --title="$APP_TITLE" --width=490 --separator="$SEP" \
      --text="<b>Conta $rot</b>\n\nCole a <b>senha de aplicativo</b> gerada no navegador.\n<small>$dica</small>" \
      --field="Seu nome (remetente)" "" \
      --field="E-mail" "" \
      --field="Senha de aplicativo:H" "" \
      --button="Cancelar!gtk-cancel:1" --button="Salvar e abrir o Claws!gtk-ok:0" 2>/dev/null
  else
    zenity --forms --title="$APP_TITLE" --separator="$SEP" --text="Conta $rot — $dica" \
      --add-entry="Seu nome (remetente)" --add-entry="E-mail" \
      --add-password="Senha de aplicativo" 2>/dev/null
  fi
}
provedor(){
  local rot="$1" link="$2" dica="$3" im="$4" ip="$5" is="$6" sm="$7" sp="$8" ss="$9"
  local o n e s okpw=1
  if [ -n "$link" ]; then
    info "<b>Passo 1 — senha de aplicativo ($rot)</b>\n\nVou abrir o navegador. Gere/copie a senha e volte.\nDepois so pedirei <b>nome, e-mail e senha</b>."
    abrir_url "$link"
  fi
  while :; do
    o=$(form "$rot" "$dica") || return 1
    IFS="$SEP" read -r n e s _ <<< "$o"
    if ! [[ "${e:-}" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then
      erro "E-mail invalido."; continue; fi
    if [ -z "${s:-}" ]; then erro "Senha vazia."; continue; fi
    [ -z "${n:-}" ] && n="${e%@*}"
    break
  done
  fechar
  grava "$rot" "$n" "$e" "$s" "$im" "$ip" "$is" "$sm" "$sp" "$ss" || okpw=0
  clip "$s"
  if [ "$okpw" -eq 1 ]; then
    info "<b>Conta configurada!</b>\n\n<tt>$e</tt>\nIMAP $im:$ip · SMTP $sm:$sp\n\nA senha tambem foi copiada (Ctrl+V se o Claws pedir).\n\nOK para abrir o Claws Mail."
  else
    info "<b>Conta configurada</b> (<tt>$e</tt>)\n\nA senha <b>nao</b> pode ser gravada no arquivo; ela esta na area de transferencia.\nNa primeira conexao use <b>Ctrl+V</b> e marque <i>lembrar</i>."
  fi
  setsid claws-mail >/dev/null 2>&1 &
  return 0
}
manual(){
  local o si pi ssl_i ss ps ssl_s
  if [ "$GUI" = yad ]; then
    o=$(yad "${YOPT[@]}" --form --title="$APP_TITLE" --width=490 --separator="$SEP" \
      --text="<b>IMAP manual</b>" \
      --field="Servidor IMAP" "" --field="Porta IMAP:NUM" "993" \
      --field="Seguranca IMAP:CB" "SSL/TLS!STARTTLS" \
      --field="Servidor SMTP" "" --field="Porta SMTP:NUM" "587" \
      --field="Seguranca SMTP:CB" "STARTTLS!SSL/TLS" 2>/dev/null) || return 1
  else
    o=$(zenity --forms --title="$APP_TITLE" --separator="$SEP" --text="IMAP manual" \
      --add-entry="Servidor IMAP" --add-entry="Porta IMAP (993/143)" \
      --add-entry="Seguranca IMAP (SSL/TLS ou STARTTLS)" \
      --add-entry="Servidor SMTP" --add-entry="Porta SMTP (465/587)" \
      --add-entry="Seguranca SMTP (SSL/TLS ou STARTTLS)" 2>/dev/null) || return 1
  fi
  IFS="$SEP" read -r si pi ssl_i ss ps ssl_s _ <<< "$o"
  pi=${pi%%.*}; ps=${ps%%.*}
  if [ -z "${si:-}" ] || [ -z "${ss:-}" ]; then erro "Servidores obrigatorios."; return 1; fi
  case "${ssl_i^^}" in *START*) ssl_i=2 ;; *) ssl_i=1 ;; esac
  case "${ssl_s^^}" in *START*) ssl_s=2 ;; *) ssl_s=1 ;; esac
  provedor "IMAP" "" "Use a senha do seu provedor." \
    "$si" "${pi:-993}" "$ssl_i" "$ss" "${ps:-587}" "$ssl_s"
}
wizard(){
  if tem_contas; then
    if perg "Ja existe conta neste perfil.\n\n<b>Sim</b> = abrir o Claws para adicionar outra em <i>Configuracao ▸ Editar contas ▸ Nova</i>\n<b>Nao</b> = mover a config atual para backup e abrir as <b>telas iniciais</b> do Claws"; then
      info "Abrindo. Va em <b>Configuracao ▸ Editar contas… ▸ Nova</b>."
    else
      fechar; backup "$ACCOUNTRC"; mkdir -p "$BKP"
      mv -f "$ACCOUNTRC" "$BKP/accountrc.desativado.$(date +%Y%m%d-%H%M%S)" 2>/dev/null
      info "Backup em <tt>$BKP</tt>.\nO Claws abrira no <b>assistente inicial</b>."
    fi
  else
    info "O Claws abrira no <b>assistente inicial</b>."
  fi
  setsid claws-mail >/dev/null 2>&1 &
}
menu(){
  local o rc
  if [ "$GUI" = yad ]; then
    o=$(yad "${YOPT[@]}" --list --title="$APP_TITLE" --width=560 --height=300 \
      --print-column=1 --column="Servico" --column="Servidores" \
      --text="<b>Escolha o servico</b>\n\nOu use <i>Assistente do Claws</i> para outro e-mail." \
      "Gmail" "imap.gmail.com / smtp.gmail.com" \
      "Outlook/Hotmail" "outlook.office365.com / smtp.office365.com" \
      "Outro (IMAP manual)" "voce informa" \
      --button="Assistente do Claws (outro e-mail)!gtk-preferences:2" \
      --button="Cancelar!gtk-cancel:1" --button="Continuar!gtk-ok:0" 2>/dev/null); rc=$?
    [ $rc -eq 2 ] && { echo WIZARD; return; }
    [ $rc -ne 0 ] && { echo SAIR; return; }
  else
    o=$(zenity --list --title="$APP_TITLE" --width=560 --height=300 --print-column=1 \
      --text="Escolha o servico" --column="Servico" --column="Servidores" \
      "Gmail" "imap.gmail.com / smtp.gmail.com" \
      "Outlook/Hotmail" "outlook.office365.com / smtp.office365.com" \
      "Outro (IMAP manual)" "voce informa" \
      --extra-button="Assistente do Claws (outro e-mail)" 2>/dev/null); rc=$?
    [ "$o" = "Assistente do Claws (outro e-mail)" ] && { echo WIZARD; return; }
    [ $rc -ne 0 ] && { echo SAIR; return; }
  fi
  case "${o%%|*}" in
    Gmail*)   echo GMAIL ;;
    Outlook*) echo OUTLOOK ;;
    Outro*)   echo OUTRO ;;
    *)        echo SAIR ;;
  esac
}

# ---------------- motor da interface grafica --------------------------
# configurar-claws-gui nao duplica nada daqui: ele chama estes modos.
# A senha vem por CLAWS_SENHA (ambiente), nunca por argumento -- argv e
# publico no ps, o environ do processo nao e.
case "${1:-}" in
  --geometria-login) geometria_login; exit 0 ;;
  --abrir)           abrir_url "${2:-}"; exit $? ;;
  --gravar)
    shift
    fechar_silencioso
    grava "${1:-}" "${2:-}" "${3:-}" "${CLAWS_SENHA:-}" "${4:-}" "${5:-}" \
          "${6:-}" "${7:-}" "${8:-}" "${9:-}"
    rc_gravar=$?
    tem_contas || exit 1
    [ "$rc_gravar" -eq 0 ] || { clip "${CLAWS_SENHA:-}"; exit 2; }
    exit 0 ;;
esac

# A interface grafica e o caminho normal. O fluxo antigo em yad fica de
# reserva para diagnostico: CLAWS_ASSISTENTE_YAD=1 configurar-claws
if [ "${CLAWS_ASSISTENTE_YAD:-0}" != 1 ] \
   && [ -x /usr/bin/configurar-claws-gui ] \
   && python3 -c "import gi" >/dev/null 2>&1; then
  exec /usr/bin/configurar-claws-gui
fi

case "$(menu)" in
  GMAIL)
    provedor "Gmail" "https://myaccount.google.com/apppasswords" \
      "Requer verificacao em 2 etapas ativa." \
      "imap.gmail.com" 993 1 "smtp.gmail.com" 465 1 ;;
  OUTLOOK)
    info "<b>Atencao:</b> em contas pessoais Outlook/Hotmail a Microsoft desativou senha para IMAP/SMTP.\nSe falhar, use <b>OAuth2</b> (Claws 4.1+) nas preferencias da conta."
    provedor "Outlook" "https://account.microsoft.com/security" \
      "Contas corporativas podem exigir OAuth2." \
      "outlook.office365.com" 993 1 "smtp.office365.com" 587 2 ;;
  OUTRO)  manual ;;
  WIZARD) wizard ;;
  *) exit 0 ;;
esac

# oferece integrar ao menu do Openbox, se aplicavel
if pgrep -x openbox >/dev/null 2>&1 \
   && ! grep -q 'configurar-claws' "$HOME/.config/openbox/menu.xml" 2>/dev/null \
   && command -v claws-mail-openbox-integra >/dev/null 2>&1; then
  perg "Detectei o <b>Openbox</b>.\n\nAdicionar 'Claws Mail' e 'Configurar Claws Mail' ao menu do botao direito?" \
    && claws-mail-openbox-integra >/dev/null 2>&1 \
    && info "Menu do Openbox atualizado."
fi
exit 0
__FIM_ASSISTENTE__

# ======================================================================
#  A2) INTERFACE GRAFICA DO ASSISTENTE
# ======================================================================
# Esta e a tela que o usuario ve de verdade: o configurar-claws acima
# passa o controle para ca quando o python3-gi esta presente, e volta a
# ser chamado por ela em modo nao-interativo (--abrir, --gravar,
# --geometria-login). Ficou meses so na maquina, fora de qualquer fonte:
# reconstruir o pacote sem ela devolvia o assistente antigo em yad.
cat > "$PAYLOAD/configurar-claws-gui" << '__FIM_GUI__'
#!/usr/bin/env python3
"""Assistente de E-mail do Tarsila (Claws Mail) — interface.

Regra de UX: nada de jargão na tela. O usuário escolhe o serviço por
ícone (Gmail, Outlook/Hotmail, Outro), entra com e-mail e senha e
acabou — servidores, portas e criptografia são deduzidos aqui dentro.

A gravação da conta continua sendo do /usr/bin/configurar-claws, que
esta interface chama em modo não-interativo (--abrir, --gravar,
--geometria-login). A senha vai por variável de ambiente, nunca por
linha de comando (argv aparece no ps; o environ não).
"""
import os
import re
import socket
import subprocess
import threading

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

MOTOR = '/usr/bin/configurar-claws'
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# rotulo, icone, pagina de senha de aplicativo, (imap, porta, ssl, smtp, porta, ssl)
# ssl: 1 = SSL/TLS, 2 = STARTTLS
PROVEDORES = [
    ('Gmail', 'gmail',
     'https://myaccount.google.com/apppasswords',
     ('imap.gmail.com', 993, 1, 'smtp.gmail.com', 465, 1)),
    ('Outlook / Hotmail', 'ms-outlook',
     'https://account.microsoft.com/security',
     ('outlook.office365.com', 993, 1, 'smtp.office365.com', 587, 2)),
    ('Outro', 'internet-mail', '', None),
]

# O que dizer em cada serviço, em português de gente.
INSTRUCAO = {
    'Gmail': 'Abri a página do Google ao lado. Entre na sua conta e crie '
             'uma <b>senha de aplicativo</b>: copie os 16 caracteres que '
             'aparecerem e cole aqui embaixo.',
    'Outlook / Hotmail': 'Abri a página da Microsoft ao lado. Entre na sua '
                         'conta e crie uma <b>senha de aplicativo</b>: copie '
                         'o que aparecer e cole aqui embaixo.',
    'Outro': 'Digite seu endereço de e-mail e a senha que você usa para '
             'entrar nele. Eu procuro o resto sozinho.',
}


def motor(*args, senha=None):
    """Chama o /usr/bin/configurar-claws e devolve (codigo, saida)."""
    amb = dict(os.environ)
    if senha is not None:
        amb['CLAWS_SENHA'] = senha
    try:
        p = subprocess.run([MOTOR, *args], env=amb, capture_output=True,
                           text=True, timeout=90)
        return p.returncode, p.stdout.strip()
    except Exception as exc:                       # motor ausente ou travado
        return 1, str(exc)


def porta_responde(host, porta, espera=4):
    try:
        with socket.create_connection((host, porta), timeout=espera):
            return True
    except OSError:
        return False


class Assistente(Gtk.Window):
    def __init__(self):
        super().__init__(title='E-mail')
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        try:
            self.set_wmclass('configurar-claws', 'Tarsila-claws')
        except Exception:
            pass
        self.set_icon_name('internet-mail')

        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.caixa.set_border_width(18)
        self.add(self.caixa)

        self.provedor = None
        self.avancado = None          # campos de servidor, só se a busca falhar
        self.tela_escolha()

    # ------------------------------------------------------------------
    # utilidades de tela
    # ------------------------------------------------------------------
    def limpar(self):
        for filho in self.caixa.get_children():
            self.caixa.remove(filho)

    def titulo(self, texto, dica=None):
        rot = Gtk.Label()
        rot.set_markup('<big><b>%s</b></big>' % texto)
        self.caixa.pack_start(rot, False, False, 0)
        if dica:
            sub = Gtk.Label()
            sub.set_markup('<small>%s</small>' % dica)
            sub.set_line_wrap(True)
            sub.set_justify(Gtk.Justification.CENTER)
            self.caixa.pack_start(sub, False, False, 0)

    def rodape(self, esquerda, direita, acao):
        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        if esquerda:
            b = Gtk.Button(label=esquerda[0])
            b.connect('clicked', esquerda[1])
            linha.pack_start(b, False, False, 0)
            linha.pack_start(Gtk.Box(), True, True, 0)
        else:
            linha.set_halign(Gtk.Align.CENTER)   # botao unico fica centrado
        ok = Gtk.Button(label=direita)
        ok.get_style_context().add_class('suggested-action')
        ok.connect('clicked', acao)
        ok.set_can_default(True)
        linha.pack_start(ok, False, False, 0)
        self.caixa.pack_start(linha, False, False, 0)
        self.set_default(ok)

    def encostar_na_esquerda(self):
        """Coloca o assistente na coluna que o navegador deixa livre.

        O navegador de login abre ancorado à direita (geometria dada pelo
        motor); antes as duas janelas brigavam pelo centro da tela e a
        página de senha cobria as instruções.
        """
        largura = 470
        rc, saida = motor('--geometria-login')
        if rc == 0 and len(saida.split()) == 4:
            _l, _a, x, _y = (int(v) for v in saida.split())
            largura = max(380, min(500, x - 26))
        self.largura_coluna = largura
        self.set_position(Gtk.WindowPosition.NONE)
        self.resize(largura, 1)          # 1 = encolhe ate a altura do conteudo
        self.move(12, 96)

    # ------------------------------------------------------------------
    # tela 1 — escolha do serviço
    # ------------------------------------------------------------------
    def tela_escolha(self):
        self.limpar()
        self.set_default_size(520, 250)
        self.resize(520, 250)
        self.titulo('Qual é o seu e-mail?')
        grade = Gtk.Grid(column_spacing=16, row_spacing=14,
                         column_homogeneous=True)
        grade.set_halign(Gtk.Align.CENTER)
        grade.set_valign(Gtk.Align.CENTER)
        for i, prov in enumerate(PROVEDORES):
            rotulo, icone = prov[0], prov[1]
            b = Gtk.Button()
            b.set_relief(Gtk.ReliefStyle.NONE)
            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            img = Gtk.Image.new_from_icon_name(icone, Gtk.IconSize.DIALOG)
            img.set_pixel_size(64)
            corpo.pack_start(img, False, False, 0)
            corpo.pack_start(Gtk.Label(label=rotulo), False, False, 0)
            b.add(corpo)
            b.connect('clicked', self.escolher, prov)
            grade.attach(b, i, 0, 1, 1)
        self.caixa.pack_start(grade, True, True, 0)
        self.show_all()

    def escolher(self, _b, prov):
        self.provedor = prov
        url = prov[2]
        if url:
            # Navegador primeiro: ele leva alguns segundos para pintar a
            # janela, então já sai na frente enquanto montamos o formulário.
            subprocess.Popen([MOTOR, '--abrir', url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            self.encostar_na_esquerda()   # so sai do centro se houver navegador
        self.tela_login()

    # ------------------------------------------------------------------
    # tela 2 — e-mail e senha (só isso)
    # ------------------------------------------------------------------
    def tela_login(self):
        rotulo, icone = self.provedor[0], self.provedor[1]
        self.limpar()

        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cab.set_halign(Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name(icone, Gtk.IconSize.DIALOG)
        img.set_pixel_size(40)
        cab.pack_start(img, False, False, 0)
        nome = Gtk.Label()
        nome.set_markup('<big><b>%s</b></big>' % GLib.markup_escape_text(rotulo))
        cab.pack_start(nome, False, False, 0)
        self.caixa.pack_start(cab, False, False, 0)

        texto = Gtk.Label()
        texto.set_markup('<small>%s</small>' % INSTRUCAO[rotulo])
        texto.set_line_wrap(True)
        texto.set_max_width_chars(46)
        self.caixa.pack_start(texto, False, False, 0)

        grade = Gtk.Grid(column_spacing=10, row_spacing=8)
        grade.set_hexpand(True)
        alvo = Gtk.Label(label='E-mail:', xalign=1)
        self.campo_email = Gtk.Entry()
        self.campo_email.set_placeholder_text('voce@exemplo.com')
        self.campo_email.set_hexpand(True)
        self.campo_email.set_activates_default(True)
        grade.attach(alvo, 0, 0, 1, 1)
        grade.attach(self.campo_email, 1, 0, 1, 1)

        alvo2 = Gtk.Label(label='Senha:', xalign=1)
        self.campo_senha = Gtk.Entry()
        self.campo_senha.set_visibility(False)
        self.campo_senha.set_hexpand(True)
        self.campo_senha.set_activates_default(True)
        grade.attach(alvo2, 0, 1, 1, 1)
        grade.attach(self.campo_senha, 1, 1, 1, 1)
        self.caixa.pack_start(grade, False, False, 0)

        ver = Gtk.CheckButton(label='Mostrar senha')
        ver.connect('toggled',
                    lambda c: self.campo_senha.set_visibility(c.get_active()))
        ver.set_halign(Gtk.Align.END)
        self.caixa.pack_start(ver, False, False, 0)

        self.aviso = Gtk.Label()
        self.aviso.set_line_wrap(True)
        self.caixa.pack_start(self.aviso, False, False, 0)

        self.rodape(('Voltar', lambda _b: (self.set_position(
            Gtk.WindowPosition.CENTER), self.tela_escolha())),
            'Salvar', self.salvar)
        self.show_all()
        self.resize(getattr(self, 'largura_coluna', 470), 1)
        self.campo_email.grab_focus()

    def erro(self, texto):
        self.aviso.set_markup(
            '<span foreground="#c01c28"><b>%s</b></span>'
            % GLib.markup_escape_text(texto))

    # ------------------------------------------------------------------
    # gravação
    # ------------------------------------------------------------------
    def salvar(self, _b=None):
        email = self.campo_email.get_text().strip()
        senha = self.campo_senha.get_text()
        if not EMAIL_RE.match(email):
            self.erro('Confira o endereço: falta algo como voce@exemplo.com')
            self.campo_email.grab_focus()
            return
        if not senha:
            self.erro('Digite a senha.')
            self.campo_senha.grab_focus()
            return

        if self.avancado is not None:            # busca falhou antes
            entrada = self.avancado[0].get_text().strip()
            saida = self.avancado[1].get_text().strip()
            if not entrada or not saida:
                self.erro('Preencha os dois endereços.')
                return
            self.gravar(email, senha, (entrada, 993, 1, saida, 587, 2))
            return

        if self.provedor[3] is not None:
            self.gravar(email, senha, self.provedor[3])
            return

        self.procurar(email, senha)              # "Outro": descobrir sozinho

    def procurar(self, email, senha):
        self.aviso.set_markup('<small>Procurando as configurações do seu '
                              'e-mail…</small>')
        self.set_sensitive(False)
        dominio = email.split('@')[1]

        def trabalho():
            entrada = saida = None
            for host in ('imap.' + dominio, 'mail.' + dominio,
                         'imap.mail.' + dominio, dominio):
                if porta_responde(host, 993):
                    entrada = host
                    break
            for host in ('smtp.' + dominio, 'mail.' + dominio,
                         'smtp.mail.' + dominio, dominio):
                if porta_responde(host, 587) or porta_responde(host, 465):
                    saida = host
                    break
            GLib.idle_add(self.achou, email, senha, entrada, saida, dominio)

        threading.Thread(target=trabalho, daemon=True).start()

    def achou(self, email, senha, entrada, saida, dominio):
        self.set_sensitive(True)
        if entrada and saida:
            porta_s, ssl_s = (587, 2) if porta_responde(saida, 587) else (465, 1)
            self.gravar(email, senha, (entrada, 993, 1, saida, porta_s, ssl_s))
            return False
        self.pedir_servidores(dominio)
        return False

    def pedir_servidores(self, dominio):
        """Último recurso: pedir os dois endereços, sem falar em protocolo."""
        self.aviso.set_markup(
            '<small>Não encontrei sozinho. Seu provedor informa estes dois '
            'endereços (procure por "configurar e-mail no celular"):</small>')
        grade = Gtk.Grid(column_spacing=10, row_spacing=8)
        e1 = Gtk.Entry()
        e1.set_text('imap.' + dominio)
        e1.set_hexpand(True)
        e2 = Gtk.Entry()
        e2.set_text('smtp.' + dominio)
        e2.set_hexpand(True)
        grade.attach(Gtk.Label(label='Recebe em:', xalign=1), 0, 0, 1, 1)
        grade.attach(e1, 1, 0, 1, 1)
        grade.attach(Gtk.Label(label='Envia por:', xalign=1), 0, 1, 1, 1)
        grade.attach(e2, 1, 1, 1, 1)
        self.caixa.pack_start(grade, False, False, 0)
        self.caixa.reorder_child(grade, len(self.caixa.get_children()) - 2)
        self.avancado = (e1, e2)
        self.show_all()

    def gravar(self, email, senha, servidores):
        entrada, porta_e, ssl_e, saida, porta_s, ssl_s = servidores
        nome = email.split('@')[0]
        rc, _ = motor('--gravar', self.provedor[0], nome, email,
                      entrada, str(porta_e), str(ssl_e),
                      saida, str(porta_s), str(ssl_s), senha=senha)
        if rc not in (0, 2):
            self.erro('Não consegui salvar a conta. Tente de novo.')
            return
        self.fechar_login_navegador()
        self.tela_pronto(email, rc == 2)

    def fechar_login_navegador(self):
        """Fecha a janela de login — e só ela.

        Fecha por WM_CLASS Tarsila-login, a classe que o motor dá à
        janela que ele mesmo abriu; se o Chromium já estava aberto os
        flags foram ignorados e a janela do usuário fica intocada.
        """
        try:
            saida = subprocess.run(['wmctrl', '-lx'], capture_output=True,
                                   text=True, timeout=5).stdout
        except Exception:
            return
        for linha in saida.splitlines():
            campos = linha.split(None, 3)
            if len(campos) > 2 and campos[2].endswith('Tarsila-login'):
                subprocess.run(['wmctrl', '-i', '-c', campos[0]], timeout=5)

    # ------------------------------------------------------------------
    # tela 3 — pronto
    # ------------------------------------------------------------------
    def tela_pronto(self, email, senha_fora):
        self.limpar()
        self.avancado = None
        img = Gtk.Image.new_from_icon_name('emblem-ok', Gtk.IconSize.DIALOG)
        img.set_pixel_size(56)
        self.caixa.pack_start(img, False, False, 0)
        self.titulo('Tudo pronto!', GLib.markup_escape_text(email))
        if senha_fora:
            extra = Gtk.Label()
            extra.set_markup('<small>Se o E-mail pedir a senha de novo, ela '
                             'está copiada: use Ctrl+V.</small>')
            extra.set_line_wrap(True)
            self.caixa.pack_start(extra, False, False, 0)
        self.rodape(None, 'Abrir o E-mail', self.abrir_claws)
        self.show_all()
        self.resize(getattr(self, 'largura_coluna', 470), 1)

    def abrir_claws(self, _b):
        subprocess.Popen(['claws-mail'], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        Gtk.main_quit()


if __name__ == '__main__':
    janela = Assistente()
    janela.connect('destroy', Gtk.main_quit)
    Gtk.main()
__FIM_GUI__

# ======================================================================
#  B) INTEGRACAO OPENBOX (menu.xml + autostart) — roda como USUARIO
# ======================================================================
cat > "$PAYLOAD/claws-mail-openbox-integra" << '__FIM_OB__'
#!/bin/bash
# Integra ao Openbox: itens no menu.xml e servicos no autostart.
set -uo pipefail
[ "$(id -u)" -eq 0 ] && { echo "Rode como usuario normal, nao root."; exit 1; }

CFG="$HOME/.config/openbox"; MENU="$CFG/menu.xml"; AUTO="$CFG/autostart"
mkdir -p "$CFG"

if [ ! -f "$MENU" ]; then
  if [ -f /etc/xdg/openbox/menu.xml ]; then cp -f /etc/xdg/openbox/menu.xml "$MENU"
  else
    cat > "$MENU" << 'XML'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_menu xmlns="http://openbox.org/3.4/menu">
<menu id="root-menu" label="Openbox 3">
  <item label="Terminal">
    <action name="Execute"><execute>x-terminal-emulator</execute></action>
  </item>
  <separator />
  <item label="Reconfigurar"><action name="Reconfigure" /></item>
  <item label="Sair"><action name="Exit" /></item>
</menu>
</openbox_menu>
XML
  fi
fi

ITENS='  <separator label="E-mail" />
  <item label="Claws Mail">
    <action name="Execute"><execute>claws-mail</execute></action>
  </item>
  <item label="Configurar Claws Mail">
    <action name="Execute"><execute>configurar-claws</execute></action>
  </item>
'

if grep -q 'configurar-claws' "$MENU"; then
  echo "menu.xml: item ja presente."
else
  cp -f "$MENU" "$MENU.bak.$(date +%Y%m%d-%H%M%S)"
  TMP=$(mktemp)
  if awk -v ins="$ITENS" '
        BEGIN{root=0; done=0}
        /id="root-menu"/{root=1}
        (root==1 && done==0 && /<\/menu>/){printf "%s", ins; done=1}
        {print}
        END{if(done==0) exit 3}' "$MENU" > "$TMP" 2>/dev/null; then
    mv -f "$TMP" "$MENU"; echo "menu.xml: itens adicionados (backup criado)."
  else
    rm -f "$TMP"
    printf '%s' "$ITENS" > "$CFG/claws-menu.frag"
    echo "AVISO: nao achei <menu id=\"root-menu\">."
    echo "Cole manualmente o conteudo de $CFG/claws-menu.frag dentro do root-menu."
  fi
fi

touch "$AUTO"
add(){ grep -qF -- "$1" "$AUTO" || printf '%s\n' "$1" >> "$AUTO"; }
add '# --- claws-mail-suite (nao editar esta secao) ---'
add 'for a in /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 /usr/bin/lxpolkit /usr/lib/mate-polkit/polkit-mate-authentication-agent-1 /usr/lib/*/libexec/polkit-kde-authentication-agent-1; do [ -x "$a" ] && { "$a" & break; }; done'
add 'command -v clipit >/dev/null 2>&1 && clipit &'
add 'command -v parcellite >/dev/null 2>&1 && ! command -v clipit >/dev/null 2>&1 && parcellite &'
add 'command -v tint2 >/dev/null 2>&1 && tint2 &'
add 'grep -q "^\[Account: " "$HOME/.claws-mail/accountrc" 2>/dev/null || (sleep 4; configurar-claws) &'
chmod 644 "$AUTO"
echo "autostart atualizado: $AUTO"

command -v openbox >/dev/null 2>&1 && openbox --reconfigure 2>/dev/null || true
echo
echo "Pronto. Botao direito na area de trabalho -> Configurar Claws Mail"
echo "Faltando algo? Sugestoes: sudo apt install lxpolkit clipit tint2"
exit 0
__FIM_OB__

# ======================================================================
#  C) LOOP DE BUILD
# ======================================================================
for ARCH in "${ARCHES[@]}"; do
  echo "======================================================================"
  echo ">> Alvo: $D_ID:$SUITE  arch=$ARCH  modo=$MODE"
  W=$(mktemp -d)
  ROOT="$W/pkg"; SHARE="$ROOT/usr/share/$PKG_NAME"; REPO="$SHARE/repo"
  mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
           "$SHARE/licencas" "$ROOT/usr/share/doc/$PKG_NAME" \
           "$ROOT/usr/share/doc/$PKG_NAME/exemplos"
  SZ="0"; EMBUTIDOS=0

  if [ "$MODE" != none ]; then
    mkdir -p "$REPO"
    A="$W/apt"
    mkdir -p "$A/etc/apt/apt.conf.d" "$A/etc/apt/preferences.d" \
             "$A/etc/apt/sources.list.d" "$A/var/lib/apt/lists/partial" \
             "$A/var/cache/apt/archives/partial" "$A/var/lib/dpkg"
    : > "$A/var/lib/dpkg/status"
    cat > "$A/apt.conf" << EOL
Dir "$A";
Dir::State "$A/var/lib/apt";
Dir::State::status "$A/var/lib/dpkg/status";
Dir::Cache "$A/var/cache/apt";
Dir::Etc "$A/etc/apt";
Dir::Etc::sourcelist "$A/etc/apt/sources.list";
Dir::Etc::sourceparts "$A/etc/apt/sources.list.d";
Dir::Etc::Trusted "/etc/apt/trusted.gpg";
Dir::Etc::TrustedParts "/etc/apt/trusted.gpg.d";
APT::Architecture "$ARCH";
APT::Architectures "$ARCH";
Acquire::Languages "none";
EOL
    escrever_sources "$A/etc/apt/sources.list" "$ARCH"
    APT=(apt-get -c="$A/apt.conf" -qq)
    ACACHE=(apt-cache -c="$A/apt.conf")

    echo ">> Baixando indices..."
    "${APT[@]}" update >/dev/null

    echo ">> Resolvendo dependencias..."
    mapfile -t URIS < <("${APT[@]}" install -y --no-install-recommends --print-uris \
                          "${TARGET_PKGS[@]}" 2>/dev/null \
                        | awk -F"'" '/http|file:/{print $2}')
    if [ ${#URIS[@]} -eq 0 ]; then
      mapfile -t NOMES < <("${ACACHE[@]}" depends --recurse --no-recommends \
         --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances \
         "${TARGET_PKGS[@]}" | grep -E '^[a-zA-Z0-9]' | sed 's/:.*$//' | sort -u)
    else
      mapfile -t NOMES < <(printf '%s\n' "${URIS[@]}" | xargs -r -n1 basename \
                           | sed 's/_.*//; s/%3a.*//' | sort -u)
    fi
    if [ "$MODE" != full ]; then
      FILTRADOS=()
      for p in "${NOMES[@]}"; do
        case "$("${ACACHE[@]}" show -q "$p" 2>/dev/null | awk -F': ' '/^Priority:/{print $2; exit}')" in
          required|important) continue ;;
        esac
        FILTRADOS+=("$p")
      done
      NOMES=("${FILTRADOS[@]}")
    fi
    echo ">> ${#NOMES[@]} pacote(s) a embutir."

    : > "$SHARE/SOURCES.txt"; FALHAS=()
    pushd "$REPO" >/dev/null
    for p in "${NOMES[@]}"; do
      if "${APT[@]}" download "$p" >/dev/null 2>&1; then
        echo "  ok  $p"
        "${APT[@]}" download --print-uris "$p" 2>/dev/null \
          | awk -F"'" '{print $2}' >> "$SHARE/SOURCES.txt"
      else
        u=$(printf '%s\n' "${URIS[@]:-}" | grep -m1 "/${p}_" || true)
        if [ -n "$u" ] && command -v wget >/dev/null 2>&1 && wget -q "$u"; then
          echo "  ok* $p"; echo "$u" >> "$SHARE/SOURCES.txt"
        else FALHAS+=("$p"); fi
      fi
    done
    popd >/dev/null
    [ -n "$(ls -A "$REPO" 2>/dev/null)" ] || { echo "ERRO: nada baixado."; rm -rf "$W"; continue; }
    [ ${#FALHAS[@]} -gt 0 ] && echo ">> AVISO ignorados: ${FALHAS[*]}"

    for f in "$REPO"/*.deb; do
      n=$(dpkg-deb -f "$f" Package)
      dpkg-deb --fsys-tarfile "$f" 2>/dev/null \
        | tar -xO "./usr/share/doc/$n/copyright" > "$SHARE/licencas/$n.copyright" 2>/dev/null \
        || rm -f "$SHARE/licencas/$n.copyright"
    done

    pushd "$REPO" >/dev/null
    dpkg-scanpackages --multiversion . /dev/null 2>/dev/null > Packages
    gzip -9kf Packages
    if command -v apt-ftparchive >/dev/null 2>&1; then
      apt-ftparchive -o APT::FTPArchive::Release::Suite=local \
        -o APT::FTPArchive::Release::Codename="$D_ID-$SUITE" release . > Release 2>/dev/null || true
    fi
    popd >/dev/null
    SZ=$(du -sh "$REPO" | cut -f1); EMBUTIDOS=1
    echo ">> Payload embutido: $SZ"
  fi

  # ----------------------------------------------------------- control
  DEP_BASE="bash (>= 4.0), coreutils, xxd | vim-common, xdg-utils, zenity | yad, sudo | policykit-1 | polkitd"
  [ "$EMBUTIDOS" -eq 0 ] && DEP_BASE="$DEP_BASE, claws-mail"
  cat > "$ROOT/DEBIAN/control" << EOF
Package: $PKG_NAME
Version: $PKG_VERSION~$D_ID-$SUITE
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: $PKG_MAINTAINER
Depends: $DEP_BASE
Recommends: yad, xclip, dbus-x11, adwaita-icon-theme,
 lxpolkit | policykit-1-gnome | mate-polkit | polkit-kde-agent-1
Suggests: openbox, tint2, clipit | parcellite | xfce4-clipman,
 xterm | lxterminal | xfce4-terminal, firefox-esr | chromium, menumaker
Description: Claws Mail + assistente Gmail/Outlook (pronto para Openbox)
 Assistente grafico que pede apenas nome, e-mail e senha de aplicativo,
 gravando um accountrc valido do Claws Mail. Traz botao para abrir as
 telas iniciais do proprio Claws (outro provedor) e integracao com o
 Openbox (menu.xml e autostart) via claws-mail-openbox-integra.
 .
 Sem depender de servicos de desktop: escalonamento de privilegio com
 fallback (pkexec/sudo/terminal) e abertura de navegador com deteccao
 propria, pois o Openbox nao define MIME handlers nem agente polkit.
 .
 Alvo: $D_ID $SUITE / $ARCH — modo $MODE (payload $SZ)
EOF

  cat > "$ROOT/DEBIAN/postinst" << EOF
#!/bin/bash
set -e
if [ "\$1" = "configure" ]; then
  if [ -d /usr/share/$PKG_NAME/repo ]; then
    cat > /etc/apt/sources.list.d/$PKG_NAME.list << 'LST'
deb [arch=$ARCH trusted=yes] file:/usr/share/$PKG_NAME/repo ./
LST
  fi
  command -v update-desktop-database >/dev/null 2>&1 && \\
    update-desktop-database -q /usr/share/applications || true
  echo "--------------------------------------------------------------"
  echo " $PKG_NAME instalado (Openbox-ready)."
  [ -d /usr/share/$PKG_NAME/repo ] && \\
    echo " 1) Claws Mail offline:  sudo claws-mail-instalar-offline"
  echo " 2) Integrar ao Openbox (como USUARIO): claws-mail-openbox-integra"
  echo " 3) Configurar e-mail:    configurar-claws"
  echo "--------------------------------------------------------------"
fi
exit 0
EOF
  cat > "$ROOT/DEBIAN/postrm" << EOF
#!/bin/bash
set -e
case "\$1" in
  remove|purge)
    rm -f /etc/apt/sources.list.d/$PKG_NAME.list
    command -v update-desktop-database >/dev/null 2>&1 && \\
      update-desktop-database -q /usr/share/applications || true ;;
esac
exit 0
EOF
  chmod 755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/postrm"

  # ------------------------------------------------ instalador offline
  cat > "$ROOT/usr/bin/claws-mail-instalar-offline" << EOF
#!/bin/bash
set -u
REPO="/usr/share/$PKG_NAME/repo"
LIST="/etc/apt/sources.list.d/$PKG_NAME.list"
PKGS="${TARGET_PKGS[*]}"
ESPERADA="$ARCH"
ATUAL="\$(dpkg --print-architecture)"
[ "\$ATUAL" != "\$ESPERADA" ] && { echo "ERRO: pacote e para \$ESPERADA; sistema e \$ATUAL." >&2; exit 1; }

if [ "\$(id -u)" -ne 0 ]; then
  if command -v pkexec >/dev/null 2>&1 && \\
     pgrep -f 'polkit-.*authentication-agent|lxpolkit' >/dev/null 2>&1; then
    exec pkexec "\$0" "\$@"
  fi
  command -v sudo >/dev/null 2>&1 && exec sudo "\$0" "\$@"
  echo "Execute como root: sudo \$0"; exit 1
fi

export DEBIAN_FRONTEND=noninteractive
for _ in \$(seq 1 60); do
  command -v fuser >/dev/null 2>&1 || break
  fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break
  sleep 2
done

if [ ! -d "\$REPO" ]; then
  echo "Sem payload embutido; instalando pela rede..."
  apt-get update && apt-get install -y \$PKGS && exit 0 || exit 1
fi

if [ -f "\$LIST" ]; then
  apt-get -o Dir::Etc::sourcelist="\$LIST" -o Dir::Etc::sourceparts="-" \\
          -o APT::Get::List-Cleanup=0 update >/dev/null 2>&1
  apt-get install -y --no-install-recommends -o Acquire::Retries=0 \$PKGS && \\
    { echo "Claws Mail instalado (repositorio local)."; exit 0; }
fi

echo "Instalando via dpkg..."
dpkg -i "\$REPO"/*.deb || apt-get -f install -y || true
command -v claws-mail >/dev/null 2>&1 && { echo "Claws Mail instalado."; exit 0; }
echo "Falha na instalacao." >&2; exit 1
EOF
  chmod 755 "$ROOT/usr/bin/claws-mail-instalar-offline"

  install -m 755 "$PAYLOAD/configurar-claws"            "$ROOT/usr/bin/configurar-claws"
  install -m 755 "$PAYLOAD/configurar-claws-gui"        "$ROOT/usr/bin/configurar-claws-gui"
  install -m 755 "$PAYLOAD/claws-mail-openbox-integra"  "$ROOT/usr/bin/claws-mail-openbox-integra"

  cat > "$ROOT/usr/share/applications/configurar-claws.desktop" << 'EOF'
[Desktop Entry]
Name=Configurar Claws Mail
Comment=Instala e configura Gmail/Outlook: so nome, e-mail e senha
Exec=/usr/bin/configurar-claws
Icon=claws-mail
Type=Application
Categories=Network;Email;
Terminal=false
Keywords=email;gmail;outlook;imap;claws;openbox;
EOF

  cat > "$ROOT/usr/share/doc/$PKG_NAME/exemplos/openbox-menu.frag" << 'EOF'
<!-- Cole dentro de <menu id="root-menu"> do seu ~/.config/openbox/menu.xml -->
  <separator label="E-mail" />
  <item label="Claws Mail">
    <action name="Execute"><execute>claws-mail</execute></action>
  </item>
  <item label="Configurar Claws Mail">
    <action name="Execute"><execute>configurar-claws</execute></action>
  </item>
EOF
  cat > "$ROOT/usr/share/doc/$PKG_NAME/exemplos/openbox-autostart.frag" << 'EOF'
# Cole em ~/.config/openbox/autostart
for a in /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 \
         /usr/bin/lxpolkit \
         /usr/lib/mate-polkit/polkit-mate-authentication-agent-1; do
  [ -x "$a" ] && { "$a" & break; }
done
command -v clipit >/dev/null 2>&1 && clipit &
command -v tint2  >/dev/null 2>&1 && tint2 &
grep -q "^\[Account: " "$HOME/.claws-mail/accountrc" 2>/dev/null || (sleep 4; configurar-claws) &
EOF

  cat > "$ROOT/usr/share/doc/$PKG_NAME/README" << EOF
$PKG_NAME $PKG_VERSION — Claws Mail + assistente (Openbox-ready)
Alvo: $D_ID $SUITE / $ARCH — modo $MODE — payload $SZ

COMANDOS
  sudo claws-mail-instalar-offline   instala o Claws do repo embutido
  claws-mail-openbox-integra         menu.xml + autostart (USUARIO)
  configurar-claws                   assistente grafico

OPENBOX
  - menu.xml e estatico: use claws-mail-openbox-integra (faz backup) ou
    'mmaker -f OpenBox3' (pacote menumaker) para menu dinamico.
  - /etc/xdg/autostart NAO e lido: use ~/.config/openbox/autostart.
  - pkexec exige agente polkit; se ausente, o assistente cai para sudo ou
    terminal automaticamente. Recomendado: apt install lxpolkit
  - Sem gerenciador de clipboard a senha copiada no navegador se perde ao
    fechar a janela: apt install clipit
  - Sem bandeja o Claws "desaparece" ao minimizar: apt install tint2 ou
    desative o icone de notificacao nas preferencias do Claws.
  - Sessao: prefira 'openbox-session' (roda o autostart); se algo GTK
    reclamar de D-Bus: exec dbus-run-session -- openbox-session

NOTAS
  - A instalacao do Claws nao ocorre no postinst (dpkg com lock); e feita
    no 1o uso do assistente ou pelo comando acima.
  - Licencas dos binarios embutidos: /usr/share/$PKG_NAME/licencas
    Origem (GPL): /usr/share/$PKG_NAME/SOURCES.txt
  - Remover este pacote nao remove o claws-mail (sudo apt remove claws-mail).
EOF
  gzip -9nf "$ROOT/usr/share/doc/$PKG_NAME/README"

  find "$ROOT" -type d -exec chmod 755 {} +
  OUT="./${PKG_NAME}_${PKG_VERSION}~${D_ID}-${SUITE}_${ARCH}.deb"
  dpkg-deb -Zxz --build --root-owner-group "$ROOT" >/dev/null 2>&1 \
    || dpkg-deb -Zxz --build "$ROOT" >/dev/null
  mv "$W/pkg.deb" "$OUT"
  echo ">> Gerado: $(readlink -f "$OUT")  ($(du -h "$OUT" | cut -f1))"
  rm -rf "$W"
done

echo "======================================================================"
echo "No alvo (Openbox):"
echo "  sudo apt install ./${PKG_NAME}_*.deb"
echo "  sudo claws-mail-instalar-offline     # se houver payload embutido"
echo "  claws-mail-openbox-integra          # como usuario normal"
echo "  configurar-claws"

