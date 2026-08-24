# Checklist de acabamento — adaptado ao ambiente real

Substitui o `tarsila-checklist-ux.md` original, que foi escrito para **XFCE +
xfwm4 + painel + polybar + bandeja**. Nada disso existe mais: hoje é **Openbox +
Dock GTK própria**, sem painel, sem barra superior e sem bandeja de sistema.
Cerca de um terço dos itens antigos verificava coisas que já não têm onde
acontecer.

Cada item abaixo foi **conferido na box de teste** em 17/08/2026 —
`tarsila@10.42.0.106`, Amlogic s905w2, aarch64, kernel 6.18.38-meson64, 1366x768,
1922 MB. O que está marcado como pronto foi medido, não presumido. Reproduza com
`docs/conferir-ux.sh`, que é somente-leitura.

Legenda: **OK** conferido funcionando · **FALTA** conferido ausente ou quebrado ·
**N/A** não se aplica a este ambiente · **?** precisa de teste manual (humano na
frente da TV).

> Atenção a uma distinção que vale para a lista inteira: *box* é este aparelho,
> montado em 21/07 e atualizado à mão desde então; *repo* é o que uma instalação
> nova produziria hoje. Onde os dois divergem, está anotado — corrigir só a box
> perde o conserto no próximo flash.

---

## Placar

203 itens com status. Contagem conferida sobre o próprio arquivo:

| | | |
|---|---:|---|
| **OK** | 83 | medido, não presumido |
| **?** | 69 | precisa de humano na frente da TV |
| **FALTA** | 35 | conferido ausente ou quebrado |
| **N/A** | 9 | o ambiente mudou |
| **PARCIAL** | 7 | funciona pela metade, explicado no item |

Mais **9 categorias inteiras** da lista original saíram — estão no final, com o
motivo de cada uma.

Os 69 pendentes de teste humano não são sobra de trabalho: são itens que só um
par de olhos na TV responde (overscan, som saindo mesmo, acento em três apps).
Foram deixados assim de propósito, e formam o roteiro de aceitação.

**Bloqueadores** — impedem um leigo de concluir uma tarefa sozinho.
**Os três reais foram resolvidos em 17/08/2026**; o registro fica porque o
diagnóstico de cada um vale mais que a correção.

### 1. Abrir arquivo caía no aplicativo errado — RESOLVIDO

Eram **dois defeitos independentes** que davam o mesmo sintoma, e o primeiro
escondia o segundo.

**Defeito A — o mimeapps apontava para o vazio.** Quatro alvos citados em
`skel/.config/mimeapps.list` **não estavam na lista do `install.sh`**:
`org.xfce.ristretto`, `org.xfce.mousepad`, `mpv` e `xarchiver`. Sem erro
nenhum: o XDG cai no próximo candidato que declare o tipo, então PNG abria no
`display` do ImageMagick e TXT no AbiWord. Numa instalação nova, vídeo e zip
cairiam junto — na box não caíram porque os dois foram instalados à mão.

Corrigido apontando para `gpicview` e `l3afpad` (GTK3, ~140 KB cada, zero
dependência nova) em vez de reinstalar os do XFCE, e acrescentando `mpv`,
`xarchiver`, `p7zip-full` e `unar` ao `install.sh`. Junto foi o
`webp-pixbuf-loader`: **nenhum app GTK abria `.webp`**, que é o formato que a
web entrega hoje.

**Defeito B — o pacote `file` não estava instalado.** Este é o mais instrutivo.
O `/usr/bin/xdg-mime` chama `/usr/bin/file` **direto, por caminho absoluto**
(linha 822) para descobrir o tipo do arquivo. Sem ele a detecção volta vazia, o
`xdg-open` desiste do mimeapps e cai no ramo do navegador. Resultado: **todo
`xdg-open` abria no Chromium**, qualquer arquivo, enquanto o GIO — que é o que
o Thunar usa — acertava.

Duas rotas para a mesma ação, só uma quebrada, nenhuma mensagem em lugar
nenhum. Só apareceu porque o teste abriu o arquivo de verdade e olhou **qual
processo nasceu**, em vez de confiar no `xdg-mime query default`, que respondia
certo o tempo todo.

Verificado de ponta a ponta: `.png` → janela do `gpicview`, `.txt` → janela do
`l3afpad`.

### 2. Sem gerenciador de área de transferência — RESOLVIDO

Nada instalado. O autostart tentava `clipit`, depois `parcellite`, os dois sob
`command -v`, e seguia calado quando nenhum existia — o sistema passou meses
sem gerenciador sem nunca acusar.

Não dá para voltar ao `clipit`: no trixie ele virou pacote de transição para o
`diodon` e arrasta zeitgeist + xapian, **nove pacotes** e um indexador com
banco de dados, num aparelho de 2 GB.

Escolhido por teste (copiar, matar o dono da seleção, colar):

| | resultado | custo |
|---|---|---|
| linha de base, sem nada | perdeu | — |
| `autocutsel` | **perdeu** | 2 MB |
| `gpaste-2` | grava histórico mas **não reassume a seleção** — o `Ctrl+V` simples continua falhando | ~9 MB |
| **`qlipper`** | **sobreviveu** | **19 MB PSS** |

