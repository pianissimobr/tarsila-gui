# Mapa de Rotas e Requisições — Tarsila OS

## 1. Infraestrutura do Sistema

| Script / Componente | Descrição |
|---|---|
| `etc/lightdm/lightdm.conf` | Display manager da tela de login. Inicia a sessão gráfica (Openbox) para o usuário. |
| `etc/lightdm/lightdm-gtk-greeter.conf` | Tema do greeter do LightDM (aparência da tela de login). |
| Openbox | Gerenciador de janelas da sessão. Responsável por decorar, posicionar e gerenciar todas as janelas. Política de posicionamento "Smart". Configurado via `~/.config/openbox/rc.xml`. |
| Polybar | Barra superior. Exibe relógio, pontos de estado de janela (genmon `tarsila-topbar-dots.py`) e menu do sistema (`tarsila-barra-menu`). |
| Plank | Dock inferior com ícones de apps fixos e abertos. Tema controlado por `tarsila-dock-apply.sh`. |
| Picom | Compositor X11. Fornece transparência, sombras e vsync. Configurado em `/usr/share/tarsila/picom.conf`. |
| Devilspie2 | Daemon que aplica regras de janela no nascimento (ex.: Chromium nasce maximizado). Scripts Lua em `~/.config/devilspie2/`. |
| xsettingsd | Serviço que mantém temas GTK, fontes e modo escuro. Lê `~/.config/xsettingsd/xsettingsd.conf`. Recarregado com `SIGHUP`. |
| Dunst | Daemon de notificações desktop. Configurado em `~/.config/dunst/dunstrc`. Recarregado com `dunstctl reload`. |
| `etc/pipewire/pipewire.conf.d/51-tarsila-fone.conf` | Configuração do PipeWire para troca automática de saída de áudio ao conectar fone. |

---

## 2. Serviços systemd

| Script | Descrição |
|---|---|
| `tarsila-heartbeat.service` | **Diagnóstico persistente.** A cada 30s grava em `/opt/tarsila-diag/heartbeat.log` (eMMC real, não zram) métricas do sistema: load (1m/5m), memória disponível, swap usado, frequência/temperatura da GPU, e contagem de processos Xorg e Chromium. O arquivo sobrevive a reset por watchdog — a última linha mostra o estado no momento do travamento. Teto de ~2000 linhas (~17h). |
| `tarsila-atualizar.service` + `.timer` | **Atualização do sistema.** O timer dispara 3 minutos após o boot (`OnBootSec=3min`) para não segurar o arranque. O serviço `Type=oneshot` executa `apt-get update && apt-get upgrade -y` com `DEBIAN_FRONTEND=noninteractive` e `--force-confold`. Não falha se estiver sem internet (`SuccessExitStatus=0 1`). O mesmo script é chamado pelo botão "Verificar e Instalar" nos Ajustes. |
| `tarsila-kmsg.service` | **Log persistente do kernel.** Lê `/dev/kmsg` continuamente e grava cada registro em `/opt/tarsila-diag/kmsg.log` com `fsync()` por mensagem (limitado a 1 por segundo em tempestade de faltas). Existe porque o journal é volátil (zram) e o `zram-config-sync` paralisa o journald. Teto de 4 MB, com rotação. |
| `tarsila-devfreq-gpu.service` | **Frequência da GPU.** Aplica política de governador e limites mínimo/máximo em `/sys/class/devfreq/fe400000.gpu/` para a GPU Mali (panfrost). `Type=oneshot` com `RemainAfterExit=yes`. |
| `tarsila-aquecer@.service` | **Aquecimento de cache.** Roda antes do login do usuário, num X server invisível (`Xvfb`). Abre e fecha os aplicativos pesados listados em `/usr/share/tarsila/aquecer.txt` para forçar o kernel a cachear as páginas de disco em RAM. `Nice=19`, `IOSchedulingClass=idle` — nunca compete com a área de trabalho. |
| `zram-config-sync.service` + `.timer` | **Sincronia RAM→disco.** A cada 6h (`OnUnitActiveSec=6h`) sincroniza os diretórios mantidos em RAM (zram) para o disco real. A primeira sincronia é 1h após o boot. |

---

## 3. Sudoers (Regras NOPASSWD)

Cada arquivo em `/etc/sudoers.d/` autoriza um caminho específico e fixo, sem coringas amplos:

| Arquivo | Comando | Chamado por |
|---|---|---|
| `tarsila-atualizar` | `/usr/local/sbin/tarsila-atualizar` | Ajustes → "Verificar e Instalar" |
| `tarsila-config` | `timedatectl set-ntp/set-time/set-timezone`, `tarsila-net-set` | Ajustes (várias ações) |
| `tarsila-idioma` | `/usr/local/sbin/tarsila-idioma` | Ajustes → trocar idioma |
| `tarsila-perfil` | `/usr/local/sbin/tarsila-perfil` | Ajustes → nome/foto do perfil |
| `tarsila-vpn` | `/usr/local/sbin/tarsila-vpn-importar` | Ajustes → importar VPN |

