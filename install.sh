#!/bin/bash
#
# Tarsila — instalador da camada gráfica (BETA)
#
# Instala a interface Tarsila (XFCE + Plank + top bar + Loja) sobre um
# Debian 13 (trixie) já instalado. Pensado para ARM64 (tvbox/SBC), mas os
# scripts são independentes de arquitetura.
#
# Uso:  sudo ./install.sh <usuario>
#       sudo ./install.sh <usuario> --with-plymouth   (inclui splash de boot)
#
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode como root: sudo ./install.sh <usuario>"; exit 1; }
TARSILA_USER="${1:-}"
[ -n "$TARSILA_USER" ] || { echo "Uso: sudo ./install.sh <usuario> [--with-plymouth]"; exit 1; }
id "$TARSILA_USER" >/dev/null 2>&1 || { echo "Usuário '$TARSILA_USER' não existe (crie com adduser)"; exit 1; }
WITH_PLYMOUTH=0; [ "${2:-}" = "--with-plymouth" ] && WITH_PLYMOUTH=1
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="$(getent passwd "$TARSILA_USER" | cut -d: -f6)"

echo "==> [1/6] Instalando dependências (apt)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  xfce4-session xfce4-panel xfce4-settings xfdesktop4 xfwm4 \
  xfce4-genmon-plugin xfce4-pulseaudio-plugin xfce4-power-manager \
  xfce4-notifyd xfce4-terminal xfce4-appfinder \
  plank devilspie2 yad lightdm lightdm-gtk-greeter \
  papirus-icon-theme thunar gvfs gvfs-daemons \
  python3-gi gir1.2-gtk-3.0 python3-gi-cairo \
  network-manager wmctrl xdotool x11-xserver-utils dconf-cli \
  lxpolkit sudo curl chromium

