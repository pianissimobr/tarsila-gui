# Diagnóstico de `/usr/local/bin` — 17/08/2026

Levantamento dos 54 scripts `tarsila-*` instalados na box de teste
(`alan@10.42.0.106`, Openbox, sessão de pé há 3 h). Três perguntas:

1. o que cada script **é** de fato;
2. quem ainda cita **Plank** ou **polybar**, e se a citação é código vivo ou história;
3. quais scripts **não conversam com ninguém** — não são chamados, ou chamam algo que
   não existe mais.

## Como foi levantado, e o que não acreditar

Um script de auditoria só de leitura varreu, para cada arquivo: interpretador, tamanho,
citações a `plank|polybar|xfce`, quem o referencia (`/usr/local/{bin,lib,share}`, `/opt`,
`/usr/share/tarsila`, `/usr/share/applications`, `/etc/{skel,xdg,systemd,sudoers.d,lightdm}`,
`~/.config`) e quais caminhos absolutos citados não existem no disco.

Duas armadilhas do próprio método, para quem repetir:

- **A varredura de "quem chama" acha backup.** `/usr/local/share/tarsila/` guarda pastas
  `polybar/`, `polybar-shape/`, `bandeja-segundoplano/` e `backup-2026*` cheias de cópias
  antigas, e `~/.config/openbox/` tem três `autostart.bak-*`. O `tarsila-tela-estados`
  aparece com 29 referências e **nenhuma viva**. Conte só o que a sessão lê.
- **`XDG_RUNTIME_DIR` aqui é `/run/user/1003`, não `/run/user/1000`.** O usuário `alan`
  tem uid 1003. Na primeira passada meia dúzia de arquivos de estado foi dada como
  inexistente por causa disso — todos existem.

## Placar

| | |
|---|---|
| Scripts em `/usr/local/bin` | 54 (+ `yt-dlp`) |
| Vivos e corretos | 38 |
| Vivos com trecho morto dentro | 6 |
| **Quebrados** (rodam, mas o que fazem não acontece) | **4** |
| **Órfãos** (ninguém chama) | **4** |
| Duplicatas byte a byte | 2 pares |

Citam Plank ou polybar: **17 arquivos**. Em 9 é só comentário histórico — e comentário
histórico aqui é patrimônio, não sujeira: explica por que o código tem a forma que tem.
Em **8** é código executado.

---

## Os defeitos, por impacto

### 1. O cursor de relógio dura 32 s em todo boot

`tarsila-boot-cursor.sh` põe o cursor de espera e roda 60 ciclos de 0,5 s esperando o
sinal de "a área de trabalho está pronta". O sinal é:

```bash
if pgrep -u "$USER" -x plank >/dev/null 2>&1; then break; fi
```

Não há Plank desde 16/08. A condição nunca é satisfeita, o laço gasta os 60 ciclos
inteiros e o usuário vê a ampulheta por ~32 s depois de a tela já estar pronta.

O mais instrutivo: **o comentário logo acima descreve esse mesmo bug**, na versão de
15/08, quando a condição exigia também um `xfce4-panel`. Consertou-se tirando o
`xfce4-panel` e deixando o Plank — que morreu no dia seguinte. A condição certa não é o
nome de um processo, é a janela existir: `xdotool search --class tarsila-dock`.

### 2. O vetor de abertura não tem mais quem o desenhe

`tarsila_vetor.acende()` escreve a vaga em `$XDG_RUNTIME_DIR/tarsila-vetor.txt` e, nas
palavras do próprio arquivo, *"quem desenha é o tarsila-tela-estados"*.

O `tarsila-tela-estados` (1293 linhas) **não é iniciado por ninguém**. Some do
`~/.config/openbox/autostart` — sobrou uma menção num comentário — e não está de pé.
O arquivo de runtime existe, vazio, com escrita recente: alguém acende, ninguém pinta.

O plano de remoção da polybar dizia, textualmente, "preservado sem mudança: o vetor de
abertura". Ele não foi preservado; foi desligado junto com a janela que o hospedava.
É a perda funcional mais silenciosa do lote — nada dá erro, o efeito visual apenas não
acontece.

### 3. O contador de janelas conta a própria mobília

`tarsila-monitor.sh` pula as janelas do sistema por nome de classe:

```bash
case "$wmclass" in *[Pp]lank*|*xfce4-panel*|*xfdesktop*|"") continue ;;
```