Os dois descartados foram removidos da box. O custo do `qlipper` é real e está
anotado: 19 MB de PSS numa sessão que era de 173 MB. Se aparecer coisa mais
leve **que reassuma a seleção**, trocar.

### 3. Relógio atrasado — RESOLVIDO na box, mas a causa não era a suspeitada

O sintoma era real: a box marcava 16/08 08:30 com o dia sendo 17/08. A causa
**não** é o `fake-hwclock` nem o `timesyncd`, que estão os dois corretos —
`fake-hwclock-load`, `-save` e o timer estão `enabled` (só o
`fake-hwclock.service` monolítico está `masked`, que é como o pacote moderno
ship). O `timesyncd` está ativo e até selecionou servidor.

**A box não tem internet.** TCP 443 falha, UDP 123 falha, ICMP falha. Ela só
enxerga o notebook em `10.42.0.1`. O DNS resolve porque quem responde é o
`dnsmasq` do próprio notebook, o que fez o teste superficial parecer saudável.

A causa está no notebook, não no produto: o Docker põe a política da chain
`FORWARD` em `DROP` e todas as regras de aceite são específicas do `docker0`;
não existe `MASQUERADE` para `10.42.0.0/24`. O contador da política mostrava os
pacotes da box sendo descartados.

Relógio acertado na box a partir do notebook, com `fake-hwclock save` em
seguida para sobreviver ao desligamento. **O `timesyncd` vai assumir sozinho no
primeiro boot com internet de verdade** — não há nada a corrigir no Tarsila.

Fica um item de produto, que é o que o checklist original queria dizer: TV box
sem RTC numa rede que bloqueia NTP (escola, empresa) termina exatamente assim.
Um caminho de hora por HTTP, que passa onde o UDP 123 não passa, é barato e
resolve. Ainda **não** está feito.

### 4. `LC_TIME` em `C` — NÃO EXISTIA. Erro meu

Relatado como bloqueador em cima de leitura errada. O script de auditoria
exporta `LC_ALL=C` no topo para estabilizar a saída das outras ferramentas, e
então perguntou o locale ao próprio ambiente que ele mesmo havia alterado.

Em shell limpo está tudo certo: `LC_TIME=pt_BR.UTF-8`, a data sai
`domingo, 16 de agosto de 2026` e o `printf` **recusa** `1234.5` justamente
porque o separador decimal é vírgula. O `conferir-ux.sh` foi corrigido para
consultar com `env -u LC_ALL` e agora imprime a data e o separador de verdade,
em vez de repetir o eco da própria contaminação.

---

## 1. Teclado — atalhos

Openbox tem **31** binds hoje: `A-Tab`, `A-S-Tab`, `A-F4`, `Print`, `A-Print` e
as três de volume. O resto da lista antiga nunca existiu.

| Item | Estado |
|---|---|
| `Print` → tela cheia em `~/Imagens` + notificação | **OK** |
| `A-Print` → janela ativa | **OK** |
| `~/Imagens` existe e é o destino | **OK** |
| `S-Print` → região | **FALTA** — `scrot -s` |
| `C-Print` → direto para a área de transferência | **FALTA** — depende do item 3 dos bloqueadores |
| `C-A-T` → terminal | **FALTA** |
| `W-E` → Thunar | **FALTA** |
| `W-D` → mostrar área de trabalho | **FALTA** — existe `tarsila-limpar.sh`, falta o bind |
| `C-A-Del` → diálogo de sessão | **FALTA** — `tarsila-ob-power.sh` já existe, falta o bind |
| `A-F2` → executar comando | **FALTA** — decidir se um leigo precisa disto |
| `A-F4` → fechar | **OK** |
| `A-Tab` / `S-A-Tab` | **OK**, `NextWindow` nativo |
| Teclas de mídia (volume) | **OK** — 3 binds |
| Play/Pause, Próxima/Anterior | **FALTA** |
| Brilho sem OSD fantasma | **N/A** — não há OSD e a TV não expõe brilho |
| `C-A-Backspace` | **?** decidir e documentar |
| `C-A-F2` (TTY) | **?** testar como resgate |
| `kernel.sysrq=1` | **OK** |
| Sem conflito com o Chromium | **OK** por construção — nenhum bind usa Ctrl |
| Lugar descobrível para ver os atalhos | **FALTA** — com 8 binds, cabe numa tela do Ajustes |

**Super sozinho abrindo o menu** é **N/A**: não há menu de aplicativos. O
equivalente é o ícone "Ver mais" na Dock. Se quiser o bind, aponte para
`tarsila-appfinder-yad.sh`.

## 2. Teclado — acentuação

| Item | Estado |
|---|---|
| `XKBLAYOUT=br`, `pc105` | **OK** — `setxkbmap -query` confirma |
| Cedilha correta | **N/A do jeito escrito** — o `ć` é problema de **US-International**. Com layout `br` o `ç` é tecla própria. `GTK_IM_MODULE` vazio aqui é o certo; defini-lo como `cedilla` seria remendo para um problema que não temos |
| `ç ã õ á à ü` nos apps | **?** teste humano |
| Vírgula decimal no teclado numérico | **?** — mas ver o `LC_NUMERIC=C` nos bloqueadores, que é a causa provável se falhar |
| Numlock no boot | **FALTA** — `numlockx` instalado, não chamado no autostart |
| Repetição de tecla | **OK** — atraso 660 ms, intervalo 40 ms, via `tarsila-entrada-apply.sh` |
| Segundo layout fora do ciclo | **OK** — só existe `br` |
| Indicador de layout | **N/A** — layout único |
| Teclado virtual | **OK** — `onboard` instalado |

