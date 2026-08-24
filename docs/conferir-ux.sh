#!/bin/bash
# conferir-ux.sh -- levanta o estado do aparelho para o docs/CHECKLIST-UX.md
#
# SOMENTE LEITURA. Nao instala, nao escreve, nao altera configuracao.
# Rode na propria box:  DISPLAY=:0 bash conferir-ux.sh
# Ou de fora:  ssh tarsila@IP "DISPLAY=:0 bash /tmp/conferir-ux.sh"
#
# A saida e para leitura humana e comparacao com o checklist -- nao ha
# codigo de saida significativo.
# AUDITORIA SOMENTE LEITURA. Nao escreve nada, nao instala nada.
export LC_ALL=C
p() { printf '\n===== %s =====\n' "$1"; }
tem() { command -v "$1" >/dev/null 2>&1 && echo "sim" || echo "NAO"; }
pkg() { dpkg -l "$1" 2>/dev/null | grep -q '^ii' && echo "sim" || echo "NAO"; }

p "IDENTIDADE"
echo "hostname: $(hostname)"
echo "machine-id: $(cut -c1-8 /etc/machine-id 2>/dev/null)"
cat /etc/tarsila-release 2>/dev/null || echo "SEM /etc/tarsila-release"
grep -E '^(NAME|PRETTY_NAME|ID)=' /etc/os-release
echo "--- lightdm greeter ---"
grep -rE '^(greeter-session|autologin-user|autologin)' /etc/lightdm/ 2>/dev/null | grep -v '^\s*#'

p "HORA E LOCALIZACAO"
echo "data: $(date)"
echo "fuso: $(cat /etc/timezone 2>/dev/null)"
echo "fake-hwclock: $(pkg fake-hwclock)  chrony: $(pkg chrony)  timesyncd: $(pkg systemd-timesyncd)"
systemctl is-active systemd-timesyncd 2>/dev/null | sed 's/^/timesyncd ativo: /'
timedatectl 2>/dev/null | grep -E 'synchronized|NTP'
echo "--- locale ---"
# ARMADILHA: este script exporta LC_ALL=C no topo para estabilizar a saida das
# outras ferramentas. Consultar 'locale' assim faz ele responder C para tudo, e
# o relatorio acusa um defeito que nao existe -- foi exatamente o que aconteceu
# em 17/08/2026. O 'env -u LC_ALL' pergunta ao ambiente de verdade.
env -u LC_ALL locale 2>&1 | grep -E '^(LANG|LANGUAGE|LC_TIME|LC_NUMERIC|LC_MONETARY|LC_ALL)='
echo "  data de verdade:   $(env -u LC_ALL date '+%A, %d de %B de %Y')"
env -u LC_ALL printf '  decimal virgula:   %.2f\n' 1,5 2>/dev/null \
  || echo "  decimal virgula:   NAO (locale numerico nao e pt_BR)"
locale -a 2>/dev/null | grep -i pt_br

