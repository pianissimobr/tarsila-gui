#!/bin/bash
# Monta o .deb da Tarsila Store.
#
# Autonomo: le tudo deste repositorio, sem depender de uma loja ja instalada
# na maquina. (O build antigo copiava capas, catalogo e whitelist de
# /opt/tarsila-store, o que so funcionava rodando dentro da propria TV.)
#
# Uso: bash build-deb.sh [pasta-de-destino]     # padrao: ./dist
set -euo pipefail

VER="4.0.0"
AQUI="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-$AQUI/dist}"
STAGE="$(mktemp -d)/tarsila-store-${VER}"
trap 'rm -rf "$(dirname "$STAGE")"' EXIT

command -v dpkg-deb >/dev/null || { echo "ERRO: falta dpkg-deb (apt install dpkg-dev)" >&2; exit 1; }

mkdir -p "$DEST" \
         "$STAGE/DEBIAN" \
         "$STAGE/opt/tarsila-store/bin" \
         "$STAGE/opt/tarsila-store/lib" \
         "$STAGE/opt/tarsila-store/loja" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/tarsila/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps" \
         "$STAGE/etc/sudoers.d"

# --- dados: catalogo, capas, icones, whitelist -------------------------
# O HTML/CSS/JS da versao web vai junto de proposito: o catalogo em
# loja/catalog/ e a mesma fonte para os dois lados, e manter a pasta permite
# abrir a loja no navegador para comparar a aparencia com a versao GTK.
cp -a "$AQUI/loja/." "$STAGE/opt/tarsila-store/loja/"
install -m 644 "$AQUI/whitelist.txt" "$STAGE/opt/tarsila-store/whitelist.txt"

# --- backend e utilitarios com privilegio ------------------------------
# tarsila-atalho-criar, tarsila-deb-instalar e tarsila-deb-gui.py nao moram
# mais aqui: foram para o tarsila-app-management (dependencia deste pacote).
install -m 755 "$AQUI/backend/tarsila-pkg" \
               "$STAGE/opt/tarsila-store/bin/tarsila-pkg"
install -m 755 "$AQUI/backend/tarsila-store-handler.sh" \
               "$STAGE/opt/tarsila-store/tarsila-store-handler.sh"

# --- o aplicativo GTK --------------------------------------------------
install -m 755 "$AQUI/src/tarsila-store-gtk.py" \
               "$STAGE/opt/tarsila-store/bin/tarsila-store-gtk.py"
install -m 644 "$AQUI/src/tarsila_store_dados.py" \
               "$STAGE/opt/tarsila-store/lib/tarsila_store_dados.py"
install -m 644 "$AQUI/src/tarsila_store_visual.py" \
               "$STAGE/opt/tarsila-store/lib/tarsila_store_visual.py"
ln -sf /opt/tarsila-store/bin/tarsila-store-gtk.py "$STAGE/usr/bin/tarsila-store"

install -m 644 "$AQUI/desktop/appstore.png" \
               "$STAGE/usr/share/icons/hicolor/256x256/apps/tarsila-store.png"

# --- sudoers (tarsila-pkg so roda com NOPASSWD; ALL = qualquer usuario) -
install -m 440 "$AQUI/etc/sudoers.d/tarsila-store" \
               "$STAGE/etc/sudoers.d/tarsila-store"

# --- atalhos -----------------------------------------------------------
# O atalho comum chama /usr/bin/tarsila-store direto -- funciona em qualquer
# Debian. O "-tarsila" passa pelos wrappers do Tarsila OS (tarsila-abrindo e
# tarsila-uma-janela), que fora dele nao existem; por isso ele vai so para a
# grade curada do sistema, e nunca para /usr/share/applications.
for d in tarsila-store.desktop tarsila-protocol.desktop; do
  install -m 644 "$AQUI/desktop/$d" "$STAGE/usr/share/applications/$d"
done
install -m 644 "$AQUI/desktop/tarsila-store-tarsila.desktop" \
               "$STAGE/usr/share/tarsila/applications/tarsila-store.desktop"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: tarsila-store
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, sudo, tarsila-app-management (>= 1.0)
Recommends: libnotify-bin, policykit-1
Maintainer: Tarsila OS <tarsila@local>
Description: Loja de aplicativos do Tarsila OS
 Interface nativa em GTK3 para instalar e remover aplicativos e jogos de uma
 lista curada. Sem WebKit e sem servidor HTTP em processo separado: um unico
 processo Python, pensado para maquina de 2 GB de RAM.
 .
 A instalacao em si passa pelo tarsila-pkg, que so aceita pacotes da
 whitelist -- a loja nunca chama o apt diretamente.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
# O backend HTTP da versao web nao existe mais: se ficou algum rodando de uma
# sessao anterior, so ocuparia memoria -- a loja GTK nao fala com ele.
pkill -f /opt/tarsila-store/bin/tarsila-backend.py 2>/dev/null || true
# Falha fechada: se a regra de sudoers nao validar, a loja nao instala nada.
visudo -c >/dev/null 2>&1 || echo "AVISO: sudoers invalido — a loja nao vai conseguir instalar" >&2
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "$STAGE" "$DEST/tarsila-store_${VER}_all.deb" >/dev/null
echo "OK: $DEST/tarsila-store_${VER}_all.deb"
ls -lh "$DEST/tarsila-store_${VER}_all.deb" | awk '{print "  tamanho:", $5}'
