#!/bin/sh
# Hora/data com fonte Roboto (font-5) via tags no output — polybar 3.7
# ignora label-font em custom/script.
LC_TIME=$(. /etc/default/locale 2>/dev/null; echo "${LC_TIME:-${LANG:-pt_BR.UTF-8}}")
export LC_TIME
printf '%s' "%{T6}$(date '+%H:%M  %d de %B')%{T-}"