Os três estão mortos; os dois vivos — `tarsila-dock` e `tarsila-barra` — não estão na
lista. Medido com **zero aplicativos abertos**: `tarsila-wincount` = **3** (barra, Dock e
a janela do daemon do Thunar). O estado "área de trabalho vazia" nunca ocorre.

É o mesmo defeito que a varinha "Limpar" tinha e que já foi corrigido: filtrar por
`_NET_WM_WINDOW_TYPE` (`DOCK`/`DESKTOP`) em vez de por nome.

Dois achados de tabela junto:

- a variável `state` (1 vazio / 2 flutuante / 3 maximizado) é calculada a cada ciclo e
  **nunca usada**. O cabeçalho anuncia "SOM: toca um som nas transições" — não há
  `paplay`, `canberra` nem `.oga` no arquivo. A responsabilidade número 2 do daemon não
  existe mais;
- o único leitor de `tarsila-wincount` no disco é
  `/usr/local/bin/__pycache__/tarsila-topbar-dots.cpython-313.pyc` — bytecode de um
  script apagado.

### 4. As janelas que "nascem junto da Dock" não acham a Dock

`tarsila-pos-dock` é o cálculo compartilhado de onde uma janela deve nascer para encostar
na Dock. Ele procura `xdotool search --class plank`, e quando acha tira uma **captura de
tela da Dock** (`import -window`) e varre os pixels com PIL para achar onde a pintura
termina.

Sem Plank, a busca volta vazia e a função devolve `None` **sempre**. Quem chama —
`tarsila-lixeira` e o fallback do `tarsila-barra-menu` — cai no plano B e abre no lugar
aproximado. O trabalho caro (captura + PIL) nunca chega a rodar; o barato (achar a
janela) é o que falha.

`tarsila-appfinder-yad.sh` tem uma **segunda cópia** da mesma rotina, inline, com o mesmo
defeito — a divergência já anotada no plano de remoção da polybar, agora com as duas
metades igualmente quebradas.

A Dock nova é `--class tarsila-dock` e tem largura própria; o `topo_da_dock()` do
`tarsila-barra-menu` já foi corrigido para isso em 17/08 e serve de modelo.

### 5. Trocar o tema não muda mais a cor da Dock

Três scripts escrevem nove chaves em `/net/launchpad/plank/docks/dock1/`
(`theme`, `position`, `hide-mode`, `pressure-reveal`, `hide-delay`, `unhide-delay`,
`icon-size`, `pinned-only`, `lock-items`). A Dock em GTK **não lê dconf**: a cor é
`FUNDO = (21/255, 17/255, 40/255)` no código e o tamanho do ícone vem da altura da tela.

Só `dock-items` ainda tem leitor — o `tarsila-dock-manager`, para mostrar a ordem atual.
A própria Dock ordena pelo nome do arquivo, então essa chave é uma cópia paralela que
pode discordar da realidade.

Consequência visível hoje: o tema salvo é `padrao` (claro), a barra de cima está clara
e obedecendo, e a Dock continua azul-escura. O `tarsila-estado.sh` também escreve
`hide-mode='dodge-maximized'` a cada troca de estado, para um Plank que não existe — a
Dock some ao maximizar por conta própria, lendo `tarsila-topbar-state.txt`.

### 6. Um usuário novo cai no mundo antigo

`/etc/skel/.config/` ainda tem `polybar/` (9 scripts: `title.sh`, `dots.sh`, `net.sh`,
`sound.sh`, `power.sh`…), `plank/`, `xfce4/`, e um `openbox/autostart` que sobe
`plank`, `polybar`, `tarsila-tela-estados` e `tarsila-ob-decor.sh` — este último apagado
do disco. Nenhuma linha sobe a Dock nova ou a barra.

O provisionamento oficial (`/usr/local/sbin/tarsila-user-provision`) não usa `/etc/skel`:
copia de `/usr/share/tarsila/skel`, **que não existe nesta box** — o `install.sh` do
repositório é quem a cria, e não foi rodado aqui desde então. Ou seja: hoje, nesta
imagem, quem criar um usuário pelo `adduser` comum recebe a sessão de duas versões atrás.
No repositório o caminho está correto; o defeito é da imagem.

De quebra, o `skel/` do repositório ainda leva `.config/autostart/plank.desktop`
(`sh -c "tarsila-dock-apply.sh; exec plank"`) e um `plank-dconf.ini` que o `install.sh`
carrega no dconf.

### 7. O autostart XDG inteiro é inerte

`openbox-autostart` termina em `exec openbox-xdg-autostart`, que morre em:

```
ERROR: openbox-xdg-autostart requires PyXDG to be installed
```

`python3-xdg` não está instalado. Portanto **nada** em `~/.config/autostart` (9 entradas)
nem em `/etc/xdg/autostart` (13) roda. A sessão funciona porque
`~/.config/openbox/autostart` sobe à mão o que importa (picom, dunst, devilspie2,
qlipper, lxpolkit, monitor, wallpaper…).

Fica sem rodar, sem que ninguém tenha decidido isso: `xdg-user-dirs-update`,
o daemon do Thunar, `blueman-applet` (pareamento de Bluetooth), `onboard` (teclado na
tela) e `nextcloud-mount.desktop` — este último aponta para
`~/.local/bin/nc-mount-and-link.sh`, enquanto o autostart do Openbox roda um
`nc-mount.py` diferente.

Isso é uma escolha a fazer, não um bug a corrigir: ou instala-se o `python3-xdg` e as 22
entradas passam a valer (com risco de duplicar o que o autostart já sobe), ou apaga-se o
que é inerte e assume-se o `~/.config/openbox/autostart` como fonte única. **A segunda é
a que combina com o resto do sistema**, e é a que eu recomendo — mas as quatro coisas
úteis acima precisam migrar para lá antes.

### 8. Restos do ritual do Plank

`tarsila-app-uninstall.sh`, ao remover o ícone do aplicativo desinstalado:

```bash
pkill -x plank; sleep 0.5; rm -f "$item"; tarsila-dock-apply.sh; nohup plank &
```

O `pkill` não acha nada, o `sleep` atrasa meio segundo à toa e o `nohup plank` subiria um
Plank intruso se o pacote voltasse. O `restart_plank()` do `tarsila-appfinder-yad.sh` faz
o mesmo, mas é protegido por `command -v plank || return 0` — inerte, não perigoso.
Desinstalar **funciona**, porque a Dock passou a observar a pasta desde 17/08. Foi esse
mesmo bloco que já saiu do `tarsila-dock-item.sh` e do `tarsila-dock-manager`.

### 9. Órfãos

| Script | Situação |
|---|---|
| `tarsila-tela-estados` (1293 linhas) | Ninguém sobe. Ver defeito 2 — vai junto com o vetor. |
| `tarsila-ajusta-janela` (47) | Ferramenta manual de acerto de encaixe. Mede o topo da Dock com `xdotool search --class plank`, então imprime vão vazio. |
| `tarsila-machine-id-check` (9) | Não é chamado por nada — nem unit, nem OOBE. E a lógica não faz o que o comentário diz: só age se `/etc/machine-id` estiver **vazio**, enquanto imagem clonada tem id **duplicado e não vazio**. Nunca protegeu de nada. |
| `tarsila-perfil`, `tarsila-wifi`, `tarsila-net-set` | **Não são órfãos** — a primeira varredura errou. São chamados pelo painel de Ajustes (`/usr/local/share/tarsila/tarsila_config.py`) via `sudo -n`, pasta que não estava na lista de busca. |

### 10. Duplicatas byte a byte

`tarsila-tema-apply.sh` ≡ `tarsila-ob-tema-apply.sh` e
`tarsila-wallpaper-apply.sh` ≡ `tarsila-ob-wallpaper-apply.sh` (`diff` vazio). As versões
`-ob-` não são chamadas por ninguém: as únicas ocorrências do nome estão nos comentários
das gêmeas. Herança do tempo em que XFCE e Openbox coexistiam.

### 11. Duas listas de classes envelhecidas — sem dano observado

Registro para não serem "descobertas" de novo como se fossem graves:

- `~/.config/devilspie2/floating.lua`: `SYSTEM_CLASSES = { Xfdesktop, Xfce4-panel, Plank,
  Tarsila-tela-estados }` — os quatro mortos, e faltam `Tarsila-dock`/`Tarsila-barra`. A
  guarda não guarda mais nada, mas o dano é um `unmaximize()` desperdiçado por janela:
  o tipo `DOCK` não entra em nenhum dos dois ramos seguintes.
- `tarsila_vaga.py`: `FORA_DO_SISTEMA` também lista `plank` e `tarsila-tela-estados` sem
  os dois vivos. **Testado**: com zero aplicativos abertos, `tarsila-vaga.py 800 600`
  responde `25 49 1` — a vaga 1, correta. Não houve dano porque a ocupação é decidida
  por proximidade de geometria (10 px), e nem a barra nem a Dock caem sobre uma vaga.

### 12. Lixo de bytecode