# tarsila-app-management (AppFinder, instalador/desinstalador de .deb)
# vive em repositório separado. Se o apt ainda não o conhece, instala o
# .deb local construído pelo repositório irmão.
if ! apt-get install -y tarsila-app-management; then
  LOCAL_DEB=$(ls "$REPO_DIR"/../tarsila-app-management/*_all.deb 2>/dev/null | head -1 || true)
  if [ -n "$LOCAL_DEB" ]; then
    apt-get install -y "$LOCAL_DEB" || \
      echo "    AVISO: não foi possível instalar tarsila-app-management"
  else
    echo "    AVISO: tarsila-app-management não encontrado — AppFinder e desinstalador indisponíveis"
  fi
fi
[ "$WITH_PLYMOUTH" = 1 ] && apt-get install -y plymouth plymouth-themes

# agenda-tarsila vem de repositório separado (pacotes/agenda-tarsila/ no repo).
# Se o apt ainda não o conhece, constrói e instala o .deb local.
if ! apt-get install -y agenda-tarsila; then
  if [ -d "$REPO_DIR/pacotes/agenda-tarsila/DEBIAN" ]; then
    dpkg-deb --build --root-owner-group "$REPO_DIR/pacotes/agenda-tarsila" /tmp/agenda-tarsila.deb >/dev/null 2>&1
    apt-get install -y /tmp/agenda-tarsila.deb || \
      echo "    AVISO: não foi possível instalar agenda-tarsila"
    rm -f /tmp/agenda-tarsila.deb
  else
    echo "    AVISO: agenda-tarsila não encontrado — Agenda indisponível"
  fi
fi

# tarsila-email vem de repositório separado (tarsila-email/). Se o apt ainda
# não o conhece, instala o .deb local construído pelo repositório irmão.
if ! apt-get install -y tarsila-email; then
  LOCAL_DEB=$(ls "$REPO_DIR"/../tarsila-email/*_all.deb 2>/dev/null | head -1 || true)
  if [ -n "$LOCAL_DEB" ]; then
    apt-get install -y "$LOCAL_DEB" || \
      echo "    AVISO: não foi possível instalar tarsila-email"
  else
    echo "    AVISO: tarsila-email não encontrado — E-mail indisponível"
  fi
fi

# tarsila-store vem de pacotes/tarsila-store/ (mesmo repo). Se o apt ainda
# não a conhece, constrói e instala o .deb local.
if ! apt-get install -y tarsila-store; then
  if [ -f "$REPO_DIR/pacotes/tarsila-store/build-deb.sh" ]; then
    bash "$REPO_DIR/pacotes/tarsila-store/build-deb.sh" /tmp >/dev/null 2>&1 || true
    LOCAL_DEB=$(ls /tmp/tarsila-store_*_all.deb 2>/dev/null | head -1 || true)
    if [ -n "$LOCAL_DEB" ]; then
      apt-get install -y "$LOCAL_DEB" || \
        echo "    AVISO: não foi possível instalar tarsila-store"
      rm -f /tmp/tarsila-store_*_all.deb
    else
      echo "    AVISO: tarsila-store não foi construído — Loja indisponível"
    fi
  else
    echo "    AVISO: tarsila-store não encontrado — Loja indisponível"
  fi
fi

echo "==> [2/6] Copiando arquivos do sistema (overlay)…"
# sudoers vai por caminho separado (precisa de validação); o resto copia direto
tar -cf - -C "$REPO_DIR/overlay" --exclude=./etc/sudoers.d . | tar -xpf - -C /
chmod 755 /usr/local/bin/tarsila-* 2>/dev/null || true

# Adota no catálogo curado os apps de repositórios separados. Os .deb do
# email e da agenda instalam só o .desktop genérico em /usr/share/applications/;
# o tarsila-atalho-criar cria o curado em /usr/share/tarsila/applications/
# (com ações de dock e desinstalação), para aparecerem no dock/appfinder.
if [ -x /usr/local/bin/tarsila-atalho-criar ]; then
  tarsila-atalho-criar agenda-tarsila 2>/dev/null || true
  tarsila-atalho-criar tarsila-email 2>/dev/null || true
fi

echo "==> [3/6] Configurando sudoers (usuário: $TARSILA_USER)…"
sed "s/^alan /$TARSILA_USER /" "$REPO_DIR/overlay/etc/sudoers.d/tarsila-config" > /etc/sudoers.d/tarsila-config
chmod 440 /etc/sudoers.d/tarsila-config
visudo -c >/dev/null || { echo "ERRO: sudoers inválido"; exit 1; }
usermod -aG sudo "$TARSILA_USER"

echo "==> [4/6] Configurações do usuário $TARSILA_USER…"
tar -cf - -C "$REPO_DIR/skel" .config user-dirs.dirs user-dirs.locale 2>/dev/null | tar -xpf - -C "$HOME_DIR" || \
  cp -a "$REPO_DIR/skel/.config" "$HOME_DIR/"
sudo -u "$TARSILA_USER" dbus-run-session -- dconf load /net/launchpad/plank/ < "$REPO_DIR/skel/plank-dconf.ini" || \
  echo "    AVISO: dconf load falhou — a ordem da dock será aplicada no primeiro login"
chown -R "$TARSILA_USER:$TARSILA_USER" "$HOME_DIR"

echo "==> [5/6] MIME, ícones e serviços…"
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -q /usr/share/icons/Tarsila-icons 2>/dev/null || true
systemctl enable lightdm NetworkManager >/dev/null 2>&1 || true

if [ "$WITH_PLYMOUTH" = 1 ]; then
  echo "==> [6/6] Splash de boot (plymouth)…"
  plymouth-set-default-theme tarsila-boot 2>/dev/null && update-initramfs -u || \
    echo "    AVISO: plymouth não configurado (sem initramfs? veja o README)"
else
  echo "==> [6/6] Splash de boot: pulado (use --with-plymouth para incluir)"
fi

echo
echo "Tarsila instalada. Reinicie (ou 'systemctl restart lightdm') e entre como $TARSILA_USER."
echo "BETA: testada na tvbox de referência (Debian 13 arm64); em outros sistemas"
echo "podem faltar ajustes — abra uma issue com o que encontrar."