---

## 4. Lançador Universal: `tarsila-abrindo`

**Arquivo:** `usr/local/bin/tarsila-abrindo`

É o ponto único de abertura de **todos** os aplicativos do sistema. Todo `.desktop` da grade curada chama `tarsila-abrindo <comando>`.

### Ciclo de abertura:

1. **Ampulheta + bloqueio de cliques** — `XGrabPointer` com cursor de espera sobre todas as janelas. Impede clique duplo acidental. O X libera automaticamente se o processo morrer.
2. **Espera pela janela** — lê `_NET_CLIENT_LIST` direto do servidor (ctypes, sem subprocesso) e dorme num `select()` na conexão do X até a lista mudar. Teto de 8 s.
3. **Solta o ponteiro.** Fim.

Quem decide **onde** a janela nasce é o Openbox, pela política `Smart` + `center` que já estava no `rc.xml`.

---

## 5. O que existia aqui, e foi removido em 17/08/2026

Entre o passo 1 e o passo 3 havia um sistema inteiro. Saiu por decisão do dono
do projeto: pesava mais do que entregava.

| Removido | O que fazia |
|---|---|
| `tarsila_vaga.py` (14 KB) | 7 slots de posicionamento; escolhia em qual deles a janela ia nascer |
| `tarsila_vetor.py` (30 KB) | Retângulo animado na vaga, se o app demorasse mais de 0,7 s; cache de tamanhos medidos; observador XDamage |
| `tarsila_openbox.py` (9 KB) | Reescrevia o `rc.xml` com `<position force="yes">` e disparava `openbox --reconfigure` **a cada abertura** |
| `tarsila-tela-estados` (1293 linhas) | Processo GTK residente cuja única função viva era pintar esse retângulo |
| `tarsila-aprender-janelas` (329 linhas) | Abria cada app numa tela invisível para medir como ele nasce e alimentar o cache |

O `openbox --reconfigure` era o custo dominante: faz o gerenciador reler o
`rc.xml` inteiro e reaplicar as regras a **todas** as janelas, no exato instante
em que a máquina está ocupada abrindo o aplicativo. O sistema gastava
processamento para escolher onde a janela nasce e, quando escolhia devagar
demais, precisava de um desenho para tapar a espera que ele mesmo causava.

Medido na box, abrindo a Calculadora pelo caminho real:

| | antes | depois |
|---|---|---|
| até a janela na tela | 3823 ms | 2885 ms |
| forks do sistema na abertura | 91 | 83 |
| ampulheta presa (medida direta) | — | 1369 ms |

129 KB de código a menos, um processo residente a menos. Os dados aprendidos
(`~/.config/tarsila/nascimento.txt` e `tamanhos.txt`) saíram junto.

---

## 6. Tarsila Email

**Diretório base:** `opt/tarsila-email/`

### API Backend (`bin/tarsila-email-backend.py`)
Servidor HTTP `ThreadingHTTPServer` na porta **8475** (`127.0.0.1`). CORS aberto. Rotas:

| Método | Rota | Função |
|---|---|---|
| `GET` | `/` ou `/index.html` | Serve a UI web |
| `GET` | `/css/*`, `/js/*` | Assets estáticos |
| `GET` | `/api/status` | Status da configuração (conta ativa, e-mail, nome, avatar, lista de contas) |
| `GET` | `/api/accounts` | Lista todas as contas configuradas |
| `POST` | `/api/accounts/open-setup` | Abre o assistente de configuração (`tarsila-email-setup.py`) |
| `POST` | `/api/accounts/switch` | Troca a conta ativa |
| `POST` | `/api/logout` | Remove todas as contas e dados locais |
| `GET` | `/api/folders` | Lista pastas IMAP (inbox, sent, drafts, starred, spam, trash) |
| `GET` | `/api/messages?folder=&page=&limit=&q=` | Lista mensagens com paginação e busca |
| `GET` | `/api/messages/<id>?body=1` | Detalhes da mensagem (com corpo via IMAP se `body=1`) |
| `GET` | `/api/sync/status` | Timestamp da última sincronização |
| `POST` | `/api/sync` | Dispara sincronização IMAP (pasta específica ou todas) |
| `POST` | `/api/messages/send` | Envia e-mail via SMTP |
| `POST` | `/api/drafts` | Salva rascunho no Gmail (via IMAP APPEND) |
| `POST` | `/api/messages/<id>/read` | Marca como lida (IMAP STORE +FLAGS \Seen) |
| `POST` | `/api/messages/<id>/star` | Alterna estrela (IMAP STORE ±FLAGS \Flagged) |
| `POST` | `/api/messages/<id>/trash` | Move para lixeira (IMAP COPY + STORE \Deleted + EXPUNGE) |
| `GET` | `/api/avatar/local/<key>` | Serve avatar em cache (PNG/JPEG) |

### Bibliotecas (`lib/`)