## 3. Ponteiro

| Item | Estado |
|---|---|
| Cursor grande para TV | **OK** — `Gtk/CursorThemeSize 32` |
| Tema com todas as formas | **OK** — Adwaita é completo |
| Velocidade calibrada | **OK** — `tarsila-entrada-apply.sh`, ajustável em Ajustes |
| Velocidade de duplo clique | **?** — não há controle exposto; leigo lento merece teste |
| Clique único | **?** decidir |
| Colar com botão do meio | **?** decidir |
| Roda trocando de workspace / no painel | **N/A** — sem área de trabalho reativa e sem painel |
| Botão direito na área de trabalho | **N/A** — não há menu raiz |
| Botões voltar/avançar no Chromium | **?** |
| Canhoto | **FALTA** |
| Controle IR | **?** — a box tem receptor; hoje se usa Logitech Nano |

## 4. Janelas — Openbox, não xfwm4

Toda a seção 4 original falava de `xfwm4`. Traduzida:

| Item | Estado |
|---|---|
| Botões da barra de título | **OK** — `<titleLayout>CML</titleLayout>` |
| Duplo clique = maximizar | **OK** — `ToggleMaximizeFull` nativo desde a remoção da polybar |
| Alt+arrastar move | **?** |
| Encaixe nas bordas | **FALTA** — `screen_edge_strength` é 0 de propósito; decidir se volta |
| Janela nunca nasce fora da tela | **OK** — `conter()` no `floating.lua` |
| Diálogos centralizados no pai | **?** |
| Foco segue clique | **OK** |
| Elevar ao focar | **OK** |
| Compositor ligado ou desligado | **OK, resolvido** — `picom` xrender ligado, e os **cantos arredondados renderizam na Mali-G31**, conferido em captura de tela na box em 16/08 |
| Custo de sombra/transparência medido | **OK** — picom 4,8 MB |
| Número de workspaces | **N/A** — sem paginador, o usuário não os alcança |
| Ciclo de janelas honesto | **OK** |
| Forçar fechamento de app travado | **?** |

## 5. Dock — substitui "Painel e área de trabalho"

A seção original inteira (painel, botões de janela, bandeja, menu de
aplicativos, ícones da área de trabalho) é **N/A**. O que sobrevive:

| Item | Estado |
|---|---|
| Ícones legíveis a 2–3 m | **OK** — a Dock calcula por resolução: 1366x768 → ícone 56, passo 61, dock 1323x74 |
| Relógio com calendário ao clicar | **OK** — ícone da Dock → `tarsila-barra-menu calendario` |
| Formato 24h e data em pt-BR | **FALTA** — `LC_TIME=C` (bloqueador 4) |
| Desligar visível sem entrar em menu | **OK** — ícone próprio na Dock |
| Todo `.desktop` com `Name[pt_BR]` e ícone válido | **?** varredura pendente |
| Nenhum ícone quebrado | **?** |
| Store em local óbvio | **OK** — ícone fixo na Dock |
| Papel de parede na resolução certa, sem esticar | **PARCIAL** — o arquivo certo foi instalado em 16/08 (`8dd7a89`), mas é **1024×572** e sobe 1,33× em 1366x768. Proporção quase idêntica (1,790 contra 1,779), então quase não corta; perde nitidez. Em 1080p vai aparecer. Falta o original em resolução maior |
| Bandeja com ícones de rede/volume/bateria | **N/A** — não existe bandeja e não será criada |

## 6. Arquivos (Thunar)

| Item | Estado |
|---|---|
| Pastas em português no primeiro login | **PARCIAL / divergente** — a box tem `Documentos`, `Downloads`, `Imagens`, mas também `Musicas`, `Videos` e `Pictures`, enquanto o `user-dirs.dirs` da box aponta para `Música` e `Vídeos`, **que não existem**. O `skel/.config/user-dirs.dirs` do **repo** aponta para `Pictures`, `Musicas`, `Videos` e deixa `TEMPLATES` e `PUBLICSHARE` como `$HOME`. Precisa de uma versão só, coerente com pt_BR |
| Miniaturas limitadas | **?** — conferir se `tumbler` está na imagem |
| "Abrir terminal aqui" | **?** |
| Lixeira e como esvaziar | **OK** — ícone próprio na Dock |
| Aviso ao excluir em mídia removível | **?** |
| Progresso honesto ao copiar para pendrive | **?** — teste do roteiro, item 6 |
| F2, Ctrl+A, Ctrl+Z | **?** |
| Ocultos escondidos | **OK** padrão do Thunar |

## 7. Mídia removível

