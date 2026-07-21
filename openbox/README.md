# Tarsila — camada gráfica leve (Openbox)

Variante **Openbox + polybar** da interface Tarsila: substituto mais leve do
XFCE, **validado em login real** na box de referência (Amlogic S905W2, 2 GB,
Debian 13). Coexiste com o XFCE (sessão separada), mas na box de referência é
forçada como padrão via `~/.xsession`.

## Números (box de referência, 768p)
| | XFCE | Openbox |
|---|---|---|
| RAM primeiro login limpo | ~460 MB | **~295–345 MB** |
| PSS da sessão do usuário | 238 MB | **~95 MB** |
| Top bar | ~55 MB | **~13 MB** |
| CPU ocioso | ~0 % | **0 %** |

## O que muda
- WM: `xfwm4` → **openbox** (tema próprio `Tarsila`: barra cinza, botões
  ✕/□ à esquerda, título DejaVu Bold). Ao **maximizar**, a barra de título
  da janela **some** (título/botões vão pra top bar) via `tarsila-ob-decor.sh`.
- Top bar: `xfce4-panel` → **polybar** (título, ✕/restaurar, som, rede,
  relógio, energia, e o botão **Limpar Área de Trabalho**).
- Desktop/wallpaper: `xfdesktop` → **feh**; tema GTK: `xfsettingsd` →
  **xsettingsd**; notificações: `xfce4-notifyd` → **dunst**.
- Compositor: **picom** (backend `xrender --no-use-damage`) — dá cantos
  arredondados ao Plank e renderização confiável; ~0,1 % CPU.

## Botão "Limpar Área de Trabalho" (o coração da UX)
Substituiu a navegação por "3 bolinhas" (que só fazia sentido pro designer).
Um botão só-ícone (varinha mágica, pill amarelo) que **aparece apenas quando
há app aberto**; clique → confirmação central (Cancelar/Limpar); se confirmar,
**fecha tudo** (educado e depois agressivo) → mesa limpa. Também **libera RAM
de verdade** (a versão antiga só escondia as janelas). `tarsila-limpar.sh` +
`polybar/limpar-btn.sh`.

## Estabilidade — leia isto
A GPU **Mali-G31/Panfrost** segfaulta o Xorg ao abrir janelas com **glamor**
(aceleração 2D). Por isso o pacote inclui `10-modeset-panfrost.conf` com
`AccelMethod=none` (2D por software). **Sem isso a sessão cai pro login ao
abrir apps/vídeo.** Compositor GL não roda nessa GPU (GLX e EGL falham) — daí o
picom `xrender`. Em GPUs boas, remova o xorg.conf.d e use um backend GL.

## Reaproveitado do stack Tarsila (com guards p/ não vazar no XFCE)
`tarsila-monitor`, `tarsila-goto{2,3}`, state file, Plank, devilspie2, Store,
appfinder. Os scripts compartilhados (`tarsila-monitor.sh`,
`tarsila-topbar-refresh.sh`, `tarsila-tema-apply.sh`) ganharam guard por
marcador `$XDG_RUNTIME_DIR/tarsila-openbox.session` para não chamar
`xfce4-panel` no Openbox (evita o dialog "org.xfce.Panel").

## Instalação
```bash
sudo ./deploy-install.sh <usuario>
```
Instala deps, copia arquivos, a fonte de ícones, o xorg.conf.d e o `~/.xsession`
que força a sessão. Reinicie depois.

## Pendências
- Botão Limpar sem tooltip de hover (polybar não suporta sem daemon que gasta
  CPU) — o amarelo + a confirmação cobrem a descoberta.
- Pill do botão com ~1-2px de desalinho no canto esquerdo.
- Cantos arredondados de **janela** não dão nessa GPU (precisa compositor GL).
- Escala 4K de alguns tamanhos ainda por afinar.
