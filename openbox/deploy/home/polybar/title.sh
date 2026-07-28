#!/bin/bash
# LÍDER do top bar: computa MAX/ID da janela ativa, grava o state file
# (mesmo formato/consumidores da versão XFCE) e mostra o nome da janela
# quando maximizada. Event-driven via xprop -spy + rede de segurança 2s.
RT="${XDG_RUNTIME_DIR:-/tmp}"; STATE="$RT/tarsila-topbar-state.txt"
emit(){
  id=$(xdotool getactivewindow 2>/dev/null)
  if [ -n "$id" ] && xprop -id "$id" _NET_WM_STATE 2>/dev/null | grep -q MAXIMIZED; then
    name=$(xdotool getwindowname "$id" 2>/dev/null)
    wmclass=$(xprop -id "$id" WM_CLASS 2>/dev/null | sed -n 's/.*"\([^"]*\)", "[^"]*".*/\1/p')
      # A comparacao e em MINUSCULAS: o WM_CLASS do Thunar e "thunar", e a
      # tabela antiga esperava "Thunar" -- nunca casava, e a barra mostrava
      # "alan - Thunar" em vez de "Arquivos".
      case "${wmclass,,}" in
        thunar)          name="Arquivos" ;;
        galculator)      name="Calculadora" ;;
        tarsila-config)  name="Ajustes" ;;
        qpdfview)        name="Leitor de PDF" ;;
        chromium|chromium-browser)
          # Navegador nao anuncia o nome: ja tem abas, endereco e os botoes da
          # janela. Repetir o titulo da pagina aqui so ocupa a barra.
          name="" ;;
      esac
    [ ${#name} -gt 60 ] && name="${name:0:60}…"
    printf 'MAX=1\nID=%s\n' "$id" > "$STATE"
    printf '%%{T2}   %s%%{T-}\n' "$name"
  else
    printf 'MAX=0\nID=\n' > "$STATE"
    echo " "
  fi
}
emit
xprop -spy -root _NET_ACTIVE_WINDOW _NET_CLIENT_LIST _NET_SHOWING_DESKTOP 2>/dev/null \
  | while :; do read -t 2 -r _ || true; emit; done
