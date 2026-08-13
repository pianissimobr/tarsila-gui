# Otimizações de Rede e CPU — Tarsila OS (TV Box)

Alvo: TV Box ARM64. Nesse hardware, a percepção de velocidade do usuário vem
de dois custos que dominam o desktop: **latência de rede** (round-trips) e
**uso de CPU** (parsing de payload, trabalho repetido). Este documento registra
o que foi identificado no `Mapa-requisições.md` e o que foi refatorado.

## 1. Email — Avatar não bloqueia mais (`avatar.py`)

**Problema.** `config.list_accounts()` e `GET /api/status` chamavam
`resolve_avatar()`, que tentava **três serviços externos em série**
(unavatar.io → Google Photos → Gravatar, 10s de timeout cada). Na primeira
abertura, a resposta de `/api/status` podia demorar até 30s — e a UI web
esperava por ela antes de renderizar qualquer coisa.

**Solução.** Nova `resolve_avatar_fast()`:
- Cache quente → devolve a URL local na hora;
- Cache frio → devolve o Gravatar externo imediatamente e dispara o download
  em segundo plano (thread daemon), com um `set` de dedupe para não baixar o
  mesmo avatar duas vezes em paralelo.

`config.account_avatar()` agora usa a versão rápida. O `/api/status` e o
`/api/accounts` passam a responder em milissegundos; o avatar em cache aparece
no próximo pedido.

## 2. Email — Rede fora da UI thread (`tarsila-email-gtk.py`)

**Problema.** `EmailWindow.apply_profile_avatar()` chamava `resolve_avatar()`
(bloqueante, com rede) na thread principal via `GLib.idle_add`, congelando a
janela no arranque e na tela de Contas.

**Solução.** `apply_profile_avatar()` virou assíncrono:
- Cache quente → desenha na hora (leitura de disco, sem rede);
- Cache frio → `resolve_avatar()` + leitura rodam em `_run_bg` (thread) e
  voltam via `idle_add`. A UI nunca mais para por causa de avatar.

## 3. Email — Sync IMAP incremental + fetch em lote (`imap_sync.py`)

**Problema.** `sync_folder()` fazia `SEARCH ALL` a cada sync (baixava *todos*
os UIDs da pasta, mesmo sem nada novo) e um `FETCH` **por mensagem** — N
round-trips de rede. Era o custo dominante numa TV Box com latência alta.

**Solução.**
- `SEARCH ALL` → `SEARCH UID <last_uid+1>:*` (busca só o delta desde o último
  UID sincronizado, guardado em `sync_state.last_uid` via novo
  `db.last_sync_uid()`).
- N `FETCH` → **1 `FETCH` em lote** (`UID FLAGS BODY.PEEK[HEADER.FIELDS …]` com
  a lista de UIDs separada por vírgula), com o UID recuperado da própria
  resposta.

## 4. Email — Menos round-trips no arranque (`tarsila-email-backend.py`)

**Problema.** A UI fazia `status → folders → sync → messages` em sequência, e o
`POST /api/sync` não retornava as mensagens, forçando um `GET /api/messages`
logo em seguida.

**Solução.**
- Novo `GET /api/bootstrap`: devolve `configured + email + name + avatar +
  accounts + folders` numa única chamada.
- `POST /api/sync` agora devolve também `messages / total / has_more` da pasta
  pedida, eliminando o `GET /api/messages` pós-sync.

A UI web (`app.js`) e a GTK passaram a consumir esses contratos.

## 5. Email — Payload enxuto (`db.py` + backend)

**Problema.**
- `GET /api/messages/<id>?body=1` devolvia `body_html` **e** `body_plain`
  juntos — o maior payload da API, ~2× duplicado.
- A lista de mensagens incluía `folder_id` e `uid`, inúteis na UI (o `id` já
  codifica `folder:uid`).

**Solução.**
- `db.list_messages()` / `db.search_messages()` não selecionam mais `folder_id`
  e `uid`.
- Body aceita `?fmt=plain|html` e `_lean_body()` envia **um** corpo só; o outro
  só acompanha quando o preferido não existe (comportamento idêntico ao
  anterior). A GTK pede `plain`, a web pede `html`.

## 6. Agenda — calendarList em cache + resposta parcial (`agenda_tarsila.py`)

**Problema.**
- `_sync_worker` refazia `GET /users/me/calendarList` a **cada autosync (180s)**,
  embora a lista de agendas quase não mude.
