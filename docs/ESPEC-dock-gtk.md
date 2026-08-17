# Especificação visual da Dock, para reimplementar em GTK+CSS

Medido na VM em 16/08/2026, tela 1920x1080, ícone 72, 21 itens, tema `Tarsila`.
Referência em pixel capturada com `scrot`; os números abaixo saíram da imagem,
não da matemática interna do Plank.

O objetivo é substituir o Plank por uma janela GTK única que contenha **também**
o botão, hoje um processo separado (`tarsila-tela-estados`). Numa janela só não
existe mais defasagem entre os dois ao mostrar/esconder.

## Geometria

| Elemento | Valor |
|---|---|
| Corpo da dock | `x=16..1902`, `y=975..1079` → **1887 × 105** |
| Raio dos cantos | **8 px**, nas quatro pontas (`TopRoundness=BottomRoundness=8`) |
| Caixa do ícone | **72 × 72**, deslocada **16 px** do topo da dock |
| Passo entre células | **87 px** |
| Folga lateral | **30 px** de cada lado — `(1887 − 21×87) / 2` |
| Sobra abaixo do ícone | 17 px — é onde vai o indicador de app aberto |
| Botão | **46 × 20** em `937,955`, centralizado e encostado no topo da dock |

O botão termina exatamente onde a dock começa (`955 + 20 = 975`), então a janela
integrada fica: **`x=0, y=955, 1920 × 125`**, com o corpo da dock em `(16, 20)` e
o botão em `(937, 0)`, ambos em coordenadas da janela.

A dock é centralizada: `(1920 − 1887) / 2 = 16`. O botão também:
`(1920 − 46) / 2 = 937`.

## Cores

Do tema em `~/.local/share/plank/themes/Tarsila/dock.theme`:

```
Fill        = rgb(21, 17, 40)     sólido, sem gradiente
OuterStroke = rgb(21, 17, 40)     mesma cor do fundo, ou seja, invisível
InnerStroke = rgba(255, 255, 255, 40)
```

**Atenção ao InnerStroke.** O valor declarado é alfa 40, mas o medido na tela
não é uniforme — é um gradiente vertical:

| Linha | Cor medida | Alfa efetivo |
|---|---|---|
| `y=976` (1 px abaixo do topo) | `(138,136,148)` | ~0,50 |
| `y=1078` (1 px acima da base) | `(65,62,80)` | ~0,19 |

É uma borda interna de 1 px com gradiente de `rgba(255,255,255,.50)` no topo
até `rgba(255,255,255,.19)` na base. Esse detalhe é o que dá o relevo sutil da
dock; sem ele o retângulo fica chapado.

Essa borda atravessa a dock inteira, então cuidado ao medir ícones por
"pixel diferente do fundo": as linhas `y=976` e `y=1078` acusam conteúdo em
todas as colunas. Media-se entre `y=978` e `y=1076`.

## Comportamento a preservar

- `hide-mode='dodge-maximized'`: some diante de janela maximizada, volta quando
  não há. O botão inverte o estado provisoriamente, e todo evento de
  maximizar/desmaximizar reimpõe a regra.
- Revelar ao encostar o cursor na borda de baixo (`pressure-reveal`).
- **Todas as animações do tema são zero** (`SlideTime`, `FadeTime`, `GlowSize`,
  bounce, `ActiveTime`). A dock é estática — não há nada de animado a imitar.
- Tooltip no hover de cada ícone.
- Clique esquerdo lança pelo `Exec=` do `.desktop`.
- Clique direito abre as `[Desktop Action]` do `.desktop`: "Tirar do Dock"
  (`tarsila-dock-item.sh`) e "Desinstalar" (`tarsila-app-uninstall.sh`).
- Indicador de app aberto, `IndicatorSize=5`, na sobra de 17 px abaixo do ícone.

## Modelo de dados

```
~/.config/plank/dock1/launchers/NN-nome.dockitem   ordem = ordem do nome
  └─ Launcher=file:///usr/share/tarsila/applications/<app>.desktop
       └─ Name, Icon, Exec, StartupWMClass, [Desktop Action ...]
```

Tema de ícones: `Tarsila-icons` (via `Net/IconThemeName` do xsettingsd).

## Divisão sugerida entre CSS e Cairo

CSS dá conta do corpo: `background-color` e `border-radius: 8px` numa janela
com visual ARGB. O que **não** sai em GTK CSS é a borda interna de 1 px com
gradiente vertical — não há `::before`, e `border-image` com gradiente é
impraticável. Esse detalhe pede Cairo.

Os ícones são melhores como widgets GTK de verdade (`Gtk.Button` + `Gtk.Image`):
hover pelo CSS `:hover`, tooltip e clique de graça, menu de contexto de graça.
Desenhar tudo à mão em Cairo jogaria fora essas três coisas.
