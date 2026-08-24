#!/bin/bash
#
# Tarsila — instalador da camada gráfica (BETA)
#
# Instala a interface Tarsila (Openbox + Dock/Barra em GTK + Loja) sobre um
# Debian 13 (trixie) já instalado. Pensado para ARM64 (tvbox/SBC), mas os
# scripts são independentes de arquitetura.
#
# Uso:  sudo ./install.sh                      (sistema; usuário criado no 1º boot)
#       sudo ./install.sh <usuario>            (cria/provisiona o usuário agora)
#       sudo ./install.sh [<usuario>] --with-plymouth
#
# Sem <usuario>, o instalador deixa o sistema pronto e marca o primeiro
# boot: na reinicialização sobe o assistente Tarsila OOBE, que cuida da
# senha de administrador e da criação da conta de usuário.
#
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode como root: sudo ./install.sh [<usuario>] [--with-plymouth]"; exit 1; }
WITH_PLYMOUTH=0
TARSILA_USER=""
for arg in "${@}"; do
  case "$arg" in
    --with-plymouth) WITH_PLYMOUTH=1 ;;
    -*) echo "Opção desconhecida: $arg"; exit 1 ;;
    *) TARSILA_USER="$arg" ;;
  esac
done
if [ -n "$TARSILA_USER" ]; then
  id "$TARSILA_USER" >/dev/null 2>&1 || { echo "Usuário '$TARSILA_USER' não existe (crie com adduser ou deixe em branco para usar o 1º boot)"; exit 1; }
fi
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -n "$TARSILA_USER" ]; then
  HOME_DIR="$(getent passwd "$TARSILA_USER" | cut -d: -f6)"
fi

echo "==> [1/6] Instalando dependências (apt, sem recommends)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update
# Núcleo gráfico mínimo + ferramentas da interface
apt-get install -y --no-install-recommends \
  xorg openbox dunst xsettingsd picom feh scrot \
  devilspie2 yad lightdm lightdm-gtk-greeter \
  papirus-icon-theme thunar gvfs gvfs-daemons \
  python3-gi gir1.2-gtk-3.0 python3-gi-cairo \
  network-manager wmctrl xdotool x11-xserver-utils x11-utils dconf-cli \
  lxpolkit sudo curl git \
  pavucontrol inotify-tools xclip qlipper \
  file shared-mime-info desktop-file-utils \
  fonts-font-awesome fonts-noto-core \
  fonts-roboto fonts-open-sans fonts-lato fonts-montserrat fonts-inter

# O pacote 'file' acima nao e opcional, por mais banal que pareca. O
# /usr/bin/xdg-mime chama /usr/bin/file diretamente para descobrir o tipo de um
# arquivo; sem ele a deteccao volta VAZIA, o xdg-open desiste do mimeapps e cai
# no ramo do navegador. Efeito medido na box em 17/08/2026: TODO xdg-open
# abria no Chromium -- .txt, .png, qualquer coisa -- enquanto o GIO (Thunar)
# acertava. Duas rotas diferentes para a mesma acao, so uma quebrada, e nenhuma
# mensagem de erro em lugar nenhum. A imagem foi montada minima e 'file', que e
# Priority: standard no Debian, ficou de fora.

# Apps de produtividade (leves, sem recommends explícito para manter enxuto)
#
# ATENCAO ao mexer aqui: todo programa citado em skel/.config/mimeapps.list TEM
# de estar nesta lista. Se faltar, nao aparece erro nenhum -- o XDG cai no
# proximo candidato que declare o tipo, e o usuario abre PNG no ImageMagick sem
# entender por que. Foi o que aconteceu de 21/07 a 17/08/2026 com quatro tipos
# de arquivo ao mesmo tempo. Confira com:
#   grep -hoE '=[a-z0-9.-]+\.desktop' skel/.config/mimeapps.list | sort -u
#
# gpicview  visualizador de imagem (LXDE, GTK3, ~140 KB, zero dependencia nova)
# l3afpad   editor de texto simples (GTK3, ~140 KB). O mousepad custaria 2 MB e
#           arrastaria bibliotecas do XFCE que nao usamos mais
# webp-pixbuf-loader  sem ele NENHUM app GTK abre .webp, que e o que a web
#           entrega hoje. 84 KB
# p7zip-full/unar  backends do xarchiver: sem eles ele abre a janela e falha
#           em 7z e rar
apt-get install -y --no-install-recommends \
  abiword gnumeric qpdfview galculator vlc \
  mpv gpicview l3afpad webp-pixbuf-loader \
  xarchiver p7zip-full unar 2>&1 | tail -3 || echo "  aviso: apps opcionais com erro (segue)"

