#!/bin/bash
# Inicio da sessao: papel de parede do tema salvo, tamanhos que dependem da
# resolucao REAL da TV e a barra de cima. Chamado por
# ~/.config/openbox/autostart.
#
# Tudo o que depende de tamanho de tela e recalculado aqui, a cada login,
# porque a tvbox negocia o modo com a TV no boot e isso varia por aparelho
# (720p, 768, 1080p, 4K): um numero de pixels gravado no disco estaria
# errado na proxima TV.
#
# UM ARQUIVO SO (05/08). O que tinha este nome era a versao XFCE (xfconf,
# "xfdesktop --reload", posicao do panel-2) e nao era chamada por ninguem:
# o unico apontamento vinha de ~/.config/autostart/, e o autostart XDG NAO
# roda nesta sessao -- o proprio autostart do Openbox anota isso na linha
# do Nextcloud ("openbox-autostart exige PyXDG, que nao esta instalado").
# O conteudo que vale e o do tarsila-ob-wallpaper-apply.sh, que continua
# valendo pelo nome antigo (link para este arquivo).
. /usr/local/lib/tarsila/comum.sh

pinta_fundo "$(wallpaper_salvo)"

# Icone da Dock proporcional a tela. So escreve se mudou: a chave e
# observada pelo Plank e escrever igual o faz redesenhar a toa.
PLK=$(icone_dock)
atual=$(dconf read /net/launchpad/plank/docks/dock1/icon-size 2>/dev/null)
[ "$atual" = "$PLK" ] || dconf write /net/launchpad/plank/docks/dock1/icon-size "$PLK" 2>/dev/null

# A barra de cima foi removida em 2026-08-15 -- aqui terminava com uma
# chamada ao tarsila-ob-bar.sh, que lia tema e resolucao, gerava o
# config.gen.ini e subia o polybar. O que estava na barra virou icone da
# Dock, e o icone da Dock ja foi dimensionado logo acima.