| Item | Estado |
|---|---|
| exFAT e NTFS | **OK** — `exfatprogs` e `ntfs-3g` |
| Automontagem com notificação | **OK** — `udiskie --automount --notify` rodando (45 MB RSS) |
| Abrir o gerenciador ao montar | **OK** — `--file-manager=thunar` |
| Desmontar/ejetar visível | **?** |
| Swap não aparece como montável | **OK** — swap é zram, não cartão |
| Aviso de disco cheio | **FALTA** — hoje 60% de 14 GB |
| `journald` limitado | **OK** — `SystemMaxUse=50M` em drop-in |
| `/tmp` em tmpfs com teto | **OK** — 962 MB, 1% usado |
| Espaço livre visível | **?** — está no `tarsila-barra-menu sistema`; confirmar |

## 8. Áudio

| Item | Estado |
|---|---|
| Saída HDMI por padrão | **OK** — `alsa_output.platform-sound.hdmi-stereo` |
| Volume 60–70% | **OK** — 80%, dentro do razoável |
| Não mudo de fábrica | **OK** |
| TV desligada no boot e o sink volta | **?** teste humano |
| OSD de volume | **?** |
| Som em três fontes | **?** roteiro |
| Sem crackling no PipeWire | **?** |
| Microfone USB | **?** |
| Sons de sistema | **NÃO EXISTEM** — o `tarsila-monitor.sh` anunciava sons de transição no cabeçalho, mas não havia `paplay`/`canberra` no arquivo: o estado era calculado e jogado fora. Descoberto ao remover o daemon, em 17/08/2026 |

Há um sink extra, `tarsila_fone_p2`. Confirmar que ele não rouba o padrão quando
a TV desliga.

## 9. Rede

**Esta box não tem Wi-Fi** — só `eth0`. Os itens de rádio não são testáveis aqui
e ficam pendentes para um aparelho com Wi-Fi.

| Item | Estado |
|---|---|
| Indicador de estado | **OK** — ícone da Dock → `tarsila-barra-menu rede` |
| Domínio regulatório BR | **?** — `iw` não instalado, sem rádio |
| Firmware Wi-Fi na imagem | **?** |
| SSID oculto, mostrar senha, reconexão | **?** |
| Cabo com prioridade | **?** |
| Portal cativo | **OK** de infra — `nmcli` reporta `connectivity: full`, a checagem está ativa |
| `avahi-daemon` | **OK**, ativo |
| Hostname único | **FALTA** — é `tvbox` fixo. Vinte aparelhos na mesma rede colidem. Derivar do `machine-id` no primeiro boot |
| Nenhum app travando sem internet | **?** |

## 10. Bluetooth

| Item | Estado |
|---|---|
| Só sobe se houver adaptador | **OK** — sem adaptador nesta box, serviço `inactive`, zero RAM |
| `blueman` para parear | **OK** instalado |
| Reconexão, A2DP, PIN | **?** — precisa de aparelho com rádio |

## 11. Energia e sessão

| Item | Estado |
|---|---|
| Suspender testado | **OK, resolvido pela raiz** — `/sys/power/state` está **vazio**: o kernel não suporta. E o `tarsila-ob-power.sh` oferece **só Desligar e Reiniciar**. Coerente por acidente feliz; vale um comentário no script para ninguém "consertar" adicionando Suspender |
| Hibernar | **OK** pelo mesmo motivo |
| DPMS numa TV | **PARCIAL** — `xset` instalado em 17/08: DPMS está **habilitado, 600 s**. Confirmado apagando a tela sozinho durante a auditoria. Falta o teste humano: a TV volta? |
| Desligar sem senha | **OK** — `CanPowerOff` e `CanReboot` respondem `yes` |
| Desligamento sem travar | **?** |
| Monta limpo após queda de energia | **PARCIAL** — o cmdline tem `fsck.repair=yes` mas também **`fsck.mode=skip`**, que o anula. Decidir qual fica |
| Ligar ao receber energia | **?** documentar |
| Botão físico de power | **?** |

## 12. Bloqueio e login

| Item | Estado |
|---|---|
| Perfil comunidade sem bloqueio | **OK** — nenhum bloqueador instalado (`xscreensaver`, `light-locker`, `xss-lock` ausentes). O usuário não tem como se trancar fora |
| Autologin | **OK** — `99-tarsila-autologin.conf`, `tarsila`, timeout 0 |
| LightDM com identidade Tarsila | **N/A na prática** — com autologin a tela não aparece. Continua valendo para o perfil escritório |
| Usuário e senha documentados | **?** |
| Recuperação por frase BIP39 | **?** — projeto separado |

Há uma fricção real no login: o `nc-mount.py` do Nextcloud dispara um pedido de
senha do chaveiro em toda sessão (`Digite a senha para "Nextcloud"` no
`.xsession-errors`). Num aparelho com autologin, isso é um diálogo de senha na
cara de quem só queria ligar a TV.

## 13. Notificações

| Item | Estado |
|---|---|
| Posição e tempo definidos | **OK** — `dunst`, `top-center`, offset `0x46`, timeouts 6/8/0 |
| Não empilhar no boot | **?** |
| Não perturbe | **FALTA** |
| Notificações úteis | **OK** — pendrive, instalação concluída, dispositivos |
| Nada em inglês | **?** varredura |

> A posição `top-center` é herança da polybar, que ocupava o topo. Com a Dock
> embaixo e o topo livre, reavaliar: pode ir para junto da Dock, onde o olho já
> está.

## 14. Aparência e a TV