- `sync_events` baixava o evento **completo** (creator, organizer, iCalUID,
  reminders, conferenceData, attachments, extendedProperties…), mas a UI só usa
  `id/status/summary/description/location/htmlLink/colorId/start/end`.

**Solução.**
- `Controller._cal_list_at` + `CAL_LIST_TTL = 3600`: reaproveita a lista em
  memória e só volta ao Google no máximo 1× por hora.
- `fields=` de resposta parcial no `sync_events`, restringindo o JSON aos
  campos usados pela interface.

## 7. Sessão Gráfica — Indicadores event-driven e sem spawns pesados

Categoria "Infraestrutura e Sessão Gráfica" (`openbox/deploy/`): os módulos da
Polybar e o alternador de barra. Mesmos três critérios: redução de chamadas,
não bloquear e CPU enxuta.

**Problema.**
- `net.sh` rodava `nmcli` a cada 5s (polling) — 12 spawns/min acordando a CPU
  da TV Box sem necessidade, só para re-exibir o mesmo ícone.
- `sound.sh` rodava a cada 3s com `awk` + `grep` (dois processos por ciclo).
- `tarsila-polybar-mode.sh` media a largura do glifo "▼" com `pango-view` +
  `identify` (ImageMagick) a **cada** alternância full/compact — dois processos
  pesados por clique de maximizar/desmaximizar, para um valor constante.
- `topbar.sh` lia o state file com 2× `sed` + 2× `head` (4 forks) por emissão.

**Solução.**
- `net.sh` virou **event-driven** via `nmcli monitor` (residente; reavalia só
  quando o NetworkManager avisa mudança), com `tail = true` no módulo e
  fallback para polling suave de 5s se o monitor não existir. 12 spawns/min → 0
  em repouso.
- `sound.sh` extrai volume + mute numa **única passagem `awk`** (antes 2
  processos) e o intervalo caiu de 3s para 5s (≈40% menos spawns).
- `tarsila-polybar-mode.sh`: largura do glifo medida **uma vez** e cacheada em
  `~/.config/tarsila/bar-compact-glyph`; toggles posteriores só leem o cache.
- `topbar.sh`: state file lido numa única passagem com `read`/`case` (builtins,
  zero forks).

**Segunda rodada (mesma categoria).**
- `topbar.sh`: o `read -t 2` re-emite o título a cada 2s para acompanhar troca
  de aba sem troca de foco. A cada re-emit rodava `xdotool getwindowname` +
  `xprop WM_CLASS` + `sed`. Como WM_CLASS só muda quando a janela muda, a classe
  agora é cacheada por id: no re-emit periódico resta só o `getwindowname`
  (necessário) — ~60 spawns/min a menos em Estado A.
- `tarsila-ob-margins.sh`: passou a pular `openbox --reconfigure` (re-parse do
  `rc.xml` + reaplicação de regras em todas as janelas) quando a margem `<top>`
  já está correta — caso comum no login e em troca de tema sem mudança de altura
  da barra.

## 8. Serviços de Sistema — Heartbeat com menos forks

Categoria "Serviços de Sistema e Diagnóstico". O único loop contínuo é o
`tarsila-heartbeat` (a cada 30s); os demais são one-shot ou já bloqueantes.

**Problema.** O heartbeat disparava ~10 processos por ciclo de 30s: 2× `awk`
(lendo `/proc/meminfo` duas vezes), 2× `cat` (GPU freq e temperatura), 2×
`pgrep`, 1× `date`, 1× `sync` e 1× `wc -l` (que relia o log inteiro a cada
ciclo só para conferir o teto de 2000 linhas).

**Solução.**
- 2× `awk` → **1× `awk`** que lê `/proc/meminfo` uma vez e extrai
  `MemAvailable` + `SwapFree` + `SwapTotal`.
- 2× `cat` → 2× `read` (builtin; 2 forks a menos).
- `wc -l` do log passa a rodar só a cada **10 ciclos** (5 min) — o teto só
  importa perto das ~17h de uso, não a cada 30s.
- Total: de ~10 para ~5 forks por ciclo, com o `sync -f` preservado (a
  garantia de sobreviver ao reset do watchdog não muda).

Sem mudanças em `tarsila-kmsg` (já é `os.read()` bloqueante — o kernel acorda a
thread quando chega mensagem, sem polling) nem em `tarsila-atualizar`,
`tarsila-aquecer` e `tarsila-devfreq-gpu` (one-shot com `Nice`/`ionice`).

