# Tarsila — camada gráfica leve (Openbox)

Variante **Openbox + polybar** da interface Tarsila, um substituto mais leve
do XFCE que economiza RAM sem perder as funções essenciais. Roda **em
coexistência** com a versão XFCE: instala uma sessão separada no lightdm
("Tarsila (Openbox)"), sem alterar a sessão padrão.

## Por quê (medido na box de referência: Amlogic S905W2, 2 GB, Debian 13, 768p)

| | XFCE (atual) | Openbox (esta) |
|---|---|---|
| PSS da sessão do usuário | ~238 MB | **~168 MB** (~142 MB sem compositor) |
| Top bar | xfce4-panel + ~6 wrappers ~55 MB | **polybar ~13 MB** |
| RAM usada (sessão carregada) | ~463 MB | **~403 MB** |
| CPU ocioso da top bar | ~0 % | **0 %** (event-driven) |

## O que muda e o que fica

**Substituídos (leves):**
- WM/compositor: `xfwm4` -> **openbox** (+ `picom` opcional, desligado por padrão)
- Top bar: `xfce4-panel`+genmon -> **polybar** (título, botões fechar/restaurar,
  3 bolinhas de workspace, som, rede, relógio, energia)
- Desktop/wallpaper: `xfdesktop` -> **feh**
- Tema GTK/ícones/fonte: `xfsettingsd` -> **xsettingsd**
- Notificações: `xfce4-notifyd` -> **dunst**

**Reaproveitados sem alteração (o "cérebro" da Tarsila):**
- `tarsila-monitor` (contagem/sons/renice + estado do top bar)
- `tarsila-goto{1,2,3}.sh` (workspaces lógicos), state file `tarsila-topbar-state.txt`
- Plank (dock), devilspie2 (regras de janela), Tarsila Store, appfinder, instalador .deb

A top bar do polybar **lê o mesmo state file** que a versão XFCE: o módulo de
título é o "líder" (grava MAX/ID), bolinhas e botões são "seguidores".
Event-driven via `xprop -spy` (sem polling) -> sem regressão de CPU.

## Instalação

Num Debian 13 já com a camada Tarsila (repo raiz) instalada:

    sudo ./deploy-install.sh

Instala dependências (openbox, polybar, dunst, xsettingsd, feh,
fonts-font-awesome...), copia os arquivos e registra a sessão. **Não** altera a
sessão padrão -> escolha "Tarsila (Openbox)" no login para testar. Para tornar
padrão: `echo 'Session=tarsila-openbox' >> ~/.dmrc` do usuário.

## Estrutura

    deploy/usr/local/bin/    tarsila-ob-session, tarsila-ob-bar.sh (gera o config
                             do polybar a partir do tema+resolução), tarsila-ob-tema-apply.sh,
                             tarsila-ob-wallpaper-apply.sh, tarsila-ob-power.sh
    deploy/usr/share/xsessions/tarsila-openbox.desktop
    deploy/home/openbox/     rc.xml, menu.xml, autostart, environment
    deploy/home/polybar/     config.ini (template) + módulos (title/dots/buttons/net/sound/power)
    deploy/home/{dunst,xsettingsd}/
    prototipo/               tpb-setup.sh -- protótipo original só da top bar

## Temas

`tarsila-ob-tema-apply.sh <padrao|maritimo|escuro|brasileiro|personalizado> [imagem]`
troca wallpaper (feh) + cor da barra e do texto (polybar) + tema do Plank
(dconf). Bem mais simples que a versão XFCE: sem recolor de SVG, sem gtk.css,
sem xfconf -- a cor da barra E do texto é a cor do polybar (TB_BG/TB_FG).

## Pendências (ajustes finos)

- Ícones via Font Awesome 4 (pacote Debian); alguns glyphs são aproximações
  (rede cabeada usa "plug"). Uma Nerd Font daria paridade visual exata.
- Escala 4K: geometria da barra adapta por faixa de altura, mas a margem
  superior do Openbox (rc.xml) é fixa em 34px -- ajustar junto.
- Módulo de som depende do PipeWire da sessão real (não sobe em teste nu).