| Item | Estado |
|---|---|
| Overscan | **?** teste humano — a captura de 16/08 não mostra corte, mas depende da TV |
| Resolução detectada | **OK** — 1366x768, HDMI-A-1 `connected` |
| Fallback com a TV desligada no boot | **FALTA** — sem `video=HDMI-A-1:...` no cmdline. Sem EDID o modo cai para o mínimo |
| Perfil de vídeo persistente | **PARCIAL** — `tarsila-resolucao-apply.sh` existe mas **depende de `xrandr`, ausente nesta box**, então é um no-op |
| Escala de texto | **?** — hoje `Inter 11` |
| Fontes com antialiasing | **OK** — `fonts-dejavu` e a família Inter/Noto |
| Emoji | **OK** — `fonts-noto-color-emoji` |
| Temas combinando | **OK** — Tarsila + Tarsila-icons via `xsettingsd` |
| Escuro/claro com troca fácil | **OK** — `~/.config/tarsila/tema`, dois temas |
| Ícones faltando | **?** varredura |
| Barra de rolagem larga | **FALTA** |

### A nota do `x11-xserver-utils` — RESOLVIDO em 17/08

`xrandr` e `xset` não estavam nesta box, e os dois vêm do mesmo pacote. Isso
derrubava três itens de uma vez: DPMS, o `tarsila-resolucao-apply.sh` e o
`altura_tela()` do `comum.sh`, que caía no fallback 768 — correto aqui **por
coincidência**, errado em qualquer TV 1080p.

Nunca foi defeito do repositório: o `install.sh` **já instalava
`x11-xserver-utils`**. Era dívida desta box, montada em 21/07, antes de a linha
existir. Instalado em 17/08 e conferido:

- `xrandr --query` → `current 1366 x 768, maximum 3840 x 2160`
- `altura_tela()` → **768**, agora medido em vez de chutado
- `xset q` → **DPMS habilitado, Standby/Suspend/Off em 600 s**

O DPMS estava ativo o tempo todo sem ninguém poder consultá-lo. No momento da
verificação o `xset` reportava `Monitor is Off` — a TV tinha apagado sozinha
aos 10 minutos. É exatamente o risco que o checklist original levantou: numa TV,
DPMS pode virar "sem sinal" e não voltar. Agora dá para medir e decidir; segue
como teste humano.

## 15. Aplicativos padrão — RESOLVIDO

Era o bloqueador 1, e eram dois defeitos somados — o detalhe está no início
desta página. Estado depois da correção, verificado abrindo arquivo de verdade
e olhando qual processo nasceu:

| Tipo | Abre em | Prova |
|---|---|---|
| `image/png`, `jpeg`, `gif`, `bmp`, `svg`, `webp`, `tiff` | `gpicview` | janela `gpicview.Gpicview` |
| `text/plain`, `markdown`, `python3`, `.sh`, `.desktop` | `l3afpad` | janela `l3afpad.L3afpad` |
| `application/pdf` | `qpdfview` | — |
| `video/mp4`, `mkv`, `webm`, `audio/mpeg`, `ogg`, `flac` | `mpv` | — |
| `application/zip`, `rar`, `7z`, `tar`, `gz`, `bz2`, `xz` | `xarchiver` | — |
| `http`, `https`, `mailto` | `tarsila-chromium` | — |

As duas seções do arquivo agora concordam item a item. A regra ficou escrita no
próprio `mimeapps.list` e no `install.sh`: **um tipo que apareça só em
`[Added Associations]` cai na escolha automática do sistema**, que foi metade
do defeito original.

| Item | Estado |
|---|---|
| Duplo clique nunca cai em "Escolha um aplicativo" | **OK** |
| `xdg-open` do terminal e de dentro do Chromium | **OK** — dependia do pacote `file`, ver bloqueador 1 |
| Visualizador de PDF leve | **OK** — `qpdfview` |
| Compactador com backends | **OK** — `p7zip-full` e `unar` acrescentados ao `install.sh`; sem eles o `xarchiver` abre a janela e falha em 7z e rar |
| Editor de texto simples | **OK** — `l3afpad` |
| `mailto:` abre o Tarsila Mail | **FALTA** — ainda vai para o Chromium |
| Link abre na janela existente do Chromium | **OK** — `tarsila-uma-janela` |
| Remover app pela Store não deixa associação órfã | **FALTA** — mesma família do defeito corrigido: nada valida que o alvo existe |

## 16. Área de transferência

**RESOLVIDO em 17/08** com o `qlipper` — ver o bloqueador 2 no início, que traz
a tabela do teste e o motivo de cada descarte.

| Item | Estado |
|---|---|
| Copiar, fechar o app, colar | **OK** — testado com o dono da seleção morto |
| Histórico com tamanho limitado | **OK** — o `qlipper` limita por padrão |
| Atalho para abrir o histórico | **PARCIAL** — o `qlipper` traz um atalho próprio, mas o ícone dele iria para a bandeja, **que não existe**. O caminho coerente aqui é um ícone na Dock |
| Copiar entre Chromium ↔ GTK ↔ terminal | **?** teste humano |

## 17. Chromium