## 9. Segurança e Privilégios — Menos privilégio morto e regra quebrada

Categoria "Segurança e Privilégios" (`/etc/sudoers.d/`). Critério aplicado:
**payload enxuto** (menor superfície de privilégio) + **redução de chamadas**
(um único caminho para atualizar).

**Problema.**
- `tarsila-config` ainda concedia `apt-get update` e `apt-get upgrade -y`, mas
  nada chama `sudo apt-get` no sistema: o botão "Verificar e Instalar" usa
  `sudo -n /usr/local/sbin/tarsila-atualizar` (que tem regra própria). Eram
  duas portas de privilégio mortas.
- A regra `tarsila-net-set` **sem `*`** não casava com a chamada real do painel
  (`sudo -n tarsila-net-set <conexão> auto|manual ...`): o `sudo -n` falhava
  pedindo senha, quebrando a configuração de IP manual/automático.

**Solução.**
- Removidas as duas regras de `apt-get` de `tarsila-config` (o apt fica num
  único lugar: `tarsila-atualizar`).
- `tarsila-net-set` ganhou o `*` (a chamada passa argumentos), alinhado ao
  padrão dos demais (`tarsila-idioma *`, `tarsila-vpn-importar *`,
  `timedatectl set-time *`).

## 10. Gerenciamento de Janelas — Um reconfigure em vez de dois

Categoria "Gerenciamento de Janelas". Os daemons (`tarsila-monitor.sh`,
`tarsila-tela-estados`) e o lançador (`tarsila-abrindo`) já são event-driven ou
com um único `wmctrl`/`XDamage` por ciclo — a vaga já caiu de 1770 ms para
~10 ms e o `Observador` já usa `select()` em vez de `XPending`.

**Problema.** `tarsila_openbox.py` fazia **dois** `openbox --reconfigure` por
abertura: um no `prepara()` (entrar a regra) e um no `limpa()` (retirá-la).
Cada `--reconfigure` re-lê o `rc.xml` inteiro e reaplica as regras de todas as
janelas. O segundo — que só apaga — rodava no `finally` do `tarsila-abrindo`,
**antes** do `XUngrabPointer`, ou seja, segurava o cursor de espera depois de o
aplicativo já estar na tela.

**Solução.** `limpa()` continua removendo a regra do **arquivo** (essencial
para não persistir), mas **não reconfigure**. Quem reconfigure é a próxima
abertura, que já reconfigure de qualquer forma para entrar a regra nova — a
retirada é absorvida ali. O arquivo fica limpo desde já, então qualquer
reconfigure por outro motivo (troca de tema, margens) também recolhe a regra.
Resultado: **1 reconfigure por abertura em vez de 2**, e o cursor de espera é
liberado antes.

## 11. Aparência e Personalização — Cursor de boot e uma leitura de xrandr

Categoria "Aparência e Personalização". A maioria dos módulos é one-shot
(aplicação de tema, wallpaper, dock, entrada) e já vive no `comum.sh` como
funções puras sem cópia — as decisões (mapa tema→Dock, ícone por altura de
tela, pintura do fundo) existem num lugar só.

**Problema 1 — cursor de "carregando" preso ~32s a cada boot.**
`tarsila-boot-cursor.sh` mostra o cursor `watch` e espera a sessão montar com
um laço `pgrep plank && pgrep xfce4-panel`. Mas esta sessão é Openbox+polybar:
o `xfce4-panel` **nunca sobe** (o substituto dele é a polybar, ver o autostart).
O segundo `pgrep` nunca casava, o laço esgotava as 60 iterações (30s) mais o
`sleep 2`, e o cursor de espera ficava na cara do usuário por ~32s mesmo com o
desktop pronto — além de ~120 `pgrep` desperdiçados por login.

**Solução.** `xfce4-panel` → `polybar`. O laço agora quebra assim que a Dock e
a barra estão de pé; o teto de 30s fica só como segurança (cursor sempre volta
à seta mesmo se algo não subir).

**Problema 2 — três leituras de `xrandr --query` no login.**
`tarsila-resolucao-apply.sh` chamava `xrandr --query` três vezes (para achar a
saída conectada, a lista de modos e o modo atual), cada uma re-negociando com a
GPU.

**Solução.** Uma única captura `XRANDR=$(xrandr --query)`, e os três usos
bebem dela.

## 12. Rede e Conectividade — Já event-driven (sem mudança)

Categoria "Rede e Conectividade". Verificada por inteiro; o caminho **ativo**
já está otimizado:

- **Indicador da barra** — o polybar usa `net.sh` (event-driven via
  `nmcli monitor`, `tail = true`; já coberto na seção 7). Zero polling em
  repouso.
- **`tarsila-wifi` (GTK)** — todas as chamadas `nmcli` (status do device, lista
  de redes, conectividade, taxa do link) rodam em **thread de fundo** e voltam
  via `GLib.idle_add`; o scan real (`rescan`) só dispara no botão "Procurar
  redes". A janela nunca congela por causa de rede.
- **`tarsila-net-set`** — one-shot (`nmcli connection modify` + `up`), já com a
  regra sudoers corrigida (seção 9).
- **`tarsila-vpn-importar`** — one-shot; deduz o tipo por extensão/conteúdo e
  delega ao `nmcli connection import`.

## 13. Mídia — Modo Cinema e Descanso (só um fork a menos)

Categoria "Mídia". Verificada por inteiro; quase tudo já é event-driven ou
one-shot:

- **`cinema_host.py`** — host de native messaging one-shot: lê uma mensagem do
  stdin e responde; o `abrir_no_mpv` faz um `pgrep mpv` (dedupe de clique) e um
  `Popen`. Sem loop.
- **Extensão (`cinema-ext/*.js`)** — o service worker aplica as regras uma vez
  no install/startup; os content scripts reagem a eventos (`MutationObserver`
  com debounce no `cinema.js`, listeners de toque no `toque.js`). O único
  `setInterval` (700ms) é o `youtube.js`, que re-desmuta o vídeo — deliberado
  (o YouTube re-muta sozinho na troca de qualidade/faixa) e limitado à página
  do YouTube.
- **`tarsila-descanso`** — one-shot: DPMS off ou `exec mpv` (a escolha do vídeo
  já é explícita, sem custo de decodificação quando ninguém olha).

**Mudança.** `tarsila-descanso-vigia` (loop de 20s) lia o arquivo de minutos
com `cat` (fork externo a cada volta). Virou `read` (builtin, zero forks) —
mesmo critério da seção 8. O `xprintidle` a cada 20s é mantido: é a consulta
MIT-SCREEN-SAVER do X, não há alternativa mais leve no trixie e o custo é
desprezível.

## 14. Distribuição de Software — Store GTK já enxuta (sem mudança)

Categoria "Store". A versão ativa (GTK) já aplica os três critérios:

- **CPU enxuta** — `tarsila_store_dados.instalados()` faz **um** `dpkg-query`
  batelado com todos os pacotes do catálogo (não um por pacote).
- **Não bloquear** — instalar/remover rodam em **thread** (`dados.executar` →
  `sudo -n tarsila-pkg`), voltando via `GLib.idle_add`; a loja continua
  navegável durante o apt.
- **Payload enxuto** — o catálogo vem direto dos `.js` existentes (JSON
  recortado, sem cópia duplicada) e as capas têm **cache com teto de 400**
  (`Capa._cache`), para não inflar a RAM da box.

O que resta de periódico é deliberado e espelha a versão web: re-varredura do
dpkg a cada 60s (só enquanto a loja está aberta, para pegar instalação feita
por fora) e a rotação do destaque a cada 9s (animação visual). O legado pesado
— servidor HTTP WebKit com `GET /api/instalados` a cada 60s e `/api/tarefas` a
cada 2.5s — já está em "Pendências" para desligar com a migração.

## 15. Configuração do Sistema — Painel de Ajustes (xfconf morto removido)

Categoria "Configuração do Sistema". Os três ajudantes sudo já estavam corretos
e one-shot: `tarsila-atualizar` (nice/ionice, trava do apt, uma simulação para
contar), `tarsila-idioma` (uma passada por arquivo) e `tarsila-perfil` (uma
ação por linha do sudoers).

O painel (`tarsila_config.py`) já é bem desenhado para ARM: páginas construídas
**sob demanda** (lazy), e toda ação com efeito demorado roda em **thread**
(`_check_updates`, NTP, fuso, idioma, configuração de IP, foto, `_procurar_scanner`)
voltando via `GLib.idle_add`.

**Mudança.** A página Aparência chamava `xfconf_get("xsettings", "/Net/ThemeName")`
e **jogava o resultado fora** — a linha seguinte lê o tema real do arquivo do
`xsettingsd` (`xsettings_get`). Era um `xfconf-query` desperdiçado a cada
abertura da página, que nesta sessão Openbox (sem xfconfd) ainda falha devagar.
Removidas a chamada morta e as funções `xfconf_get`/`xfconf_set`, que só ela
usava.