echo "==> [2/6] Instalando apps Tarsila…"
GH_USER="${GITHUB_USER:-pianissimobr}"
LOCAL_DEBS=$(ls "$REPO_DIR"/pacotes/*.deb 2>/dev/null || true)

if [ -n "$LOCAL_DEBS" ]; then
  echo "    Modo offline — .deb locais encontrados"
  apt-get install -y "$REPO_DIR"/pacotes/*.deb
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "    Modo git — clonando e buildando…"
  GH_BASE="https://oauth2:${GITHUB_TOKEN}@github.com/$GH_USER"
  for repo in tarsila-chromium tarsila-email tarsila-agenda tarsila-app-management tarsila-store; do
    tmp="/tmp/tarsila-$repo"
    echo "    $repo..."
    rm -rf "$tmp"
    if git clone --depth 1 "$GH_BASE/$repo.git" "$tmp" 2>/dev/null; then
      # O "find" em vez de "./*_all.deb" não é preciosismo: o build da Store
      # larga o pacote em dist/, e o glob procurava só na raiz do repositório.
      # Sem casar nada, o bash entregava a string literal "./*_all.deb" para o
      # apt-get, que errava -- ou seja, a Loja nunca chegou a ser instalada.
      #
      # E é preciso instalar TODOS os .deb do repositório de uma vez: o
      # tarsila-app-management gera dois (tarsila-motor e a interface, que
      # depende dele), e o apt só resolve a dependência entre arquivos locais
      # se os dois forem passados na mesma chamada.
      if ( cd "$tmp" && ./build-deb.sh ); then
        mapfile -t debs < <(find "$tmp" -name '*_all.deb' -type f | sort)
        if [ "${#debs[@]}" -gt 0 ]; then
          apt-get install -y "${debs[@]}" \
            || echo "      ERRO: apt recusou os pacotes de $repo"
        else
          echo "      ERRO: $repo não gerou nenhum .deb"
        fi
      else
        echo "      ERRO: build-deb.sh de $repo falhou"
      fi
    else
      echo "      ERRO: clone falhou — verifique o token ou a internet"
    fi
  done
else
  echo "    AVISO: sem .deb locais e sem GITHUB_TOKEN"
  echo "    Gere o release com ./build-release.sh ou defina GITHUB_TOKEN"
fi

[ "$WITH_PLYMOUTH" = 1 ] && apt-get install -y plymouth plymouth-themes

echo "==> [3/6] Copiando arquivos do sistema (overlay + openbox deploy)…"
# sudoers vai por caminho separado (precisa de validação); o resto copia direto
tar -cf - -C "$REPO_DIR/overlay" --exclude=./etc/sudoers.d . | tar -xpf - -C /
chmod 755 /usr/local/bin/tarsila-* /usr/local/sbin/tarsila-oobe-init /usr/local/sbin/tarsila-user-provision 2>/dev/null || true

# openbox deploy: binários da sessão, xsessions, fonts, themes
if [ -d "$REPO_DIR/openbox/deploy/usr" ]; then
  cp -a "$REPO_DIR/openbox/deploy/usr/." /usr/
  chmod +x /usr/local/bin/tarsila-ob-* 2>/dev/null || true
fi
if [ -d "$REPO_DIR/openbox/deploy/etc" ]; then
  cp -a "$REPO_DIR/openbox/deploy/etc/." /etc/
fi

# Adota no catálogo curado os apps de repositórios separados. Os .deb do
# email e da agenda instalam só o .desktop genérico em /usr/share/applications/;
# o tarsila-atalho-criar cria o curado em /usr/share/tarsila/applications/
# (com ações de dock e desinstalação), para aparecerem no dock/appfinder.
if [ -x /usr/local/bin/tarsila-atalho-criar ]; then
  tarsila-atalho-criar agenda-tarsila 2>/dev/null || true
  tarsila-atalho-criar tarsila-email 2>/dev/null || true
fi

echo "==> [4/6] Modelo de usuário (skel + openbox) e sudoers…"
# O assistente de primeiro boot cria o usuário a partir destes modelos;
# ficam no sistema para que o OOBE não dependa do repositório.
# rm antes do cp, aqui tambem: numa reinstalacao por cima, o `cp -a` deixaria
# conviver o modelo novo e o antigo (ver a nota do /etc/skel, logo abaixo).
rm -rf /usr/share/tarsila/skel /usr/share/tarsila/openbox-home
mkdir -p /usr/share/tarsila/skel
cp -a "$REPO_DIR/skel/." /usr/share/tarsila/skel/
if [ -d "$REPO_DIR/openbox/deploy/home" ]; then
  mkdir -p /usr/share/tarsila/openbox-home
  cp -a "$REPO_DIR/openbox/deploy/home/." /usr/share/tarsila/openbox-home/
fi

# /etc/skel TAMBEM, e não é redundância.
#
# O provisionamento do Tarsila (tarsila-user-provision, chamado pelo assistente
# de primeiro boot) lê os dois modelos acima. Mas `adduser` — o comando que
# qualquer um usa para criar uma segunda conta — não conhece nenhum deles:
# copia /etc/skel, e só.
#
# Medido na box em 17/08/2026: /etc/skel ainda tinha .config/polybar (9
# scripts), .config/xfce4, e um openbox/autostart que subia plank, polybar,
# tarsila-tela-estados e um tarsila-ob-decor.sh já apagado do disco. Nenhuma
# linha subia a Dock nem a barra. Um usuário criado à mão caía na sessão de
# duas versões atrás — hoje, numa que nem existe mais.
# APAGA ANTES DE COPIAR. `cp -a` MISTURA: copiar o modelo por cima do que ja
# estava deixaria os dois. Testado na box em 17/08/2026 -- o usuario novo
# recebia 30 icones na Dock, os 15 atuais mais os 15 da versao anterior com
# numeracao diferente, incluindo os seis indicadores que sairam de la hoje.
rm -rf /etc/skel/.config /etc/skel/.local
mkdir -p /etc/skel/.config
cp -a "$REPO_DIR/skel/." /etc/skel/
if [ -d "$REPO_DIR/openbox/deploy/home" ]; then
  for d in openbox dunst xsettingsd mpv; do
    [ -d "$REPO_DIR/openbox/deploy/home/$d" ] || continue
    rm -rf "/etc/skel/.config/$d"
    cp -a "$REPO_DIR/openbox/deploy/home/$d" "/etc/skel/.config/$d"
  done
  [ -f "$REPO_DIR/openbox/deploy/home/dot-xsession" ] &&
    cp -f "$REPO_DIR/openbox/deploy/home/dot-xsession" /etc/skel/.xsession
fi

# Modelo de sudoers por usuário (as regras usam o usuário de referência
# "tarsila"; o provisionador troca pelo nome real). Concatena os tarsila-*.
mkdir -p /usr/local/lib/tarsila
cat "$REPO_DIR"/overlay/etc/sudoers.d/tarsila-* > /usr/local/lib/tarsila/sudoers-template

if [ -n "$TARSILA_USER" ]; then
  echo "==> [4/6] Configurando sudoers (usuário: $TARSILA_USER)…"
  sed "s/^tarsila /$TARSILA_USER /" "$REPO_DIR/overlay/etc/sudoers.d/tarsila-config" > /etc/sudoers.d/tarsila-config
  chmod 440 /etc/sudoers.d/tarsila-config
  visudo -c >/dev/null || { echo "ERRO: sudoers inválido"; exit 1; }
  usermod -aG sudo "$TARSILA_USER"

  echo "==> [4/6] Configurações do usuário $TARSILA_USER…"
  tar -cf - -C "$REPO_DIR/skel" .config user-dirs.dirs user-dirs.locale 2>/dev/null | tar -xpf - -C "$HOME_DIR" || \
    cp -a "$REPO_DIR/skel/.config" "$HOME_DIR/"
  sudo -u "$TARSILA_USER" dbus-run-session -- dconf load /net/launchpad/plank/ < "$REPO_DIR/skel/plank-dconf.ini" || \
    echo "    AVISO: dconf load falhou — a ordem da dock será aplicada no primeiro login"
  chown -R "$TARSILA_USER:$TARSILA_USER" "$HOME_DIR"
else
  echo "==> [4/6] Sem usuário: primeiro boot vai criar a conta (OOBE)…"
fi

echo "==> [5/6] MIME, ícones e serviços…"
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -q /usr/share/icons/Tarsila-icons 2>/dev/null || true
systemctl enable lightdm NetworkManager >/dev/null 2>&1 || true

# Serviços que o Debian liga sozinho e que esta TV box não usa. Medido em
# 24/08/2026 numa sessão de 474 MB, na campanha para caber em ~300 MB:
#
#   unattended-upgrades  17,4 MB  fica de pé só para SEGURAR o desligamento
#                                 enquanto um upgrade roda. Quem atualiza o
#                                 Tarsila é o tarsila-atualizar.timer.
#   cups-browsed          4,1 MB  descobre impressora REMOTA na rede.
#   cups (daemon)         2,6 MB  o cups.socket FICA e sobe o daemon sozinho
#                                 quando alguém plugar uma impressora --
#                                 imprimir continua funcionando.
#   avahi-daemon          ~1 MB   nesta instalação só o cups-browsed usava.
#   bluetooth/blueman        0    a placa não tem rádio BT (/sys/class/
#                                 bluetooth nem existe); só custava boot.
#   openvpn                  0    /etc/openvpn vazio.
#
# Desligar, e não desinstalar, de propósito: quem precisar de algum destes
# num aparelho diferente reativa com um systemctl enable --now.
for _s in unattended-upgrades.service cups-browsed.service cups.service \
          avahi-daemon.service avahi-daemon.socket bluetooth.service \
          blueman-mechanism.service openvpn.service; do
  systemctl disable --now "$_s" >/dev/null 2>&1 || true
done
# O socket e o path do CUPS continuam ligados: são eles que ressuscitam o
# daemon sob demanda. Sem esta linha, uma reinstalação em cima de um sistema
# onde alguém já os tinha desligado ficaria sem impressão nenhuma.
systemctl enable cups.socket cups.path >/dev/null 2>&1 || true

# Monitores de volume do gvfs que nada nesta TV box usa: câmera fotográfica
# por PTP, iPhone/iPad por AFC e contas online do GNOME. São ~4 MB somados,
# subidos por D-Bus junto com o gerenciador de arquivos. Os que FICAM são os
# que trabalham de verdade aqui: udisks2 (pendrive, cartão) e mtp.
#
# Desativar é renomear o .monitor -- é assim que o gvfs os descobre. Um
# upgrade do pacote gvfs traz o arquivo de volta; se isso incomodar, o jeito
# definitivo é um dpkg-divert.
for _m in gphoto2 afc goa; do
  _f="/usr/share/gvfs/remote-volume-monitors/$_m.monitor"
  [ -f "$_f" ] && mv -f "$_f" "$_f.desligado-pelo-tarsila"
done 2>/dev/null || true

if [ -z "$TARSILA_USER" ]; then
  echo "==> [6/6] Habilitando o primeiro boot (assistente OOBE)…"
  mkdir -p /var/lib/tarsila
  touch /var/lib/tarsila/firstboot
  systemctl daemon-reload
  systemctl enable tarsila-oobe-init.service >/dev/null 2>&1 || true
else
  if [ "$WITH_PLYMOUTH" = 1 ]; then
    echo "==> [6/6] Splash de boot (plymouth)…"
    plymouth-set-default-theme tarsila-boot 2>/dev/null && update-initramfs -u || \
      echo "    AVISO: plymouth não configurado (sem initramfs? veja o README)"
  else
    echo "==> [6/6] Splash de boot: pulado (use --with-plymouth para incluir)"
  fi
fi

echo
if [ -z "$TARSILA_USER" ]; then
  echo "Tarsila instalada. Reinicie: o primeiro boot vai pedir a senha de"
  echo "administrador e criar a sua conta de usuário."
else
  echo "Tarsila instalada. Reinicie (ou 'systemctl restart lightdm') e entre como $TARSILA_USER."
fi
echo "BETA: testada na tvbox de referência (Debian 13 arm64); em outros sistemas"
echo "podem faltar ajustes — abra uma issue com o que encontrar."