| Item | Estado |
|---|---|
| Sem assistente de boas-vindas | **OK** — `--no-first-run`, `--no-default-browser-check` |
| Sem telemetria | **OK** — `--metrics-recording-only`, `--disable-breakpad`, `--disable-domain-reliability` |
| Aviso de flags suprimido | **OK** — política `CommandLineFlagSecurityWarningsEnabled: false` |
| Bloqueador de anúncios | **PARCIAL** — há `--load-extension`, mas `/etc/hosts` tem **33 linhas**: a blocklist do StevenBlack **não está aplicada** |
| Zoom para TV | **?** |
| Flags revisadas depois do Panfrost | **OK — GPU ligada, verificado** (ver abaixo) |
| "Restaurar páginas?" após OOM | **?** |
| Aviso na 10ª aba | **FALTA** |
| Keyring sem senha extra | **FALTA** — ver a fricção do Nextcloud em §12 |
| Downloads em `~/Downloads` | **OK** |
| Imprimir do navegador | **?** roteiro |
| Limitar resolução do YouTube | **?** — reavaliar: com GPU o cálculo muda |

### A GPU do Chromium está ligada — e as flags não são contraditórias

Correção de um relato meu anterior. Eu havia dito que o launcher tinha
`--disable-gpu` convivendo com `--ignore-gpu-blocklist` e `--use-angle`. Não
tem: aquilo foi um `grep` no arquivo inteiro, que **achatou os ramos de um
`if/elif`** e mostrou lado a lado flags que nunca coexistem. O
`--disable-gpu` só aparece em dois ramos que se excluem dos outros —
`TARSILA_GPU=0`, ou nenhum servidor gráfico detectado.

Verificado sem abrir o navegador na tela: o launcher resolve `chromium` pelo
PATH, então basta pôr um dublê na frente que imprime os argumentos. As flags
efetivas na box são

```
--ozone-platform=x11
--use-angle=gles
--ignore-gpu-blocklist
--enable-features=…,VaapiVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxGL,…
```

34 flags no total, **nenhuma delas `--disable-gpu`**. `TARSILA_GPU=1` vem do
`environment` e não há `~/.config/tarsila/gpu` sobrescrevendo; `TARSILA_HWDEC`
também está no padrão 1. O caminho está correto e nada precisa mudar.

O que continua **não** verificado é o efeito: `chrome://gpu` dizendo
"Video Decode: Hardware accelerated" só se confere com o navegador aberto na
TV. As flags estão certas; o resultado é teste humano.

## 18. Terminal

`xfce4-terminal` instalado. Reclama `SESSION_MANAGER environment variable not
defined` em toda abertura — inofensivo, mas é ruído no log.

| Item | Estado |
|---|---|
| Fonte legível com acentos | **?** |
| Rolagem limitada | **?** |
| Ctrl+Shift+C/V | **?** |
| `PS1` e `LS_COLORS` | **?** |
| `sudo` em português | **?** |
| MOTD enxuto | **OK** — o banner é `Tarsila OS 1.0 (tester)`, sem lixo do Debian |

## 19. Impressão

| Item | Estado |
|---|---|
| CUPS + avahi | **OK** — os dois ativos |
| Driverless | **OK** — `cups-filters` |
| HP | **OK** — `hplip` |
| Diálogo em português | **?** |
| Fila cancelável | **?** |
| Scanner | **OK** — `simple-scan` + `sane-utils` |
| Peso parado | **FALTA medir** — CUPS e Avahi ativos o tempo todo num aparelho de 2 GB. Candidatos a socket-activation |

## 20. Primeiro boot

| Item | Estado |
|---|---|
| Boot silencioso | **OK** — `quiet splash loglevel=0 vt.global_cursor_default=0 systemd.show_status=false udev.log_level=0` |
| Sem erro de kernel na tela | **OK** pelo mesmo cmdline |
| Assistente de primeiro uso | **FALTA** |
| Expansão da partição | **?** — 14 GB de 16, parece expandido |
| `machine-id` único | **OK** — existe e é próprio; falta **derivar o hostname dele** (§9) |
| Frase BIP39 confirmada | **FALTA** |
| Tour de 6 telas | **FALTA** |
| Tempo de boot medido | **FALTA** — `systemd-analyze` é uma linha |

## 21. Hora e localização — bloqueador nº 2

| Item | Estado |
|---|---|
| `fake-hwclock` | **OK** instalado |
| NTP ativo | **OK** — `systemd-timesyncd` `active`, `NTP service: active` |
| **Relógio certo** | **RESOLVIDO na box** — acertado em 17/08 e salvo com `fake-hwclock save`. A causa não era o Tarsila: a box **não tem internet** neste laboratório. Ver o bloqueador 3 |
| Fuso | **OK** — `America/Sao_Paulo` |
| `LANG=pt_BR.UTF-8` | **OK** |
| **`LC_TIME`, `LC_NUMERIC`, `LC_MONETARY`** | **FALTA** — os três em **`C`**. Data americana, ponto decimal, moeda errada. É o bloqueador 4 |
| Semana no domingo | **?** — depende do `LC_TIME` acima |
| Pacotes de tradução | **?** |
| Nenhuma string em inglês no fluxo comum | **?** varredura |

