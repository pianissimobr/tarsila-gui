#!/bin/bash
# Tarsila AppFinder - Lançador curado com gerenciamento de dock
# Instalado automaticamente em install_tarsila_appfinder.py
set -euo pipefail

CURATED_DIR="/usr/share/tarsila/applications"
DOCK_CONFIG="/root/.config/plank/dock1/launchers/"
DOCK_LIMIT=20

# Cria diretório do dock se não existir
mkdir -p "$DOCK_CONFIG"

# Lê os apps curados
declare -A curated_apps
for f in "$CURATED_DIR"/*.desktop; do
  [ -e "$f" ] || continue
  name=$(sed -n 's/^Name=//p' "$f" | head -n1)
  [ -n "$name" ] && curated_apps["$name"]="$f"
done

if [ "${#curated_apps[@]}" -eq 0 ]; then
  zenity --info --title="Tarsila AppFinder" \
    --text="Nenhum aplicativo curado encontrado em:\n$CURATED_DIR" \
    --width=400
  exit 0
fi

# Função: verifica se app está no dock
is_in_dock() {
  local app_name="$1"
  local desktop_file="${curated_apps[$app_name]}"
  
  find "$DOCK_CONFIG" -name "*.dockitem" 2>/dev/null | while read -r dockitem; do
    if grep -q "^Launcher=file://$desktop_file$" "$dockitem" 2>/dev/null; then
      return 0
    fi
  done
  return 1
}

# Função: conta apps no dock
count_dock_items() {
  find "$DOCK_CONFIG" -name "*.dockitem" 2>/dev/null | wc -l
}

# Função: fixar no dock
pin_to_dock() {
  local app_name="$1"
  local desktop_file="${curated_apps[$app_name]}"
  local dock_count=$(count_dock_items)
  
  if [ "$dock_count" -ge "$DOCK_LIMIT" ]; then
    zenity --warning --title="Limite atingido" \
      --text="O dock já tem $DOCK_LIMIT aplicativos.\nRemova algum antes de adicionar outro." \
      --width=350
    return 1
  fi
  
  local base_name=$(basename "$desktop_file" .desktop)
  local dockitem="$DOCK_CONFIG/${base_name}.dockitem"
  
  cat > "$dockitem" << EOF
[DockItem]
Launcher=file://$desktop_file
EOF
  
  zenity --info --title="Fixado" \
    --text="'$app_name' foi fixado no dock." \
    --timeout=2
  return 0
}

# Função: desfixar do dock
unpin_from_dock() {
  local app_name="$1"
  local desktop_file="${curated_apps[$app_name]}"
  
  find "$DOCK_CONFIG" -name "*.dockitem" 2>/dev/null | while read -r dockitem; do
    if grep -q "^Launcher=file://$desktop_file$" "$dockitem" 2>/dev/null; then
      rm -f "$dockitem"
      zenity --info --title="Desfixado" \
        --text="'$app_name' foi removido do dock." \
        --timeout=2
      return 0
    fi
  done
  
  zenity --warning --title="Não encontrado" \
    --text="'$app_name' não está no dock." \
    --timeout=2
  return 1
}

# Função: desinstalar (backend silencioso)
uninstall_app() {
  local app_name="$1"
  local desktop_file="${curated_apps[$app_name]}"
  local package_name=""
  
  # Tenta extrair o nome do pacote
  if grep -q "^X-Package=" "$desktop_file" 2>/dev/null; then
    package_name=$(sed -n 's/^X-Package=//p' "$desktop_file" | head -n1)
  else
    local exec_cmd=$(sed -n 's/^Exec=//p' "$desktop_file" | head -n1 | cut -d' ' -f1)
    if command -v dpkg &>/dev/null && [ -n "$exec_cmd" ]; then
      package_name=$(dpkg -S "$exec_cmd" 2>/dev/null | cut -d: -f1 | head -n1)
    fi
  fi
  
  if [ -z "$package_name" ]; then
    package_name=$(echo "$app_name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
  fi
  
  if ! zenity --question --title="Desinstalar" \
    --text="Deseja realmente desinstalar '$app_name'?\n\nPacote: $package_name\n\nO processo será executado em segundo plano." \
    --width=400; then
    return 0
  fi
  
  # Desinstala em background
  (
    if command -v apt &>/dev/null; then
      sudo apt remove -y "$package_name" > /dev/null 2>&1 || true
    elif command -v dpkg &>/dev/null; then
      sudo dpkg -r "$package_name" > /dev/null 2>&1 || true
    else
      rm -f "$desktop_file"
    fi
    
    # Remove do dock
    find "$DOCK_CONFIG" -name "*.dockitem" 2>/dev/null | while read -r dockitem; do
      if grep -q "$(basename "$desktop_file")" "$dockitem" 2>/dev/null; then
        rm -f "$dockitem"
      fi
    done
    
    if command -v notify-send &>/dev/null; then
      notify-send "Desinstalação concluída" "'$app_name' foi removido."
    fi
  ) &
  
  zenity --info --title="Desinstalando" \
    --text="A desinstalação de '$app_name' está em andamento em segundo plano." \
    --timeout=3
  
  return 0
}

# Função: gera lista para exibição
generate_list() {
  local in_dock=""
  
  for name in "${!curated_apps[@]}"; do
    if is_in_dock "$name"; then
      in_dock=" ✓"
    else
      in_dock=""
    fi
    echo "$name$in_dock"
  done | sort
}

# Interface principal
selected_app=""
while true; do
  app_list=$(generate_list)
  
  chosen=$(echo "$app_list" | zenity --list \
    --title="Tarsila AppFinder" \
    --text="Selecione um aplicativo curado\n(Clique direito para opções)" \
    --column="Aplicativo" \
    --width=500 --height=400 \
    --ok-label="Executar" \
    --cancel-label="Sair")
  
  [ $? -ne 0 ] && exit 0
  
  # Remove indicador de dock se houver
  selected_app=$(echo "$chosen" | sed 's/ ✓$//')
  
  # Mostra menu de contexto
  action=$(zenity --list --title="Opções para $selected_app" \
    --text="Escolha uma ação:" \
    --column="Ação" \
    --column="Descrição" \
    "Executar" "Abrir o aplicativo" \
    "Fixar" "Adicionar ao dock" \
    "Desfixar" "Remover do dock" \
    "Desinstalar" "Remover o aplicativo" \
    --width=400 --height=300)
  
  case "$action" in
    "Executar")
      exec gio launch "${curated_apps[$selected_app]}"
      break
      ;;
    "Fixar")
      if is_in_dock "$selected_app"; then
        zenity --warning --text="'$selected_app' já está no dock." --timeout=2
      else
        pin_to_dock "$selected_app"
      fi
      ;;
    "Desfixar")
      unpin_from_dock "$selected_app"
      ;;
    "Desinstalar")
      uninstall_app "$selected_app"
      ;;
    *)
      # Sai ou volta
      ;;
  esac
done