`/usr/local/bin/__pycache__/` guarda `.pyc` de três scripts que não existem mais:
`tarsila-polybar-hitboxes`, `tarsila-topbar-dots` e `tarsila-tela-estados`. Inofensivo,
mas é o que faz uma busca por "quem lê o wincount" responder errado.

---

## Inventário

Legenda: **✓** vivo e correto · **~** vivo com trecho morto · **✗** quebrado · **○** órfão

### Sessão e área de trabalho

| Script | O que é | Chamado por | |
|---|---|---|---|
| `tarsila-ob-session` | Define o ambiente e entrega ao `openbox-session` | `/usr/share/xsessions` | ✓ |
| `tarsila-dock` | A Dock (GTK+Cairo). Observa a pasta de lançadores e o estado da tela | autostart | ✓ |
| `tarsila-barra` | Barra de indicadores do topo (GTK), sempre por cima | autostart | ✓ |
| `tarsila-barra-menu` | Os quatro popups: som, rede, calendário, sistema | `tarsila-barra` | ✓ |
| `tarsila-estado.sh` | Fonte de verdade de "há janela maximizada?", por `xprop -spy` | autostart | ~ |
| `tarsila-monitor.sh` | Daemon único: contagem, título amigável, renice | autostart | ✗ |
| `tarsila-limpar.sh` | A varinha: fecha tudo, poupando `DOCK`/`DESKTOP` | `tarsila-barra` | ✓ |
| `tarsila-ob-power.sh` | Menu Desligar/Reiniciar/Sair (yad) | `tarsila-barra` | ✓ |
| `tarsila-dialogos` | Tamanho e lugar dos diálogos Abrir/Salvar do GTK3 | autostart | ✓ |
| `tarsila-dispositivos` | Aviso de dispositivo conectado, em duas etapas | autostart | ✓ |
| `tarsila-descanso-vigia` | Vigia de ociosidade (`xprintidle`, 20 s) | autostart | ✓ |
| `tarsila-descanso` | Modo de espera: vídeo em loop com a hora | `descanso-vigia` | ✓ |
| `tarsila-ob-picom.sh` | Sobe o picom em xrender (GLX congela esta GPU) | autostart | ✓ |
| `tarsila-boot-cursor.sh` | Cursor de espera enquanto a sessão sobe | autostart | ✗ |
| `tarsila-tela-estados` | Botão, fundo e vetor da era polybar | — | ○ |

### Aparência e ajustes

| Script | O que é | Chamado por | |
|---|---|---|---|
| `tarsila-wallpaper-apply.sh` | Pinta o papel de parede e calcula `icon-size` | autostart, `resolucao-apply` | ~ |
| `tarsila-tema-apply.sh` | Aplica o tema escolhido | painel de Ajustes | ~ |
| `tarsila-ob-wallpaper-apply.sh` | Cópia idêntica da de cima | — | ○ |
| `tarsila-ob-tema-apply.sh` | Cópia idêntica da de cima | — | ○ |
| `tarsila-resolucao-apply.sh` | Reaplica a resolução, só se o modo existir | autostart | ✓ |
| `tarsila-entrada-apply.sh` | Teclado e mouse (o que o `xfsettingsd` fazia) | autostart | ✓ |
| `tarsila-perfil` | Nome e foto do perfil, via `sudo -n` | painel de Ajustes | ✓ |
| `tarsila-net-set` | IPv4 no NetworkManager sem polkit, via `sudo -n` | painel, `tarsila-perfil` | ✓ |
| `tarsila-wifi` | Janela "Conexões de rede", seção Wi-Fi | painel de Ajustes | ✓ |
| `tarsila-config` | Abre o painel (`/usr/local/share/tarsila/tarsila_config.py`) | `.desktop`, `menu.xml` | ✓ |

### Dock e catálogo de aplicativos

| Script | O que é | Chamado por | |
|---|---|---|---|
| `tarsila-dock-apply.sh` | Ordem da Dock; grava 9 chaves de dconf que ninguém lê | autostart e os 4 abaixo | ~ |
| `tarsila-dock-manager` | Janela "Gerenciar Dock" | "Ver mais", appfinder | ✓ |
| `tarsila-dock-item.sh` | "Tirar do Dock" do clique-direito | Desktop Actions | ✓ |
| `tarsila-app-uninstall.sh` | "Desinstalar" do clique-direito | Desktop Actions | ~ |
| `tarsila-appfinder-yad.sh` | "Aplicativos Instalados" (grade em yad) | `menu.xml`, "Ver mais" | ✗ |
| `tarsila-icon-cache` | Normaliza ícones em PNG para a grade do yad | `appfinder` | ✓ |
| `tarsila-pos-dock` | Onde a janela nasce para encostar na Dock | `lixeira`, `barra-menu` | ✗ |
| `tarsila-lixeira` | A Lixeira | `.desktop` | ✓ |

