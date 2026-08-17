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
# Ate 17/08/2026 havia aqui um ritual: pkill -x plank, apagar o arquivo,
# dock-apply, subir o Plank de novo. Existia porque o inotify do Plank
# corrompia dockitem mexido ao vivo.
#
# O Plank saiu em 16/08. O pkill virou linha morta -- nao havia mais o que
# matar -- e, pior, ninguem avisava a Dock nova: tirar um icone nao surtia
# efeito nenhum ate o proximo login. O `nohup plank` do fim ainda seria capaz
# de subir um Plank intruso se o pacote voltasse a ser instalado um dia.
#
# Agora a tarsila-dock observa esta pasta e se remonta sozinha em ~400 ms.
# Nada a matar, nada a reiniciar, ninguem a avisar.
rm -f "$item"
/usr/local/bin/tarsila-dock-apply.sh 2>/dev/null
exit 0