p "TECLADO"
echo "--- /etc/default/keyboard ---"
grep -E 'XKB' /etc/default/keyboard 2>/dev/null
echo "--- cedilha em /etc/environment ---"
grep -iE 'IM_MODULE' /etc/environment /etc/profile.d/*.sh 2>/dev/null || echo "  NENHUM IM_MODULE definido"
echo "numlockx: $(tem numlockx)  onboard: $(pkg onboard)"
echo "--- sysrq ---"
sysctl kernel.sysrq 2>/dev/null
grep -rh sysrq /etc/sysctl.d/ /etc/sysctl.conf 2>/dev/null | grep -v '^#'

p "ATALHOS OPENBOX (rc.xml)"
RC=$HOME/.config/openbox/rc.xml
if [ -f "$RC" ]; then
  echo "keybinds definidos:"
  grep -oE 'key="[^"]+"' "$RC" | sed 's/key="//;s/"//' | tr '\n' ' '; echo
  echo "--- Print/captura ---"
  grep -iE 'print|screenshot|scrot|xfce4-screenshooter' "$RC" | head -10
else
  echo "SEM rc.xml em $RC"
fi
echo "captura instalada: scrot=$(tem scrot) xfce4-screenshooter=$(tem xfce4-screenshooter) maim=$(tem maim)"
echo "pasta de destino: $(ls -d ~/Imagens 2>/dev/null || echo 'SEM ~/Imagens')"

p "PASTAS DO USUARIO"
cat ~/.config/user-dirs.dirs 2>/dev/null | grep -v '^#' || echo "SEM user-dirs.dirs"
ls ~ 2>/dev/null | tr '\n' ' '; echo

p "PONTEIRO E FONTES"
echo "--- Xresources / cursor ---"
grep -riE 'Xcursor' ~/.Xresources ~/.config/xsettingsd/xsettingsd.conf /etc/X11/ 2>/dev/null | head
grep -iE 'Cursor|Font|Dpi|Xft' ~/.config/xsettingsd/xsettingsd.conf 2>/dev/null
echo "emoji: $(pkg fonts-noto-color-emoji)  dejavu: $(pkg fonts-dejavu-core)"

p "MIDIA REMOVIVEL"
echo "exfatprogs: $(pkg exfatprogs)  exfat-fuse: $(pkg exfat-fuse)  ntfs-3g: $(pkg ntfs-3g)  udisks2: $(pkg udisks2)"
echo "udiskie rodando: $(pgrep -c udiskie 2>/dev/null || echo 0)"
echo "gvfs: $(pkg gvfs)  thunar: $(pkg thunar)"

p "AUDIO"
echo "pipewire: $(pkg pipewire)  pulseaudio: $(pkg pulseaudio)"
pactl info 2>/dev/null | grep -E 'Server Name|Default Sink'
echo "--- sinks ---"
pactl list short sinks 2>/dev/null
echo "--- volume ---"
pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | head -1
pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null

p "REDE"
echo "hostname: $(hostname)   avahi: $(pkg avahi-daemon)"
systemctl is-active avahi-daemon 2>/dev/null
echo "--- dominio regulatorio ---"
iw reg get 2>/dev/null | head -4 || echo "  iw nao instalado"
echo "--- conectividade NM ---"
nmcli -t -f RUNNING,STATE,CONNECTIVITY general 2>/dev/null
grep -rh 'connectivity' /etc/NetworkManager/ 2>/dev/null | grep -v '^#' | head -5

p "BLUETOOTH"
echo "bluez: $(pkg bluez)  blueman: $(pkg blueman)"
hciconfig 2>/dev/null | head -3 || echo "  sem adaptador visivel"
systemctl is-active bluetooth 2>/dev/null

p "ENERGIA E SESSAO"
echo "suspend suportado: $(cat /sys/power/state 2>/dev/null)"
echo "xscreensaver: $(pkg xscreensaver)  light-locker: $(pkg light-locker)  xss-lock: $(pkg xss-lock)"
echo "--- DPMS agora ---"
xset q 2>/dev/null | grep -A2 'DPMS\|Screen Saver' | head -8
echo "--- polkit desligar sem senha ---"
ls /etc/polkit-1/localauthority/50-local.d/ /etc/polkit-1/rules.d/ 2>/dev/null

p "NOTIFICACOES"
echo "dunst: $(pkg dunst)  rodando: $(pgrep -c dunst 2>/dev/null || echo 0)"
grep -E '^\s*(origin|offset|timeout|geometry)' ~/.config/dunst/dunstrc 2>/dev/null | head

p "APLICATIVOS PADRAO"
echo "--- mimeapps.list do usuario ---"
head -25 ~/.config/mimeapps.list 2>/dev/null || echo "  SEM ~/.config/mimeapps.list"
echo "--- xdg-mime consultas ---"
for m in application/pdf image/png video/mp4 audio/mpeg application/zip text/plain x-scheme-handler/http x-scheme-handler/mailto; do
  printf '  %-32s %s\n' "$m" "$(xdg-mime query default "$m" 2>/dev/null || echo '(nada)')"
done
echo "xarchiver: $(pkg xarchiver)  p7zip: $(pkg p7zip-full)  unrar: $(pkg unrar-free)$(pkg unrar)"

p "AREA DE TRANSFERENCIA"
echo "qlipper: $(pkg qlipper)  de pe: $(pgrep -cx qlipper 2>/dev/null || echo 0)"
# NAO basta o pacote estar instalado: o que importa e se a selecao SOBREVIVE a
# morte do processo que copiou. Foi assim que autocutsel e gpaste-2 foram
# reprovados em 17/08 -- os dois instalam e sobem, e os dois perdem o conteudo.
if command -v xclip >/dev/null 2>&1; then
  _f="conferir-$$"
  printf '%s' "$_f" | timeout 3 xclip -selection clipboard -i 2>/dev/null
  sleep 2; pkill -x xclip 2>/dev/null; sleep 1
  if [ "$(timeout 4 xclip -selection clipboard -o 2>/dev/null)" = "$_f" ]; then
    echo "  TESTE REAL: copiar / fechar o dono / colar -> SOBREVIVEU"
  else
    echo "  TESTE REAL: copiar / fechar o dono / colar -> PERDEU (sem gerenciador util)"
  fi
else
  echo "  (xclip ausente: nao da para fazer o teste real)"
fi

p "CHROMIUM"
echo "chromium: $(pkg chromium)"
ls -la /usr/local/bin/tarsila-chromium.sh 2>/dev/null
grep -oE '\-\-[a-z0-9-]+(=[^ "]*)?' /usr/local/bin/tarsila-chromium.sh 2>/dev/null | sort -u | tr '\n' ' '; echo
echo "--- extensoes / politicas ---"
ls /etc/chromium/policies/managed/ 2>/dev/null && cat /etc/chromium/policies/managed/*.json 2>/dev/null | head -30
echo "--- hosts blocklist ---"
wc -l /etc/hosts 2>/dev/null

p "IMPRESSAO"
echo "cups: $(pkg cups)  cups-filters: $(pkg cups-filters)  hplip: $(pkg hplip)  simple-scan: $(pkg simple-scan)  sane: $(pkg sane-utils)"
systemctl is-active cups 2>/dev/null

p "ACESSIBILIDADE"
echo "magnifier: $(pkg xzoom)$(pkg magnus)"
xkbset q 2>/dev/null | head -5
echo "--- sticky keys agora ---"
xset q 2>/dev/null | grep -i 'sticky'

p "HARDWARE AMLOGIC"
echo "--- governor GPU ---"
for g in /sys/class/devfreq/*/governor; do echo "  $g = $(cat $g 2>/dev/null)"; done
echo "--- persistencia do governor ---"
grep -rl devfreq /etc/udev/rules.d/ /etc/systemd/system/ /etc/rc.local /usr/local/bin/ 2>/dev/null | head
echo "--- temperatura ---"
for t in /sys/class/thermal/thermal_zone*/temp; do echo "  $t = $(cat $t 2>/dev/null)"; done
echo "--- cpufreq ---"
ls /sys/devices/system/cpu/cpu0/cpufreq/ 2>/dev/null | head -3 || echo "  sem cpufreq"
echo "--- zram / earlyoom ---"
zramctl 2>/dev/null
echo "earlyoom: $(pkg earlyoom) ativo=$(systemctl is-active earlyoom 2>/dev/null)"
free -m