| Módulo | Descrição |
|---|---|
| `api_client.py` | Cliente HTTP Python para a API local. Usado pela UI GTK nativa. Métodos: `get()`, `post()`, `ok()`, `fetch_bytes()`. |
| `config.py` | **Configuração multi-conta.** Armazena em `~/.config/tarsila-email/config.json`. Suporta múltiplas contas com chaveamento. Senha ofuscada com XOR + base64 (`passkey0`). |
| `db.py` | **Cache SQLite local.** Tabelas: `folders` (pastas IMAP), `messages` (cache de mensagens), `sync_state` (último UID sincronizado). Schema com índices para busca e paginação. Teto de 500 mensagens com `prune_cache()`. |
| `imap_sync.py` | **Sincronização IMAP.** Conexão `IMAP4_SSL` com Gmail. Descobre pastas por atributos `SPECIAL-USE` (RFC 6154) + fallback por nome (com decodificação UTF-7 modificado). Sync incremental (últimos N UIDs) com fetch de `FLAGS` + `BODY.PEEK[HEADER.FIELDS]`. Suporte a IDLE, movimentação entre pastas, rascunhos. |
| `smtp_send.py` | **Envio SMTP.** `SMTP_SSL` com Gmail. Suporta anexos (base64). Após envio, sincroniza a pasta "sent". |
| `avatar.py` | **Avatar do perfil.** Busca em 3 fontes: `unavatar.io/google/<email>`, `s2/photos/profile/<email>`, `gravatar.com/avatar/<md5>`. Cache local em `~/.local/share/tarsila-email/avatars/`. |

### Interfaces de Usuário

| Script | Descrição |
|---|---|
| `tarsila-email-gtk.py` | **UI 100% GTK3 nativa.** Sem WebKit. Usa `Api` client para todas as operações. Gerencia backend (inicia se necessário) e IDLE daemon. Tema CSS em `gmail-gtk.css`. Funcionalidades: lista de mensagens com pastas, busca, composição com anexos, diálogo de contas, leitura com ações (responder, estrela, apagar). |
| `UI Web (index.html + app.js)` | **SPA vanilla JS.** Consome a API REST local via `fetch()`. Funcionalidades completas: pastas, mensagens, composição, múltiplas contas, logout. |
| `tarsila-email-setup.py` | **Assistente de configuração.** Wizard GTK3 em duas telas: (1) tela inicial com link para Google App Passwords e explicação, (2) formulário e-mail + senha de app. Testa conexão IMAP (imaplib) antes de salvar. Abre o app principal ao concluir. |

### Daemons

| Script | Descrição |
|---|---|
| `tarsila-email-idle.py` | **Push de novos e-mails.** Loop infinito com `IMAP IDLE` na INBOX. Ao detectar mudança (via `select.select`), busca a mensagem mais recente e dispara `notify-send`. Reconecta a cada ~9 min (timeout do Gmail). Fallback: sleep de 5 min em caso de erro. |

---

## 7. Agenda Tarsila

**Arquivo:** `opt/agenda-tarsila/agenda_tarsila.py` (arquivo único, ~2700 linhas)

Calendário GTK3 completo com Google Agenda opcional.

| Componente | Descrição |
|---|---|
| **UI** (`MainWindow`) | Três visões: Dia (com grade horária), Semana (7 colunas com eventos empilhados e allday no cabeçalho), Mês (grade 6×7 com chips de eventos). Sidebar com mini calendário, lista de agendas (checkboxes), botão "Criar evento" e "Enviar locais ao Google". Cores derivadas do tema GTK (`Palette`). |
| **Modelo** (`Store`, `Ev`) | `Store` — SQLite local (`~/.local/share/agenda-tarsila/cache.db`). Tabelas: `calendars`, `events` (com range d0-d1), `sync` (syncToken + horizonte), `sync_links` (eventos locais → Google). `Ev` — wrapper de evento com parsing de datas Google, suporte a all-day, multiday, colunas sobrepostas. |
| **Google Plugin** (`GooglePlugin`) | **OAuth 2.0 Installed App + PKCE.** Loopback HTTP server em porta aleatória. `webbrowser.open()` para autorização. Troca `authorization_code` por `access_token` + `refresh_token`. Token salvo em `token.json`. Refresh automático. |
| **Google Calendar API** | Endpoints consumidos: `GET /users/me/calendarList` (lista agendas), `GET /calendars/{id}/events` (sync com `syncToken` ou janela de tempo), `POST /calendars/{id}/events` (criar), `PATCH /calendars/{id}/events/{id}` (editar), `DELETE` (remover). Horizonte de ±400/800 dias. |
| **Controller** (`Controller`) | Orquestrador. Gerencia estado (visão, semana, datas), carrega do cache SQLite, decide se precisa sincronizar (horizonte insuficiente → full sync, senão incremental). Autosync a cada 180s. Push de eventos locais para o Google (fase D/E). |
| **Sync** | Suporta dois modos: **full** (sem token, com `timeMin`/`timeMax`) e **incremental** (com `syncToken`). `SyncExpired` (HTTP 410) dispara reset do calendário e full sync. |
| **Eventos locais** | Agenda `local:default` sempre existe. Eventos criados offline são salvos no SQLite e podem ser enviados ao Google depois. Link `sync_links` rastreia a correspondência. |

