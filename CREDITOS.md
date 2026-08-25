# Créditos e licenças de terceiros

O Tarsila OS é software livre sob a **GPL-3.0** (ver `LICENSE`). Este arquivo
registra o que vem de fora e sob qual licença.

## A distinção que importa aqui

O Tarsila **não redistribui** os aplicativos que integra. O `install.sh` roda
`apt-get install`, e quem entrega AbiWord, VLC, Thunar, Openbox, Gnumeric,
mpv, qpdfview, galculator, yad e os demais ao aparelho é o **repositório
oficial do Debian** — não este projeto. Cada um continua sob a própria
licença, com o Debian como distribuidor.

O código deste repositório também não é obra derivada deles: os programas são
chamados como processos separados (`subprocess`), não ligados como biblioteca.

O que a lista abaixo cobre é o oposto: o que **está versionado aqui** e por
isso viaja junto com o Tarsila.

## O que este repositório distribui de fato

### Tarsila-icons — derivado do Papirus (GPL-3.0)

`overlay/usr/share/icons/Tarsila-icons/`

Não é um tema do zero: o próprio `index.theme` declara `Inherits=Papirus` e
descreve o conjunto como "Papirus com retoques do Tarsila". São ícones
derivados, e portanto sob a **GPL-3.0** do Papirus.

- Projeto: Papirus Development Team — https://github.com/PapirusDevelopmentTeam/papirus-icon-theme
- Licença: GPL-3.0
- Fonte: os próprios arquivos `.svg` deste diretório já são a forma
  preferida para modificação, que é o que a GPL pede.

### Symbols Nerd Font

`openbox/deploy/usr/share/fonts/nerd/SymbolsNerdFont-Regular.ttf`

- Copyright (c) 2016, Ryan McIntyre
- Projeto: Nerd Fonts — https://github.com/ryanoasis/nerd-fonts
- O arquivo `.ttf` traz o aviso de copyright mas **não preenche o campo de
  licença** na tabela `name`. O projeto Nerd Fonts distribui o conjunto
  Symbols-Only sob MIT; conferir na origem antes de redistribuir em outro
  contexto.

### GTK 3 e PyGObject

Usados como biblioteca, via `python3-gi`. São **LGPL**, licença feita
justamente para permitir uso por programas de outra licença. Instalados pelo
apt, não versionados aqui.

## Marcas

"Tarsila" nomeia este projeto. O nome e a identidade visual são da Piano Lab
Ribeirão e não estão cobertos pela GPL-3.0, que licencia software — não marca.

## Se faltar alguém

Achou algo redistribuído aqui sem o crédito devido? Abra uma issue. A intenção
é creditar tudo corretamente, e correção de crédito é bem-vinda.
