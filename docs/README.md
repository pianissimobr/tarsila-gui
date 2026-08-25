# Documentação do Tarsila OS

Esta pasta tem duas naturezas misturadas, e o objetivo deste índice é deixar
claro qual é qual: **o que descreve o sistema de hoje** e **o que registra
como se chegou até aqui**. Sem essa separação, um documento datado parece
uma descrição do presente — e manda quem lê para o lugar errado.

## Atual — descreve o sistema como ele é

| arquivo | o que é |
|---|---|
| [`MAPA.md`](MAPA.md) | Inventário dos componentes: cada script, o que faz e quem o chama. O ponto de partida para se localizar no projeto. |
| [`CHECKLIST-UX.md`](CHECKLIST-UX.md) | Roteiro de conferência da interface, com o estado de cada item. Já foi reescrito uma vez quando o XFCE saiu — ele mesmo explica o que mudou. |
| [`ESPEC-dock-gtk.md`](ESPEC-dock-gtk.md) | As medidas em pixel que fundamentam a Dock, tiradas de captura de tela. É a razão por trás de números que continuam no código — a cor `rgb(21,17,40)` do tema padrão saiu daqui. |
| [`categorias.md`](categorias.md) | Classificação funcional dos scripts. |
| [`otimizacao.md`](otimizacao.md) | Custos de rede e CPU identificados e o que foi feito a respeito. |

## Ferramentas — para rodar, não para ler

| arquivo | o que faz |
|---|---|
| [`conferir-ux.sh`](conferir-ux.sh) | Roda na box e confere os itens do `CHECKLIST-UX.md`. |
| [`audita-bin.sh`](audita-bin.sh) | Varre `/usr/local/bin` e reporta o estado dos scripts instalados. |

## [`historico/`](historico/) — registro, não descrição

Estes documentos **não descrevem o sistema atual** e não devem ser lidos como
se descrevessem. Ficam porque explicam decisões que ainda valem, e apagá-los
custaria mais do que guardá-los.

| arquivo | o que registra | por que não é atual |
|---|---|---|
| `PLANO-MIGRACAO.md` | A decisão de separar os aplicativos em repositórios próprios | **Já foi executado.** O plano falava em criar um `tarsila-core`; o repositório resultante se chama `tarsila-gui`. O `Status: planejamento` no topo é de antes da execução. |
| `ARQUIVO-MORTO.md` | O que foi removido do sistema e por quê | É um cemitério, por definição. As menções a Plank, polybar e XFCE são o assunto, não desatualização. |
| `DIAGNOSTICO-BIN.md` | Levantamento dos 54 scripts em `/usr/local/bin`, feito em 17/08/2026 | Retrato de um dia. Vários desses scripts mudaram depois — inclusive alguns que o documento descreve como vivos. |
| `Mapa-requisições.md` | As rotas HTTP do cliente de e-mail | Duas razões: o e-mail vive no próprio repositório desde a separação, e as rotas mudaram em parte (hoje há `/api/bootstrap`, `/api/accounts`, `/api/drafts` que não constam aqui). |

## Ao mexer aqui

Documento que registra uma medição deve dizer **quando** foi medido e **em que
hardware** — sem isso, um número perde o sentido em seis meses. Os arquivos
desta pasta seguem essa regra; vale mantê-la.