O relógio é o item que o checklist original acertou em cheio: o sintoma
(HTTPS falhando, `apt` recusando repositório) nunca é atribuído ao relógio. E a
investigação mostrou por que ele é traiçoeiro — o `timesyncd` estava ativo, com
servidor selecionado, e o DNS respondia. Tudo parecia saudável. Só um teste que
**mandou um pacote NTP de verdade** mostrou que nada saía da box.

Lição para as próximas: DNS respondendo não prova internet quando o resolvedor
é local, e abrir um socket UDP não prova alcance nenhum — o primeiro teste que
fiz aqui foi `/dev/udp`, que só abre o socket e sempre "funciona".

## 22. Hardware Amlogic

| Item | Estado |
|---|---|
| **Governor da GPU em `performance`** | **OK** — lendo `fe400000.gpu/governor` agora |
| **Persistente** | **OK, resolvido** — há `99-tarsila-gpu-governor.rules`, `99-tarsila-devfreq.rules`, `tarsila-devfreq-gpu.service` e o binário `tarsila-devfreq-gpu`. Deixou de ser trabalho manual |
| Sem `cpufreq` | **OK, confirmado** — `/sys/devices/system/cpu/cpu0/cpufreq/` não existe. Sem DVFS e sem throttling por frequência, como suspeitado |
| Temperatura monitorada | **PARCIAL** — `thermal_zone0` existe e marca **44,5 °C** em repouso. Falta expor e falta decidir o limite |
| zRAM ativo | **OK** — `/dev/zram0`, 1,44 GB, prioridade 10, 0 em uso |
| `earlyoom` ativo | **OK** |
| OOM com aviso em português | **?** |
| LED do aparelho | **?** |
| Firmware Wi-Fi/BT | **N/A** nesta box, sem rádio |
| Portas USB com hub | **?** |

### Memória: o que o `devilspie2` faz e quanto custa

Correção de medida: eu havia citado **73 MB de RSS** para o `devilspie2`. RSS
conta bibliotecas compartilhadas inteiras em cada processo que as usa, então
superestima. Por **PSS**, que divide o compartilhado entre quem usa, o quadro é
outro e ninguém destoa tanto:

| | RSS | PSS |
|---|---:|---:|
| `python3` (a Dock) | 61 MB | **37 MB** |
| `devilspie2` | 71 MB | **36 MB** |
| `udiskie` | 44 MB | 25 MB |
| `openbox` | 20 MB | 9 MB |
| `wireplumber` | 17 MB | 8 MB |

Soma de PSS da sessão: **173 MB** antes das mudanças de hoje, **206 MB**
depois — os 19 MB do `qlipper` mais o diálogo do chaveiro que está aberto na
tela. `free` reporta 436 MB usados de 1922.

**O que o `devilspie2` gerencia hoje** (`skel/.config/devilspie2/floating.lua`,
67 linhas, e a maior parte é comentário): roda uma vez a cada janela nova e faz
só três coisas.

1. Ignora janelas de sistema e as do próprio Tarsila (`Yad`,
   `Tarsila-dock-manager`, `Tarsila-deb-gui`).
2. `unmaximize()` — nenhuma janela nasce maximizada.
3. `conter()` — se a janela nasceu grande demais, encolhe. Diálogo acima de
   75%×80% da área útil vai para 60%×70% e é centralizado; janela normal acima
   de 90%×90% vai para 70%×75%, sem centralizar. Janelas cuja classe começa com
   `tarsila` ficam de fora.

Não há posicionamento forçado — o arquivo diz explicitamente para não
reintroduzir os "slots"/cascata removidos em 19/07. **Não** é ele quem cuida do
nascimento das janelas com vaga e vetor: isso é o `tarsila-abrindo` com
`tarsila_vaga`/`tarsila_vetor`.

Duas dívidas ali: a lista `SYSTEM_CLASSES` ainda cita `Plank`,
`Tarsila-tela-estados` e `Xfce4-panel`, **três coisas que não existem mais**, e
não cita a classe atual da Dock. Como a Dock é `WINDOW_TYPE_DOCK`, nenhum dos
dois ramos de `conter()` a alcança e não há dano hoje — mas o `unmaximize()` da
linha 31 roda nela à toa. Vale limpar.

Se a meta de 200 MB voltar à mesa, 36 MB de PSS para "desmaximizar e encolher
janela grande" é caro em comparação com o que entrega. As duas regras cabem no
`tarsila-estado.sh`, que já observa o X por evento e já custa zero parado.
Nenhuma das duas precisa de Lua nem de libwnck.

## 23. Manutenção

| Item | Estado |
|---|---|
| Atualização sob demanda | **?** decidir |
| Nunca durante videochamada | **?** |
| App de manutenção | **PARCIAL** — `tarsila-barra-menu sistema` e `diagnostico-rapido` existem |
| Botão de suporte remoto | **?** |
| ID de sessão legível | **?** |
| Rollback | **FALTA** |

## 24. Acessibilidade

| Item | Estado |
|---|---|
| Escala de texto em 2 cliques | **?** |
| Alto contraste | **FALTA** |
| Lupa | **FALTA** — nem `xzoom` nem `magnus` |
| Sticky keys desligadas | **OK** — decisão já tomada e documentada no autostart |
| Navegação por teclado | **?** |