### Fluxo de autenticação OAuth:

```
Agenda → GooglePlugin.interactive_login()
  → DesktopFlow.run()
    → HTTPServer(127.0.0.1, porta aleatória)
    → webbrowser.open(accounts.google.com/o/oauth2/v2/auth?...)
    → Navegador redireciona para http://127.0.0.1:<porta>/?code=...&state=...
    → POST oauth2.googleapis.com/token (authorization_code + code_verifier)
    → access_token + refresh_token
```

---

## 8. Modo Cinema (Extensão Chromium)

**Diretório:** `usr/share/tarsila/cinema-ext/`

| Arquivo | Descrição |
|---|---|
| `background.js` | **Service Worker MV3.** Três funções: (1) **Native Messaging** — ao receber mensagem do popup, envia `{url, qualidade}` via `chrome.runtime.sendNativeMessage("br.tarsila.cinema")` para o host nativo. (2) **Regras de User-Agent** — `declarativeNetRequest` com regras dinâmicas que injetam `User-Agent` mobile em todos os domínios da lista curada. (3) **Content Scripts** — registra `ua-main.js` + `toque.js` no mundo `MAIN` de todos os frames dos sites da lista. Recarrega abas abertas ao iniciar. |
| `cinema_host.py` (`usr/local/lib/tarsila/`) | **Host nativo.** Recebe JSON via stdin/stdout (protocolo Native Messaging: 4 bytes little-endian + payload). Abre a URL no `mpv` com `--fs --hwdec=auto-safe --ytdl=yes` e formato de qualidade configurável (auto/1080/720/480 com limites de codec H.264 e fps). Usa `tarsila-abrindo` como wrapper para ampulheta. Detecta se já há mpv rodando (evita dupla abertura). |
| `ua-main.js` | Injetado no mundo `MAIN`. Sobrescreve `navigator.userAgent`, `navigator.platform` e propriedades de tela para simular dispositivo móvel. |
| `toque.js` | Injetado no mundo `MAIN`. Adapta eventos de toque/scroll para sites mobile. |
| `sites-mobile.js` | Lista de domínios que recebem versão mobile. |
| Demais arquivos | `fundo.js`, `imagens.js`, `modo_leve.js`, `youtube.js`, `cinema.js`, `rules.json` — scripts auxiliares e regras de conteúdo. |

### Fluxo Modo Cinema:

```
Usuário clica no ícone da extensão no Chromium
  → Popup envia chrome.runtime.sendMessage({url, qualidade})
  → background.js → chrome.runtime.sendNativeMessage("br.tarsila.cinema", msg)
  → cinema_host.py (processo nativo)
    → subprocess.Popen: tarsila-abrindo mpv --fs --hwdec=auto-safe --ytdl=yes <url>
    → tarsila-abrindo: ampulheta + bloqueio de cliques
    → mpv abre com yt-dlp integrado, tela cheia, aceleração de hardware
```

---

## 9. Tarsila Store

**Diretório base:** `opt/tarsila-store/`

| Arquivo | Descrição |
|---|---|
| `tarsila-store-gtk.py` (`bin/`) | **Interface GTK3 da loja.** Navegação com barra superior (Apps / Jogos), busca, tema claro/escuro. Hero com destaques, trilhos por categoria, grade de cartões com capas. Modal de detalhes com botão Instalar/Remover, comando terminal, licenças, selos. Feedback visual durante instalação (spinner). |
| `tarsila_store_dados.py` (`usr/local/lib/tarsila/`) | **Camada de dados.** Lê os catálogos `catalog-apps.js` e `catalog-jogos.js` (parse do JSON dentro dos arrays JavaScript). Consulta `dpkg-query` para estado de instalação. Executa `sudo -n tarsila-pkg install/remove <pkg>` em thread separada. Gerencia cache de capas e tema (claro/escuro). |
| `tarsila_store_visual.py` (`usr/local/lib/tarsila/`) | **Renderização.** Desenho de capas via Cairo (blob colorido com iniciais quando não há imagem PNG, igual à versão web). Cartões com selos (RAM, PT-BR, Gamepad, 3D, Licença, Instalado). Temas claro/escuro com os mesmos tokens CSS da versão web original. |
| `tarsila-pkg` (`bin/`) | **Wrapper seguro para apt.** Roda como root via `sudo NOPASSWD`. Valida o nome do pacote contra `/opt/tarsila-store/whitelist.txt`. `install`: `apt-get install -y --no-install-recommends` + cria atalhos `.desktop`. `remove`: captura atalhos antes do `apt-get remove -y` (inclusive os curados com nome próprio). Log em `/var/log/tarsila-store.log`. |
| `tarsila-store-handler.sh` | **Handler do protocolo `tarsila://`.** Registrado como esquema de URI no sistema. Parse rigoroso: só aceita `tarsila://install/<pacote>`. Valida contra whitelist. Instala via `pkexec apt-get install -y`. Feedback com `notify-send` e barra de progresso (`zenity`). |
| `tarsila-atalho-criar` (`bin/`) | **Gerador de atalhos .desktop.** Chamado pelo `tarsila-pkg` após instalar. Copia/ajusta arquivos `.desktop` dos pacotes para `/usr/share/tarsila/applications/` ou `games/`, garantindo ícones e nomes consistentes. |
| `tarsila-deb-gui.py` (`bin/`) | **Instalador de .deb avulso.** Diálogo GTK para selecionar um arquivo `.deb`. Mostra metadados do pacote (`dpkg-deb --info`). Instala via `pkexec dpkg -i` com feedback. |
| `tarsila-deb-instalar` (`bin/`) | Script chamado pelo GUI para executar `dpkg -i` com `pkexec`. |
| `loja/` | Assets da versão web: `index.html`, `css/store.css`, `js/store.js`, `catalog/catalog-apps.js`, `catalog/catalog-jogos.js`, `capas/` (~130 PNGs de ícones), `icons/` (ícones da loja em vários tamanhos). |

