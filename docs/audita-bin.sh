#!/bin/bash
# Auditoria de /usr/local/bin: o que cada script e, quem o chama, e o que ele
# chama que nao existe. Somente leitura.
export LC_ALL=C
BIN=/usr/local/bin

# Onde alguem poderia chamar um script: sessao, WM, atalhos, unidades, cron.
LOCAIS=(
  /usr/local/bin /usr/local/lib/tarsila
  /usr/share/tarsila /usr/share/applications /usr/share/xsessions
  /etc/xdg /etc/skel /etc/systemd /etc/X11 /etc/sudoers.d /etc/cron.d
  "$HOME/.config" "$HOME/.local/share/applications" "$HOME/.xsessionrc"
  /usr/share/lightdm /etc/lightdm
)

echo "########## 1. INVENTARIO ##########"
for f in "$BIN"/tarsila-*; do
  [ -f "$f" ] || continue
  n=$(basename "$f")
  tipo=$(head -1 "$f" | sed 's/^#!//;s|/usr/bin/env ||;s|.*/||' | cut -d' ' -f1)
  [ -x "$f" ] && x=x || x=-
  printf '%s|%s|%s|%s\n' "$n" "${tipo:-binario}" "$(wc -l <"$f")" "$x"
done

echo
echo "########## 2. CITACOES A PLANK / POLYBAR / XFCE ##########"
for f in "$BIN"/tarsila-*; do
  [ -f "$f" ] || continue
  h=$(grep -inE 'plank|polybar|xfce|xfconf|xfdesktop' "$f" | head -40)
  [ -n "$h" ] || continue
  echo "=== $(basename "$f")"
  # separa citacao em comentario de citacao em codigo
  while IFS= read -r l; do
    num=${l%%:*}; txt=${l#*:}
    corpo=$(printf '%s' "$txt" | sed 's/^[[:space:]]*//')
    case "$corpo" in
      \#*|\"\"\"*|"'''"*) marca="COMENT" ;;
      *) marca="CODIGO" ;;
    esac
    printf '   %-6s %5s  %s\n' "$marca" "$num" "$(printf '%s' "$corpo" | cut -c1-110)"
  done <<< "$h"
done

echo
echo "########## 3. QUEM CHAMA QUEM ##########"
for f in "$BIN"/tarsila-*; do
  [ -f "$f" ] || continue
  n=$(basename "$f")
  # procura o nome em todo lugar, menos no proprio arquivo
  refs=$(grep -rlI --exclude-dir=__pycache__ --exclude-dir=.git -- "$n" "${LOCAIS[@]}" 2>/dev/null \
         | grep -v "^$f\$" | sed "s|$HOME|~|" | sort -u)
  cnt=$(printf '%s' "$refs" | grep -c . )
  printf '%-34s %2s  %s\n' "$n" "$cnt" "$(printf '%s' "$refs" | tr '\n' ' ' | cut -c1-150)"
done

echo
echo "########## 4. PROGRAMAS CHAMADOS QUE NAO EXISTEM ##########"
for f in "$BIN"/tarsila-*; do
  [ -f "$f" ] || continue
  falta=""
  # comandos externos plausiveis citados no corpo
  cmds=$(grep -ohE '\b(/usr/local/bin/[a-zA-Z0-9._-]+|/usr/bin/[a-zA-Z0-9._-]+|/usr/share/tarsila/[a-zA-Z0-9._/-]+)' "$f" 2>/dev/null | sort -u)
  for c in $cmds; do
    [ -e "$c" ] || falta+="$c "
  done
  # nomes soltos de binarios conhecidos do stack
  for c in plank polybar xfconf-query xfce4-panel xfdesktop wmctrl xdotool xprop \
           yad zenity picom dunst devilspie2 pactl nmcli notify-send xrandr \
           xdpyinfo qlipper scrot import feh nitrogen conky; do
    grep -qE "(^|[^-a-zA-Z0-9_./])$c([^-a-zA-Z0-9_.]|$)" "$f" 2>/dev/null || continue
    command -v "$c" >/dev/null 2>&1 || falta+="$c(NAO INSTALADO) "
  done
  [ -n "$falta" ] && printf '%-34s %s\n' "$(basename "$f")" "$falta"
done

echo
echo "########## 5. ARQUIVOS DE ESTADO CITADOS ##########"
# ARMADILHA: nao chute /run/user/1000. O usuario desta box e uid 1003, e a
# primeira versao deste script deu meia duzia de arquivos de estado como
# inexistentes so por causa disso -- todos existiam.
RUNTIME="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
echo "   (XDG_RUNTIME_DIR = $RUNTIME)"
grep -rhoE '(\$XDG_RUNTIME_DIR|\$RT|/run/user/[0-9]+|~|\$HOME)/[a-zA-Z0-9._/-]+' "$BIN"/tarsila-* 2>/dev/null \
  | sed "s|\$XDG_RUNTIME_DIR|$RUNTIME|;s|^\$RT|$RUNTIME|;s|^/run/user/[0-9]*|$RUNTIME|;s|^~|$HOME|;s|\$HOME|$HOME|" \
  | sort | uniq -c | sort -rn | head -25 | while read -r c p; do
      [ -e "$p" ] && e="existe" || e="NAO EXISTE"
      printf '   %2sx  %-52s %s\n' "$c" "$p" "$e"
    done

echo
echo "########## 6. O QUE ESTA DE PE AGORA ##########"
ps -u "$(id -un)" -o comm= | sort | uniq -c | sort -rn | head -25 | sed 's/^/   /'

echo
echo "########## 7. AUTOSTART EFETIVO ##########"
for d in "$HOME/.config/autostart" /etc/xdg/autostart; do
  [ -d "$d" ] || continue
  echo "=== $d"
  for a in "$d"/*.desktop; do
    [ -e "$a" ] || continue
    printf '   %-40s %s\n' "$(basename "$a")" "$(sed -n 's/^Exec=//p' "$a" | head -1 | cut -c1-70)"
  done
done
echo "=== ~/.config/openbox/autostart"
grep -vE '^\s*(#|$)' "$HOME/.config/openbox/autostart" 2>/dev/null | sed 's/^/   /'