p "ARMAZENAMENTO E LOGS"
df -h / /tmp 2>/dev/null
mount | grep -E ' /tmp ' || echo "  /tmp NAO e tmpfs"
grep -E '^\s*SystemMaxUse' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null || echo "  journald sem SystemMaxUse"
du -sh /var/log/journal 2>/dev/null

p "SESSAO GRAFICA AGORA"
ps -u "$(whoami)" -o rss=,comm= --sort=-rss 2>/dev/null | head -15
echo "--- resolucao ---"
xdpyinfo 2>/dev/null | grep dimensions
echo "xrandr: $(tem xrandr)"
echo "--- scripts tarsila ---"
ls /usr/local/bin/ | grep -c '^tarsila-'
echo "--- erros na sessao ---"
tail -20 ~/.xsession-errors 2>/dev/null

p "FIM"
p() { printf '\n===== %s =====\n' "$1"; }

p "SWAP / ZRAM"
cat /proc/swaps
ls /sys/block/ | grep -i zram || echo "  sem dispositivo zram"
lsmod 2>/dev/null | grep -i zram || echo "  modulo zram nao carregado"
systemctl is-enabled zramswap 2>/dev/null; systemctl is-enabled zram-setup@zram0 2>/dev/null

p "DPMS / SCREENSAVER"
xset q 2>&1 | tail -20