---

## 10. Painel de Ajustes

**Arquivo:** `usr/local/share/tarsila/tarsila_config.py` (~3000+ linhas)

Painel de configuração GTK3 no estilo "System Preferences", com 7 (ou 8, com dev) categorias fixas. Construção lazy (páginas montadas sob demanda para economizar RAM em ARM).

| Categoria | Funcionalidades |
|---|---|
| **Geral** | Nome do usuário (`tarsila-perfil` via sudo), foto do perfil (recorte circular em Cairo, salva em `/var/lib/tarsila/perfil.png`), troca de senha, idioma (`tarsila-idioma`), data/hora e fuso horário (`timedatectl`), atualizações (`tarsila-atualizar`), espaço em disco, formatar disco/pendrive, sobre o sistema. |
| **Internet** | Status das conexões (Wi-Fi e Ethernet via `nmcli`), botão "Conectar ao Wi-Fi" (abre `tarsila-wifi`), "Redes salvas" (`nm-connection-editor`), "Importar VPN" (`tarsila-vpn-importar`), IP automático/manual (`tarsila-net-set`), modo avião (`nmcli radio all on/off`), números da conexão ativa (IP, gateway, DNS). |
| **Aparência** | Tema visual (Padrão / Marítimo / Escuro / Brasileiro / Personalizado), papel de parede, modo escuro (`xsettingsd`), tamanho do texto, ícones na área de trabalho. |
| **Som e Notificações** | Volume, dispositivos de entrada/saída, tempo das notificações (`dunstrc`). |
| **Tela e Energia** | Resolução (`xrandr`), suspensão/desligamento de tela. |
| **Dispositivos** | Mouse (velocidade, scroll), teclado (layout), impressora, câmera, microfone, USB, Bluetooth. |
| **Acessibilidade** | Alto contraste (tema `Tarsila-Contraste`), tamanho do texto. |
| **Avançado** (oculto) | Desbloqueado com 7 toques no número da versão. Opções de desenvolvimento. |

### Mecanismos internos:

- **Busca global** — Índice estático (`SEARCH_TOPICS`) com sinônimos coloquiais. Resultados navegam para a categoria e destacam a linha.
- **Posicionamento** — Janela não redimensionável, posicionada junto à Dock via `tarsila-pos-dock`, altura calculada dinamicamente (espaço entre Polybar e Plank menos a moldura).
- **xsettingsd** — Tema escuro e tamanho do texto gravam em `~/.config/xsettingsd/xsettingsd.conf` e mandam `pkill -HUP xsettingsd`.
- **Polybar** — Mudanças de hora/fuso disparam `pkill -USR1 polybar` para recarregar.

---

## 11. Rede e Conectividade

| Script | Descrição |
|---|---|
| `tarsila-wifi` (`usr/local/bin/`) | **Janela GTK3 "Conexões de rede".** Tabela com SSID, sinal (%), segurança, status de internet. Scan de redes com `nmcli device wifi list`. Conexão com diálogo de senha. Mostra velocidade negociada do link (`GENERAL.SPEED`). Estado de internet via `CONNECTIVITY` do NetworkManager (custo zero). |
| `tarsila-net-set` (`usr/local/bin/`) | **Configuração IPv4.** Chamado via `sudo -n`. Modos: `auto` (DHCP) ou `manual <ip/prefixo> <gateway> <dns>`. Aplica com `nmcli connection modify` + `nmcli connection up`. |
| `tarsila-vpn-importar` (`usr/local/sbin/`) | **Importador de VPN.** Detecta tipo pelo conteúdo do arquivo (WireGuard: `[Interface]` + `PrivateKey`; OpenVPN: `remote`/`client`/`dev tun`/`dev tap` ou extensão `.ovpn`). Chama `nmcli connection import type <wireguard/openvpn>`. |