## 16. Utilitários e Acessórios — Já event-driven (sem mudança)

Categoria "Utilitários e Acessórios". Verificada por inteiro; nada no caminho
ativo roda em polling:

- **`tarsila-topbar-dots.py`** — event-driven via Wnck (`active-window-changed`,
  `state-changed`), sem polling; o `timeout` de 60s é só rede de segurança.
- **`tarsila-dispositivos`** — lê `udevadm monitor` em leitura bloqueante (o
  kernel acorda quando há evento); sem laço de varredura.
- **`tarsila-barra-menu`** — one-shot: abre, tira uma foto do `/proc`/`statvfs`
  uma vez e morre com a janela. A "medição" de CPU (2 leituras separadas por
  0,25s) só roda no menu "sistema" quando aberto.
- **`tarsila-chromium`**, **`tarsila-obs`**, **`tarsila-calculadora`**,
  **`tarsila-vermais.sh`**, **`tarsila-greeter-power-gtk.py`** — one-shot.
- **`tarsila-appfinder-yad.sh`** — one-shot; o cache de ícones é persistente por
  usuário (só ícone novo é renderizado) e a medição da Dock (`import`+PIL) é
  pontual, por abertura.

## 17. Cloud — Nextcloud one-shot (sem mudança)

Categoria "Cloud". Os quatro scripts (`nc-mount.py`, `nc-edit-online.py`,
`nc-share.py`, `nc-setup.py`) são todos one-shot, disparados por ação do usuário
(menu do Thunar, wizard) ou uma vez no login:

- **`nc-mount.py`** — roda `(sleep 5; …) &` no autostart (fora do caminho da
  sessão); um `gio mount` + um `gio mount -l` para conferir, e o laço de espera
  do gvfs é limitado (25×1s) e em segundo plano.
- **`nc-edit-online.py`** / **`nc-share.py`** — uma única chamada HTTP
  (PROPFIND / POST share) com `timeout=10`, depois `xdg-open`/`xclip`. Sem loop.
- **`nc-setup.py`** — wizard com três diálogos zenity e um `GET` de validação.

Todas as chamadas de rede têm timeout explícito e nenhum polling; nada a mudar
na categoria.

## 18. Arquivos de Configuração e Assets — Estáticos, já corretos (sem mudança)

Categoria "Arquivos de Configuração e Assets". São ativos estáticos (temas GTK,
ícones, temas da Dock, tema de boot do Plymouth, listas `aquecer.txt`/
`native-apps.txt`, manifestos da extensão) — não executam nada por conta própria
e não têm custo de CPU/rede em repouso. Os dois únicos que afetam runtime já
estavam otimizados:

- **`picom-xrender.conf`** — backend `xrender` (sem GLX), `shadow=false`,
  `fading=false`, `unredir-if-possible=true` e `corner-radius=0` (a sombra
  custava 4% de CPU contínuos; o vídeo em tela cheia ganhou 26→33 fps).
- **`descanso/relogio.lua`** — redesenha o OSD só quando o texto muda (uma vez
  por minuto); redesenhar a cada segundo levava o modo de espera de 50% para
  91% de CPU.

Nada a mudar na categoria.

## O que NÃO mudou (já estava correto)

- **Agenda**: sync já roda em thread de fundo e publica via `GLib.idle_add`
  (`_sync_worker`, `save_event`, `delete_event`, `push_local_to_google`).
- **Store GTK**: não usa HTTP — `tarsila_store_dados.instalados()` faz um único
  `dpkg-query` batelado e as ações (`sudo -n tarsila-pkg`) rodam em thread.
- **Sessão**: `picom-xrender.conf` já sem sombra/fading e com
  `unredir-if-possible`; `autostart` já sobe componentes em `&` (paralelo);
  `xsettingsd`/`dunst`/`devilspie2` são residentes sem polling;
  `tarsila-tela-estados` e `tarsila-ob-decor.sh` já são event-driven (inotify/
  X); `tarsila-polybar-hitboxes.py`, `tarsila-dialogos`, `tarsila-limpar.sh` e
  `tarsila-ob-power.sh` são one-shot.

## Verificação

- `python3 -m py_compile` em todos os `.py` alterados: sem erro.
- `node --check` no `app.js`: sintaxe válida.
- `bash -n` e `sh -n` nos scripts de sessão alterados: sintaxe válida.