p "MENU DE ENERGIA"
ls -la /usr/local/bin/tarsila-ob-power.sh /usr/local/bin/tarsila-power* 2>/dev/null
grep -oE '(Suspender|Hibernar|suspend|hibernate|Desligar|Reiniciar|poweroff|reboot)' /usr/local/bin/tarsila-ob-power.sh 2>/dev/null | sort -u

p "DESLIGAR SEM SENHA"
timeout 8 dbus-send --system --print-reply --dest=org.freedesktop.login1 \
  /org/freedesktop/login1 org.freedesktop.login1.Manager.CanPowerOff 2>&1 | tail -2
timeout 8 dbus-send --system --print-reply --dest=org.freedesktop.login1 \
  /org/freedesktop/login1 org.freedesktop.login1.Manager.CanReboot 2>&1 | tail -2

p "CHROMIUM LAUNCHER"
find /usr/local/bin /usr/bin -name '*chromium*' 2>/dev/null
for f in /usr/local/bin/tarsila-chromium*; do
  [ -f "$f" ] && { echo "--- $f ---"; grep -oE '\-\-[a-z0-9-]+' "$f" | sort -u | tr '\n' ' '; echo; }
done

p "MIMEAPPS COMPLETO"
echo "--- secoes do usuario ---"
grep -n '^\[' ~/.config/mimeapps.list 2>/dev/null
echo "--- existe Default Applications? ---"
sed -n '/\[Default Applications\]/,$p' ~/.config/mimeapps.list 2>/dev/null | head -20
echo "--- sistema ---"
ls /usr/share/applications/mimeapps.list /etc/xdg/mimeapps.list 2>/dev/null
echo "--- ristretto/mousepad instalados? ---"
for a in ristretto mousepad qpdfview mpv abiword; do printf '  %-12s %s\n' "$a" "$(command -v $a || echo NAO)"; done

p "TECLADO ABNT / CEDILHA"
setxkbmap -query 2>/dev/null
echo "GTK_IM_MODULE=${GTK_IM_MODULE:-(vazio)}  QT_IM_MODULE=${QT_IM_MODULE:-(vazio)}"

p "PASTAS DO USUARIO - REAL"
ls -d ~/Música ~/Vídeos ~/Musicas ~/Videos ~/Pictures ~/Documents 2>/dev/null
echo "xdg-user-dirs-update: $(command -v xdg-user-dirs-update || echo NAO)"

p "OVERSCAN / MODO DE VIDEO"
cat /proc/cmdline
ls /sys/class/drm/*/modes 2>/dev/null | head
for m in /sys/class/drm/card*-HDMI*/modes; do echo "--- $m ---"; head -3 "$m" 2>/dev/null; done
for s in /sys/class/drm/card*-HDMI*/status; do echo "$s = $(cat $s)"; done

p "BLUETOOTH ADAPTADOR"
ls /sys/class/bluetooth/ 2>/dev/null || echo "  nenhum adaptador"
lsusb 2>/dev/null | head

p "REDE - WIFI"
nmcli -t -f DEVICE,TYPE,STATE device 2>/dev/null
iw list 2>/dev/null | head -3 || echo "  iw ausente"

p "AUTOSTART REAL DA SESSAO"
grep -vE '^\s*#|^\s*$' ~/.config/openbox/autostart 2>/dev/null

p "ATALHOS - rc.xml integral (mouse+key)"
grep -cE '<keybind|<mousebind' ~/.config/openbox/rc.xml
grep -A3 'key="A-F4"' ~/.config/openbox/rc.xml | head -6

p "FIM2"