---

## 12. Monitor da Sessão — removido em 17/08/2026

O `tarsila-monitor.sh` era um daemon que varria as janelas a cada 2 s. Das
quatro coisas que fazia, **três já não serviam a ninguém**:

| Responsabilidade | Destino |
|---|---|
| **Contagem de janelas** | **Cortada.** Escrevia `$XDG_RUNTIME_DIR/tarsila-wincount`; o último leitor era o `tarsila-tela-estados`, removido no mesmo dia. Contava errado de todo jeito: pulava Plank e painéis do XFCE, que não existem, e contava a Dock e a barra — 3 janelas com a área de trabalho vazia. |
| **Estado 1/2/3 + sons** | **Cortado.** A variável era calculada a cada ciclo e nunca usada; não havia `paplay` nem `.oga` no arquivo. O som das transições já não existia. |
| **Prioridade (`renice +10`)** | **Cortada.** Um usuário comum não consegue *baixar* o nice de volta (EPERM, testado): tudo derivava para +10 e nunca voltava. No momento do corte, a própria Dock e a própria barra já estavam em nice 10, degradadas para sempre pelo daemon que deveria priorizar o primeiro plano. |
| **Títulos amigáveis** | **Preservada** — mudou de casa, para o `tarsila-estado.sh`. |

O título não é enfeite: o `tarsila-uma-janela` acha a janela existente **pelo
título** (`^Calculadora$`), então perdê-lo quebraria a instância única.

A mudança de casa é a parte interessante. O `tarsila-estado.sh` já acorda
exatamente nos eventos que o monitor procurava varrendo: janela nasce, foco
muda, título muda (esta última entrou junto, `_NET_WM_NAME` no espião da janela
ativa). Ou seja, o trabalho já estava sendo feito — faltava só reaproveitá-lo.

De quebra o título passou a funcionar no Thunar: o `case` do monitor procurava
a classe `Thunar.Thunar`, e o `wmctrl` imprime `thunar.Thunar`. Nunca casou.
galculator e qpdfview funcionavam; o Thunar dizia "alan - Thunar" desde sempre.

**Medido:** forks em repouso caíram de **35 para 12 a cada 20 s** — o monitor
sozinho respondia por 1,2 dos 1,75 fork/s da sessão parada.

---

## 13. Aparência (Temas, Wallpaper, Dock)

| Script | Descrição |
|---|---|
| `comum.sh` (`usr/local/lib/tarsila/`) | **Biblioteca compartilhada.** Funções puras (só respondem perguntas, não escrevem): `tema_salvo()`, `wallpaper_do_tema()`, `wallpaper_salvo()`, `dock_do_tema()`, `altura_tela()`, `icone_dock()` e `pinta_fundo()` (fallback em cascata: feh → xwallpaper → hsetroot → convert+display → xsetroot). |
| `tarsila-tema-apply.sh` | **Aplicador de tema completo.** Lê o tema salvo, aplica wallpaper (via `comum.sh`), tema da Dock, configuração do Polybar, e notifica o Openbox. |
| `tarsila-wallpaper-apply.sh` | **Aplicador de papel de parede.** Usa `pinta_fundo()` do `comum.sh`. |
| `tarsila-dock-apply.sh` | **Aplicador de tema da Dock.** Altera `dock.theme` e tamanho do ícone conforme altura da tela. |
| `tarsila-entrada-apply.sh` | **Aplicador de mouse/teclado.** Lê `~/.config/tarsila/<nome>` e aplica com `xinput set-prop`. |
| `tarsila-resolucao-apply.sh` | **Aplicador de resolução.** Usa `xrandr` para trocar o modo do monitor conectado. |
| `tarsila-pos-dock` | **Calculadora de posição.** Devolve (x, y) para uma janela de largura/altura dadas ficar encostada na Dock, na mesma referência das outras janelas do sistema. |

---

## 14. Outros Scripts e Utilitários