### Nascimento de janelas

| Script | O que é | Chamado por | |
|---|---|---|---|
| `tarsila-abrindo` | Ampulheta de verdade: cursor de espera e cliques bloqueados | os `.desktop` curados | ✓ |
| `tarsila-uma-janela` | Garante uma janela só por aplicativo (`flock`) | os `.desktop` curados | ✓ |
| `tarsila-vaga.py` | Wrapper de `tarsila_vaga` (a lógica está em `lib/`) | libs | ✓ |
| `tarsila-travar-janela` | Trava tamanho e tira o maximizar | `tarsila-calculadora` | ✓ |
| `tarsila-ajusta-janela` | Ferramenta manual de encaixe (uso do desenvolvedor) | — | ○ |
| `tarsila-aprender-janelas` | Aprende, em tela invisível, como cada app nasce | `tarsila-aquecer` | ✓ |

### Aplicativos

| Script | O que é | |
|---|---|---|
| `tarsila-chromium` | Launcher do Chromium com as flags da box (712 linhas) | ✓ |
| `tarsila-email` | Launcher do Tarsila Email (`/opt/tarsila-email`) | ✓ |
| `tarsila-agenda` | Cópia local do `agenda-tarsila` (fonte canônica é o `.deb`) | ✓ |
| `tarsila-calculadora` | galculator com tamanho travado | ✓ |
| `tarsila-obs` | OBS com o contorno do EGL_BAD_MATCH do Panfrost | ✓ |
| `tarsila-obs-scene-sanitize.py` | Limpa a cena do OBS antes de abrir | ✓ |

### Boot, login e hardware

| Script | O que é | Chamado por | |
|---|---|---|---|
| `tarsila-aquecer` | Aquece o cache de disco dos apps pesados, em tela invisível | `tarsila-aquecer@.service` | ✓ |
| `tarsila-devfreq-gpu` | Fixa a política de frequência da GPU | unit própria | ✓ |
| `tarsila-greeter-power.sh` | Botão de energia na tela de login | `lightdm.conf` | ✓ |
| `tarsila-greeter-power-gtk.py` | A interface desse botão | `greeter-power.sh` | ✓ |
| `tarsila-greeter-power-stop.sh` | Encerra o botão quando a sessão começa | `lightdm.conf` | ✓ |
| `tarsila-oobe-session` | Sessão da primeira execução | `/usr/share/xsessions` | ✓ |
| `tarsila-oobe-gtk.py` | A interface da primeira execução | `oobe-session` | ✓ |
| `tarsila-machine-id-check` | Deveria evitar machine-id duplicado em imagem clonada | — | ○ |

---

## Ordem sugerida

Do que o usuário sente para o que só incomoda quem mantém:

1. **`tarsila-boot-cursor.sh`** — 32 s de ampulheta em todo boot. Uma linha.
2. **O vetor** — decidir se volta (subir o `tela-estados` só para isso, ou portar o
   desenho para dentro do `tarsila-dock`) ou se sai de vez, com a `lib` limpa junto.
   São 1293 linhas paradas esperando essa decisão.
3. **`tarsila-pos-dock`** (e a cópia no appfinder) — trocar `plank` por `tarsila-dock`.
   Com a janela certa, a captura de tela e o PIL provavelmente ficam dispensáveis: a Dock
   nova tem largura própria e não pinta só o meio.
4. **`tarsila-monitor.sh`** — filtrar por `_NET_WM_WINDOW_TYPE`, apagar o `state` órfão e
   decidir o destino do `wincount` (hoje ninguém o lê).
5. **A cor da Dock** — ou ela passa a ler o tema, ou o `theme` do dconf sai dos três
   scripts. Hoje a barra obedece ao tema e a Dock não.
6. **`/etc/skel`** — trocar pelo estado atual, ou fazer o `install.sh` rodar nesta imagem.
7. **Autostart XDG** — escolher fonte única e migrar as quatro coisas úteis.
8. **Faxina** — restos do `plank` no `app-uninstall.sh`, as duas duplicatas `-ob-`,
   `machine-id-check`, `ajusta-janela`, `__pycache__`, as listas de classes envelhecidas.
