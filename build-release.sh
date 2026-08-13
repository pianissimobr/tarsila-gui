#!/bin/bash
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT="$(dirname "$REPO_DIR")"
DEST="$REPO_DIR/release"
GH_USER="${GITHUB_USER:-pianissimobr}"

echo "==> Gerando release offline em $DEST/"
rm -rf "$DEST"
mkdir -p "$DEST/pacotes"

APPS="tarsila-chromium tarsila-email tarsila-agenda tarsila-app-management tarsila-store"

for app in $APPS; do
  echo "    $app..."
  if [ -d "$PARENT/$app" ]; then
    ( cd "$PARENT/$app" && ./build-deb.sh )
    cp "$PARENT/$app"/*.deb "$DEST/pacotes/"
  elif [ -n "${GITHUB_TOKEN:-}" ]; then
    tmp="/tmp/tarsila-build-$app"
    rm -rf "$tmp"
    git clone --depth 1 "https://oauth2:${GITHUB_TOKEN}@github.com/$GH_USER/$app.git" "$tmp" 2>/dev/null || {
      echo "      ERRO: clone falhou"; continue
    }
    ( cd "$tmp" && ./build-deb.sh )
    cp "$tmp"/*.deb "$DEST/pacotes/"
    rm -rf "$tmp"
  else
    echo "      NÃO ENCONTRADO — defina GITHUB_TOKEN ou clone o repo ao lado"
  fi
done

echo "==> Copiando arquivos do core..."
cp "$REPO_DIR/install.sh" "$DEST/"
cp -a "$REPO_DIR/overlay" "$DEST/"
cp -a "$REPO_DIR/skel" "$DEST/"
[ -d "$REPO_DIR/openbox" ] && cp -a "$REPO_DIR/openbox" "$DEST/"
find "$DEST" -name "*.deb" -path "*/overlay/*" -delete 2>/dev/null || true
find "$DEST" -name "*.deb" -path "*/skel/*" -delete 2>/dev/null || true

echo ""
echo "==> Release pronto:"
find "$DEST" -maxdepth 2 -not -path '*/.git/*' | sort | sed "s|$DEST|   |" | head -30
echo "   ..."
echo ""
echo "    Copie esta pasta para a tvbox e rode: sudo ./install.sh"