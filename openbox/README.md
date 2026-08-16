# Tarsila — camada gráfica leve (Openbox)

Interface **Openbox + Plank + picom**, sem barra superior: substituto mais leve
do XFCE, **validado em login real** na box de referência (Amlogic S905W2, 2 GB,
Debian 13). Coexiste com o XFCE (sessão separada), mas na box de referência é
forçada como padrão via `~/.xsession`.

> **A polybar saiu em 16/08/2026.** Este README descreve o estado depois disso.
> O histórico da barra superior está no git; se você procura `tarsila-goto*`,
> `tarsila-ob-bar.sh`, `tarsila-polybar-mode.sh` ou `~/.config/polybar/`, eles
> foram removidos junto com ela.

## Números

Box de referência (Amlogic S905W2, 768p), medidos **antes** da remoção da
polybar:

| | XFCE | Openbox |
|---|---|---|
| RAM primeiro login limpo | ~460 MB | **~295–345 MB** |
| PSS da sessão do usuário | 238 MB | **~95 MB** |
| Top bar | ~55 MB | **~13 MB** |
| CPU ocioso | ~0 % | **0 %** |

Efeito da remoção da polybar, medido **na VM de teste**, não na box:

| | antes | depois |
|---|---|---|
| forks por segundo, ocioso | 10–11 | **3** |
| processo polybar | 20,6 MB (na box) | **não existe** |

A queda de forks vem dos módulos que a barra chamava em laço: `sound.sh` a cada
3 s e `net.sh` (que roda `nmcli`) a cada 5 s.

## O que muda em relação ao XFCE

- WM: `xfwm4` → **openbox**, tema próprio `Tarsila` (barra cinza, botões ✕/□ à
  esquerda via `<titleLayout>CML</titleLayout>`, título DejaVu Bold). Maximizar
  é **nativo** (`ToggleMaximizeFull`) e a janela **mantém a barra de título** —
  antes ela era removida e o título ia para a barra superior.
- Barra superior: **não existe**. O que estava nela (som, rede, calendário,
  sistema, limpar, energia) virou **ícone na Dock**, na cauda fixa à direita.
- Dock: **Plank**, com `hide-mode='dodge-maximized'` — some sozinha diante de
  janela maximizada e volta quando não há. O botão da Dock inverte esse estado
  temporariamente; todo evento de maximizar/desmaximizar reimpõe a regra.
- Desktop/wallpaper: `xfdesktop` → **feh**; tema GTK: `xfsettingsd` →
  **xsettingsd**; notificações: `xfce4-notifyd` → **dunst**.
- Compositor: **picom** (backend `xrender --no-use-damage`) — dá cantos
  arredondados ao Plank e ao botão, e renderização confiável; ~0,1 % CPU.
  Ele é **carga útil, não enfeite**: sem picom o botão da Dock perde os cantos
  arredondados.

## Quem responde "há janela maximizada?"

`tarsila-estado.sh`. É a peça central da sessão: um daemon curto que mantém
dois `xprop -spy` (um na raiz, para `_NET_ACTIVE_WINDOW`/`_NET_CLIENT_LIST`, e
outro na janela ativa, para `_NET_WM_STATE`), grava `MAX=`/`ID=` em
`$XDG_RUNTIME_DIR/tarsila-topbar-state.txt` e aplica a política da Dock.

Substituiu o `tarsila-polybar-mode.sh`, que respondia à mesma pergunta matando
e relançando o processo da barra a cada troca de estado.

**Os dois espiões são necessários.** Um espião só na raiz não enxerga
maximização: maximizar não muda a janela ativa nem a lista de clientes, só o
`_NET_WM_STATE` da própria janela. Medido: 0 eventos na raiz contra 2 na janela.

## Botão "Limpar Área de Trabalho"

Substituiu a navegação por "3 bolinhas". Aparece apenas quando há app aberto;
clique → confirmação central (Cancelar/Limpar); se confirmar, fecha tudo
(educado e depois agressivo) → mesa limpa. Libera RAM de verdade — a versão
antiga só escondia as janelas.

Hoje é um ícone da Dock (`20-limpar-tarsila.dockitem` → `limpar-tarsila.desktop`
→ `tarsila-limpar.sh`). Como ícone de Dock ele **ganhou tooltip de hover de
graça**, que era pendência conhecida enquanto vivia na polybar.

## Estabilidade — leia isto

A GPU **Mali-G31/Panfrost** segfaulta o Xorg ao abrir janelas com **glamor**
(aceleração 2D). Por isso o pacote inclui `10-modeset-panfrost.conf` com
`AccelMethod=none` (2D por software). **Sem isso a sessão cai pro login ao
abrir apps/vídeo.** Compositor GL não roda nessa GPU (GLX e EGL falham) — daí o
picom `xrender`. Em GPUs boas, remova o xorg.conf.d e use um backend GL.

## Instalação

```bash
sudo ./deploy-install.sh <usuario>
```

Instala deps, copia arquivos, a fonte de ícones, o xorg.conf.d e o `~/.xsession`
que força a sessão. Reinicie depois.

## Pendências

- **`corner-radius` e `shadow` do picom na Mali ainda não foram testados.** Na
  VM (virtio-gpu) os dois funcionam no backend `xrender` — o congelamento que a
  documentação do picom descreve é específico do backend `glx`. A VM não
  reproduz o hardware da box, então a confirmação depende de rodar na Mali.
- **A Dock está no teto da largura.** Com 21 ícones a 52 px (o tamanho que o
  `icone_dock()` escolhe para telas de até 900 px de altura), ela pede 1409 px
  numa tela de 1366. O Plank não deixa vazar: comprime. Medido em 1360x768, o
  resultado foi 1346 px — encostando nas duas bordas, ~7 px de folga de cada
  lado. Não cabe um 22º ícone sem apertar os que já estão lá.
- **Pico de CPU na box, a investigar** — provavelmente decodificação de vídeo
  caindo para software, o que o manteria na camada de chip e fora desta base.
- **`xrandr` não está instalado na box** (só `xdpyinfo`). O `altura_tela()` já
  tem fallback para ele, mas `tarsila-resolucao-apply.sh` continua um no-op.
- Pill do botão com ~1-2 px de desalinho no canto esquerdo.
- Escala 4K de alguns tamanhos ainda por afinar.
