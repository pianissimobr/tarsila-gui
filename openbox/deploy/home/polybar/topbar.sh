#!/bin/bash
# Modulo unico da topbar (fusionou title.sh + buttons.sh em 07/08).
# Estado B (compact): espaco vazio.
# Estado A (full, MAX=1):  ✕  restaurar  Nome do App
RT="${XDG_RUNTIME_DIR:-/tmp}"
STATE="$RT/tarsila-topbar-state.txt"
CLOSE=$(printf "\xef\x80\x8d")
RESTORE=$(printf "\xef\x81\xa6")

emit(){
  local max id name wmclass t
  max=0; id=""
  # Le MAX e ID numa unica passagem (builtin, sem sed+head por ciclo).
  if [ -f "$STATE" ]; then
    while IFS='=' read -r k v; do
      case "$k" in
        MAX) max="$v" ;;
        ID)  id="$v" ;;
      esac
    done < "$STATE"
  fi
  # Fonte de verdade e o MAX do state file. O antigo MODE_FILE
  # (tarsila-polybar-mode.txt) foi ABANDONADO em 06/08 porque podia mentir,
  # e desde entao ninguem o escreve -- mas esta linha continuava lendo. Como
  # o redirecionamento "<arquivo" e feito pelo SHELL, o 2>/dev/null (que vale
  # para o tr) nao silenciava nada: o bash imprimia "linha 13: ... Arquivo ou
  # diretorio inexistente" a cada 2 s, e o polybar mostrava esse texto
  # piscando no lugar do titulo da janela.
  if [ "$max" != "1" ]; then
    echo " "
    return
  fi
  [ -n "$id" ] || { echo " "; return; }

  t=$(xdotool getwindowname "$id" 2>/dev/null || true)
  name=$t
  wmclass=$(xprop -id "$id" WM_CLASS 2>/dev/null | sed -n "s/.*\"\\([^\"]*\\)\", \"[^\"]*\".*/\\1/p")
  case "${wmclass,,}" in
    thunar)          name="Arquivos" ;;
    galculator)      name="Calculadora" ;;
    tarsila-config)  name="Ajustes" ;;
    qpdfview)        name="Leitor de PDF" ;;
    chromium|chromium-browser) name="Navegador de Internet" ;;
  esac
  [ ${#name} -gt 60 ] && name="${name:0:60}\\u2026"

  printf "%%{A1:/usr/local/bin/tarsila-topbar-close.sh ${id}:}%%{T3}%s%%{T-}%%{A}   %%{A1:/usr/local/bin/tarsila-goto2.sh:}%%{T3}%s%%{T-}%%{A}%%{T2}   %s%%{T-}\n" \
    "$CLOSE" "$RESTORE" "$name"
}

emit
xprop -spy -root _NET_ACTIVE_WINDOW 2>/dev/null \
  | while true; do
      if read -t 2 -r _; then
        emit
      else
        rc=$?
        [ "$rc" -gt 128 ] && { emit; continue; }
        break
      fi
    done
