#!/bin/bash
# Acao "Desinstalar" do clique-direito nos icones do Plank (Desktop
# Action dos atalhos curados). Mesma logica de resolucao/protecoes do
# AppFinder: X-Package= > Exec+dpkg -S; atalhos web e apps fora da
# whitelist sao recusados com mensagem amigavel; remocao roda em
# segundo plano via sudo tarsila-pkg (unico caminho NOPASSWD).
DESKTOP="${1:-}"
[ -f "$DESKTOP" ] || exit 1

WHITELIST=/opt/tarsila-store/whitelist.txt
PKG_HELPER=/opt/tarsila-store/bin/tarsila-pkg
NATIVES=/usr/share/tarsila/native-apps.txt
DOCK="$HOME/.config/plank/dock1/launchers"
NOME=$(sed -n 's/^Name=//p' "$DESKTOP" | head -1)
base=$(basename "$DESKTOP")

recusa() {
  yad --info --center --fixed --title="Desinstalar" --width=400 --text="$1"
  exit 0
}

grep -qxF "$base" "$NATIVES" 2>/dev/null \
  && recusa "'$NOME' faz parte do sistema e não pode ser desinstalado."

exec_line=$(sed -n 's/^Exec=//p' "$DESKTOP" | head -1)
case "$exec_line" in
  *--app=*) recusa "'$NOME' é um atalho do sistema e não pode ser desinstalado por aqui." ;;
esac

package=$(sed -n 's/^X-Package=//p' "$DESKTOP" | head -1)
if [ -z "$package" ]; then
  cmd=${exec_line%% *}
  path=$(command -v "$cmd" 2>/dev/null)
  [ -n "$path" ] && package=$(dpkg -S "$path" 2>/dev/null | cut -d: -f1 | head -1)
fi
{ [ -z "$package" ] || ! grep -qxF "$package" "$WHITELIST" 2>/dev/null; } \
  && recusa "'$NOME' faz parte do sistema e não pode ser desinstalado."

yad --question --center --fixed --title="Desinstalar" --width=400 \
    --text="Deseja realmente desinstalar '$NOME'?" || exit 0

(
  if sudo -n "$PKG_HELPER" remove "$package" >/dev/null 2>&1; then
    item=$(grep -l "file://$DESKTOP" "$DOCK"/*.dockitem 2>/dev/null | head -1)
    if [ -n "$item" ]; then
      pkill -x plank
      sleep 0.5
      rm -f "$item"
      /usr/local/bin/tarsila-dock-apply.sh 2>/dev/null
      nohup plank >/dev/null 2>&1 &
    fi
    command -v notify-send >/dev/null \
      && notify-send "Desinstalação concluída" "'$NOME' foi removido."
  else
    command -v notify-send >/dev/null \
      && notify-send "Desinstalação falhou" "Não foi possível remover '$NOME'."
  fi
) &
yad --info --center --fixed --title="Desinstalando" --timeout=3 \
    --text="A desinstalação de '$NOME' está em andamento em segundo plano."
exit 0
