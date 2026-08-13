#!/bin/bash
# Botao "tres riscos" do dock: lista os aplicativos instalados que ainda NAO
# estao fixados no dock. Se houver algum, mostra um menu para escolher e
# abrir; se nao houver nenhum, so avisa que ja esta tudo visivel.
set -euo pipefail

CURATED_DIR=/usr/share/tarsila/applications
SEARCH_DIRS=(/usr/share/applications "$CURATED_DIR")

declare -A curated_names
for f in "$CURATED_DIR"/*.desktop; do
  [ -e "$f" ] || continue
  name=$(sed -n 's/^Name=//p' "$f" | head -n1)
  [ -n "$name" ] && curated_names["$name"]=1
done

declare -A extra_apps
for dir in "${SEARCH_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  for f in "$dir"/*.desktop; do
    [ -e "$f" ] || continue
    grep -q '^NoDisplay=true' "$f" && continue
    grep -q '^Type=Application' "$f" || continue
    name=$(sed -n 's/^Name=//p' "$f" | head -n1)
    [ -z "$name" ] && continue
    [ -n "${curated_names[$name]:-}" ] && continue
    extra_apps["$name"]="$f"
  done
done

if [ "${#extra_apps[@]}" -eq 0 ]; then
  zenity --info --title="Aplicativos" \
    --text="Todos os seus aplicativos estão sendo exibidos." \
    --width=320
  exit 0
fi

chosen=$(printf '%s\n' "${!extra_apps[@]}" | sort | zenity --list \
  --title="Mais aplicativos" \
  --text="Aplicativos instalados que ainda não estão no dock:" \
  --column="Aplicativo" --width=420 --height=480)

[ -n "$chosen" ] && exec gio launch "${extra_apps[$chosen]}"