| Script | Descrição |
|---|---|
| `tarsila-perfil` (`usr/local/sbin/`) | Altera nome de exibição (GECOS via `chfn`) e foto do perfil (`/var/lib/tarsila/perfil.png`). Roda como root. |
| `tarsila-idioma` (`usr/local/sbin/`) | Troca o idioma do sistema: edita `/etc/locale.gen`, desliga o idioma anterior (exceto inglês), roda `locale-gen` e `update-locale`. |
| `tarsila-appfinder` | Buscador de aplicativos. Varre `.desktop` files de `/usr/share/applications` e `/usr/share/tarsila/applications`. Interface GTK3 com busca. |
| `tarsila-lixeira` | Gerenciador de lixeira GTK3. Lista arquivos em `~/.local/share/Trash/`. |
| `tarsila-calculadora` | Lançador que abre o `galculator`. |
| `tarsila-descanso` | Modo descanso: tela cheia com relógio mpv (`relogio.lua`) e bloqueio de entrada (`input.conf`). |
| `tarsila-descanso-vigia` | Daemon que monitora o tempo de atividade e sugere pausa. |
| `tarsila-barra-menu` | Menu do sistema no Polybar (genmon). Ações: Aplicativos, Ajustes, Loja, Arquivos, e ações de energia. |
| `tarsila-topbar-dots.py` | Indicador de estado das janelas (3 bolinhas). Lê o cache de wincount e o arquivo de estado da barra. |
| `tarsila-greeter-power-gtk.py` | Diálogo de desligar/reiniciar na tela de login. |
| `tarsila-obs` | Lançador do OBS Studio com sanitização de cenas. |
| `tarsila-ajusta-janela` | Tiling manual: ao arrastar para borda, redimensiona para metade da tela. |
| `tarsila-dispositivos` | Abre o gerenciador de arquivos focado em dispositivos. |
| `tarsila-boot-cursor.sh` | Aplica cursor personalizado durante o boot (Plymouth). |
| `tarsila-dock-manager` | Gerenciador de itens da Dock (adicionar/remover atalhos). |
| `tarsila-chromium` | Lançador do Chromium com perfil isolado e extensão Modo Cinema. |
| `tarsila-goto.sh` | Navegação rápida entre áreas de trabalho. |
| `tarsila-alt-tab.sh` | Alternador de janelas personalizado. |
| `tarsila-vermais.sh` | Abre o gerenciador de arquivos em modo de detalhes. |
| `tarsila-uma-janela` | Garante que só uma instância do app rode. |
| `tarsila-travar-janela` | Trava/desbloqueia a posição de uma janela. |

---

## 15. Configurações Estáticas

| Arquivo | Descrição |
|---|---|
| `usr/share/tarsila/picom.conf` | Configuração do compositor Picom (sombras, transparência, vsync). |
| `usr/share/tarsila/aquecer.txt` | Lista de aplicativos a serem pré-carregados no boot pelo `tarsila-aquecer@.service`. |
| `usr/share/tarsila/native-apps.txt` | Lista de aplicativos nativos do sistema. |
| `usr/share/tarsila/cinema-ext/manifest.json` | Manifesto da extensão Chrome MV3. |
| `usr/share/tarsila/cinema-ext/rules.json` | Regras declarativas da extensão. |
| `usr/share/themes/Tarsila-Contraste/` | Tema GTK de alto contraste. |
| `usr/share/icons/Tarsila-icons/` | Ícones personalizados para dispositivos e rede. |
| `usr/share/plank/themes/Tarsila*/` | Temas da Dock (Tarsila, Brasileiro, Escuro, Gelo, Marítimo). |
| `usr/share/plymouth/themes/tarsila-boot/` | Tema de boot com animação (36 frames) e throbber (30 frames). |
| `usr/share/tarsila/descanso/input.conf` + `relogio.lua` | Configuração do mpv para o modo descanso. |

---

## 16. Diagrama de Fluxo Resumido