Nota: `NO_AT_BRIDGE=1` no `environment` desliga o barramento de acessibilidade.
Está certo hoje (o `at-spi2-core` nem está instalado), mas é o que barra um
leitor de tela no futuro. Já está documentado no próprio arquivo.

## 25. Identidade

| Item | Estado |
|---|---|
| Nada de "Debian" visível | **OK** — `/etc/os-release` diz `Tarsila OS 1.0 (tester)`, `ID=tarsila` |
| `/etc/tarsila-release` | **OK** — versão, data de build e alvo |
| **`TARSILA_DE="xfce"`** | **FALTA** — está desatualizado, hoje é Openbox |
| Ícone e nome em cada app | **?** |
| Diálogo "Sobre o Tarsila" | **?** |
| Nenhum app de exemplo sobrando | **?** — a `$HOME` desta box tem `print.png`, `imagem_ssh*.png`, `omniclone.py`, backups. É a box de desenvolvimento, mas **conferir que o `skel` está limpo** |
| Papel de parede consistente entre skel e usuário | **OK desde `8dd7a89`** — antes o arquivo "padrão" era byte a byte igual ao tema escuro |

---

## Roteiro de aceitação — adaptado

Quinze minutos, num aparelho recém-flashado. Os passos 5 e 7 do roteiro antigo
mudaram de resposta esperada por causa dos bloqueadores.

1. Ligar com a TV **desligada**, ligar a TV 30 s depois. Tem imagem? Tem som?
2. Conferir o relógio. **Hoje falha.**
3. Chromium: conta Google e um vídeo do YouTube.
4. `Print`. Achou em `~/Imagens`? Abriu com duplo clique? **Hoje abre no
   ImageMagick.**
5. Pendrive NTFS: montou, copiou 500 MB com barra honesta, ejetou?
6. Copiar texto, **fechar o app**, colar em outro. **Hoje falha.**
7. Digitar "informação, açúcar, avaliação" em três apps.
8. Imprimir numa impressora de rede sem digitar IP.
9. Dez minutos parado: a tela volta?
10. Oito abas + 2 apps até estressar a RAM. O que acontece é compreensível?
11. Desligar pelo menu, ligar de novo: o governor ainda está em `performance`?
    **Hoje passa** — há persistência por udev e service.
12. Abrir um `.txt`, um `.png` e um `.pdf` pelo Thunar. Os três no app certo?
    **Hoje dois de três falham.**

---

## O que saiu da lista original, e por quê

| Removido | Motivo |
|---|---|
| §5 inteira: painel, altura, botões de janela, agrupar, menu de aplicativos, ícones na área de trabalho | Não há painel nem menu nem área de trabalho clicável. A Dock cobre o papel |
| Bandeja do sistema, em §5, §9, §10, §16 | Não existe `_NET_SYSTEM_TRAY_S0` nesta sessão e a decisão foi não recriar. OBS e VLC voltam pelo ícone da Dock |
| Todos os itens `xfwm4` | O gerenciador é Openbox |
| `xfrun4`, `xfce4-screenshooter` | Não instalados; `scrot` faz a captura |
| "Super abre o menu de aplicativos" | Não há menu; o equivalente é o "Ver mais" da Dock |
| Workspaces, paginador, roda do mouse trocando de espaço | Sem paginador, o usuário não os alcança |
| Cedilha via `GTK_IM_MODULE` | Problema de US-International; com layout `br` o `ç` é tecla própria |
| Suspender e hibernar | O kernel não suporta e o menu não oferece. Resolvido pela raiz |
| Indicador de layout de teclado | Layout único |
| Brilho / OSD fantasma | A TV não expõe controle de brilho |

## Como conferir de novo

```
bash docs/conferir-ux.sh              # na própria box
```

Somente leitura: não instala, não escreve, não muda configuração. Foi ele que
produziu as evidências desta página. Para rodar de fora:

```
scp docs/conferir-ux.sh tarsila@10.42.0.106:/tmp/
ssh tarsila@10.42.0.106 'DISPLAY=:0 bash /tmp/conferir-ux.sh'
```

Regra que vale para tudo aqui: **item resolvido vira arquivo no repositório**,
não configuração aplicada à mão na box. Senão o próximo flash perde.

O que mudou no repositório em 17/08:

| Arquivo | Mudança |
|---|---|
| `skel/.config/mimeapps.list` | reescrito: alvos que existem, as duas seções concordando, webp e mais tipos cobertos |
| `install.sh` | `+file`, `+shared-mime-info`, `+desktop-file-utils`, `+qlipper`, `+xclip`, `+gpicview`, `+l3afpad`, `+webp-pixbuf-loader`, `+mpv`, `+xarchiver`, `+p7zip-full`, `+unar`; **`-plank`**, que já não é usado |
| `openbox/deploy/home/openbox/autostart` | `clipit`/`parcellite` → `qlipper`, com o registro do teste que decidiu |
| `docs/conferir-ux.sh` | consulta o locale com `env -u LC_ALL`, para não repetir o eco da própria contaminação |

E os dois lados da moeda continuam valendo como exemplo: o defeito do
`mimeapps` estava **no repositório** e ia junto em toda instalação nova; o do
`x11-xserver-utils` já estava certo no repositório e era dívida só desta box.
Vale perguntar de qual tipo é cada item antes de sair corrigindo.
