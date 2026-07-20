#!/bin/bash
# Acao "Tirar do Dock" do clique-direito nos icones do Plank (Desktop
# Action dos atalhos curados). Confirmacao centrada; nativos recusam.
ACAO="${1:-}"
DESKTOP="${2:-}"
[ "$ACAO" = "remove" ] && [ -f "$DESKTOP" ] || exit 1

NOME=$(sed -n 's/^Name=//p' "$DESKTOP" | head -1)
DOCK="$HOME/.config/plank/dock1/launchers"
NATIVES=/usr/share/tarsila/native-apps.txt
base=$(basename "$DESKTOP")

if grep -qxF "$base" "$NATIVES" 2>/dev/null; then
  yad --info --center --fixed --title="Dock" --width=380 \
      --text="'$NOME' é um aplicativo do sistema e fica sempre na Dock."
  exit 0
fi

yad --question --center --fixed --title="Tirar do Dock" --width=400 \
    --text="Tirar '$NOME' do Dock?\n\nO aplicativo continua instalado — você pode devolvê-lo pelo Gerenciar Dock." \
  || exit 0

item=$(grep -l "file://$DESKTOP" "$DOCK"/*.dockitem 2>/dev/null | head -1)
[ -n "$item" ] || exit 0
# nunca mexer em dockitem com o Plank rodando (o inotify dele corrompe)
pkill -x plank
sleep 0.5
rm -f "$item"
/usr/local/bin/tarsila-dock-apply.sh 2>/dev/null
nohup plank >/dev/null 2>&1 &
disown
exit 0