```
┌─────────────────────────────────────────────────────────────┐
│                      BOOT / SYSTEMD                          │
│  tarsila-kmsg  tarsila-heartbeat  tarsila-aquecer            │
│       ↓              ↓ (30s)           ↓ (once)              │
│  /dev/kmsg →  /opt/tarsila-diag/     cache warm              │
│  kmsg.log      heartbeat.log                                │
│                                                              │
│  tarsila-atualizar.timer (3min após boot)                    │
│       ↓                                                      │
│  apt-get update && apt-get upgrade                           │
│                                                              │
│  zram-config-sync.timer (a cada 6h)                          │
│       ↓                                                      │
│  sync RAM → eMMC                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  LOGIN → SESSÃO OPENBOX                       │
│                                                              │
│  LightDM → Openbox → tarsila-dock + tarsila-barra + Picom     │
│           → Devilspie2 + xsettingsd + Dunst + tarsila-estado  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                ABERTURA DE APLICATIVO                         │
│                                                              │
│  tarsila-abrindo <app>                                       │
│       │                                                      │
│       ├→ tarsila_vaga.escolhe(w, h) → slot livre             │
│       ├→ tarsila_openbox.prepara(classe, x, y) → rc.xml      │
│       ├→ XGrabPointer (ampulheta + bloqueio de cliques)      │
│       ├→ subprocess.Popen(<app>)                             │
│       ├→ [se demorar >0.7s] tarsila_vetor.acende(vaga)      │
│       ├→ XDamage espera pintar                               │
│       ├→ tarsila_vaga.registra(slot, wid)                    │
│       ├→ tarsila_vetor.guarda_nascimento(chave, w, h, cls)  │
│       ├→ tarsila_vetor.apaga()                               │
│       ├→ tarsila_openbox.limpa() → remove regra              │
│       └→ XUngrabPointer                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    TARSILA EMAIL                              │
│                                                              │
│  UI (GTK ou WebView)                                         │
│       │                                                      │
│       ├→ inicia backend (se offline)                         │
│       ├→ inicia IDLE (se offline)                            │
│       │                                                      │
│  API Backend (:8475)                                         │
│       │                                                      │
│       ├── GET  /api/status     → config + avatar             │
│       ├── POST /api/sync       → imap_sync.sync_all()        │
│       ├── GET  /api/messages   → db.list_messages()          │
│       ├── POST /api/messages/send → smtp_send.send_mail()   │
│       ├── POST /api/messages/{id}/read → imap_sync.mark_read│
│       ├── POST /api/messages/{id}/star → imap_sync.toggle_star
│       ├── POST /api/messages/{id}/trash → imap_sync.move_to_trash
│       └── POST /api/drafts     → imap_sync.save_draft()     │
│                                                              │
│  IMAP IDLE (daemon separado)                                 │
│       │                                                      │
│       ├→ IMAP IDLE na INBOX                                  │
│       └→ notify-send ao detectar novo e-mail                │
│                                                              │
│  APIs externas:                                              │
│       │                                                      │
│       Gmail IMAP (imap.gmail.com:993)                        │
│       Gmail SMTP (smtp.gmail.com:465)                        │
│       Gravatar / Unavatar / Google Photos (avatar)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   AGENDA TARSILA                              │
│                                                              │
│  GTK3 UI (visões dia/semana/mês)                             │
│       │                                                      │
│       └→ Controller                                          │
│            │                                                 │
│            ├→ Store (SQLite local)                            │
│            ├→ GooglePlugin (OAuth 2.0 + PKCE)                │
│            │     │                                           │
│            │     ├→ accounts.google.com/o/oauth2/v2/auth     │
│            │     ├→ oauth2.googleapis.com/token              │
│            │     └→ www.googleapis.com/calendar/v3/*         │
│            │                                                 │
│            └→ Autosync a cada 180s                            │
│                 (full ou incremental syncToken)               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  MODO CINEMA (Chromium)                       │
│                                                              │
│  Extensão MV3                                                │
│       │                                                      │
│       ├→ [popup] → chrome.runtime.sendMessage({url, q})     │
│       │                                                      │
│       ├→ [background.js]                                     │
│       │     ├→ chrome.runtime.sendNativeMessage(             │
│       │     │      "br.tarsila.cinema", msg)                 │
│       │     ├→ declarativeNetRequest (UA mobile)             │
│       │     └→ contentScripts (ua-main.js + toque.js)        │
│       │                                                      │
│       └→ cinema_host.py (stdin/stdout JSON)                  │
│             └→ tarsila-abrindo mpv --fs --hwdec=auto-safe    │
│                   --ytdl=yes <url>                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   TARSILA STORE                               │
│                                                              │
│  GTK3 UI                                                     │
│       │                                                      │
│       ├→ tarsila_store_dados.py                              │
│       │     ├→ lê catalog-apps.js + catalog-jogos.js        │
│       │     ├→ dpkg-query (instalados)                       │
│       │     └→ sudo -n tarsila-pkg install/remove <pkg>     │
│       │                                                      │
│       ├→ tarsila_store_visual.py                             │
│       │     ├→ Capa (Cairo + GdkPixbuf)                      │
│       │     └→ tema claro/escuro (CSS)                       │
│       │                                                      │
│       └→ tarsila-pkg (sudo)                                  │
│             ├→ whitelist check                               │
│             ├→ apt-get install/remove -y                     │
│             └→ tarsila-atalho-criar                          │
│                                                              │
│  Protocolo tarsila://                                         │
│       │                                                      │
│       └→ tarsila-store-handler.sh                           │
│             ├→ valida URI + whitelist                        │
│             └→ pkexec apt-get install -y                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     PAINEL AJUSTES                            │
│                                                              │
│  GTK3 (7 categorias)                                         │
│       │                                                      │
│       ├── Internet                                            │
│       │     ├→ nmcli device status / radio wifi              │
│       │     ├→ subprocess: tarsila-wifi                      │
│       │     ├→ subprocess: nm-connection-editor              │
│       │     ├→ sudo tarsila-net-set                          │
│       │     └→ sudo tarsila-vpn-importar                     │
│       │                                                      │
│       ├── Aparência                                           │
│       │     ├→ tarsila-tema-apply.sh                         │
│       │     ├→ tarsila-wallpaper-apply.sh                    │
│       │     ├→ xsettingsd.conf + pkill -HUP                  │
│       │     └→ dunstrc + dunstctl reload                     │
│       │                                                      │
│       ├── Geral                                               │
│       │     ├→ sudo tarsila-perfil                           │
│       │     ├→ sudo tarsila-idioma                           │
│       │     ├→ sudo timedatectl set-*                        │
│       │     └→ sudo tarsila-atualizar                        │
│       │                                                      │
│       ├── Tela e Energia                                      │
│       │     └→ xrandr --query / --output --mode              │
│       │                                                      │
│       └── Dispositivos                                        │
│             └→ tarsila-entrada-apply.sh                      │
└─────────────────────────────────────────────────────────────┘
```