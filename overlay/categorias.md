# Categorias — Classificação do Código Tarsila OS

Classificação funcional de todos os scripts e componentes documentados em
`MAPA.md` e `Mapa-requisições.md`. Cada item recebe um **tipo**:

| Tag | Significado |
|---|---|
| `GTK3` | Interface gráfica em Python/GTK |
| `Py` | Python sem GUI |
| `Shell` | Script bash |
| `JS` | JavaScript (Web / extensão Chromium) |
| `Daemon` | Processo residente em segundo plano |
| `Service` | Unidade systemd |
| `Config` | Arquivo de configuração estática |
| `Lib` | Módulo/biblioteca |

---

## 1. Infraestrutura e Sessão Gráfica

A base sobre a qual tudo roda: display manager, gerenciador de janelas e os
processos que compõem a área de trabalho.

| Item | Tipo | Função |
|---|---|---|
| `etc/lightdm/lightdm.conf` | Config | Display manager da tela de login; inicia a sessão Openbox. |
| `etc/lightdm/lightdm-gtk-greeter.conf` | Config | Tema do greeter do LightDM. |
| Openbox | — | Gerenciador de janelas; decora, posiciona e gerencia janelas (política "Smart"). |
| Polybar | — | Barra superior (relógio, rede, bolinhas de estado, menu do sistema). |
| Plank | — | Dock inferior de aplicativos. |
| Picom | — | Compositor X11 (transparência, sombras, vsync). |
| Devilspie2 | Daemon | Aplica regras de janela no nascimento (ex.: Chromium maximizado). |
| xsettingsd | Daemon | Mantém temas GTK, fontes e modo escuro. |
| Dunst | Daemon | Notificações desktop. |
| `etc/pipewire/pipewire.conf.d/51-tarsila-fone.conf` | Config | Troca automática de saída de áudio ao conectar fone. |

---

## 2. Serviços de Sistema e Diagnóstico

Unidades systemd que cuidam de boot, cache, atualização e logs persistentes
(importante: logs vão para eMMC real, não zram).

| Item | Tipo | Função |
|---|---|---|
| `tarsila-heartbeat.service` | Service | A cada 30s grava métricas (load, memória, swap, GPU, processos) em log persistente para diagnóstico de travamentos. |
| `tarsila-atualizar.service` + `.timer` | Service | `apt-get update && upgrade` 3 min após o boot e via botão nos Ajustes. |
| `tarsila-kmsg.service` | Service | Lê `/dev/kmsg` e grava log persistente do kernel com rotação. |
| `tarsila-devfreq-gpu.service` | Service | Aplica política de frequência na GPU Mali (panfrost). |
| `tarsila-aquecer@.service` | Service | Pré-carrega apps pesados em cache antes do login (Xvfb, nice 19). |
| `zram-config-sync.service` + `.timer` | Service | Sincroniza diretórios em RAM (zram) para disco a cada 6h. |

---

## 3. Segurança e Privilégios

Regras `NOPASSWD` de caminho fixo — cada uma autoriza um único comando, sem
coringas amplos.

| Item | Tipo | Função |
|---|---|---|
| sudoers `tarsila-atualizar` | Config | Autoriza `/usr/local/sbin/tarsila-atualizar` (Ajustes → atualizar). |
| sudoers `tarsila-config` | Config | Autoriza `timedatectl` e `tarsila-net-set` (Ajustes). |
| sudoers `tarsila-idioma` | Config | Autoriza `/usr/local/sbin/tarsila-idioma` (troca de idioma). |
| sudoers `tarsila-perfil` | Config | Autoriza `/usr/local/sbin/tarsila-perfil` (nome/foto). |
| sudoers `tarsila-vpn` | Config | Autoriza `/usr/local/sbin/tarsila-vpn-importar` (VPN). |

---

## 4. Gerenciamento de Janelas

Tudo que controla **como e onde** as janelas nascem, se movem e se comportam.

| Item | Tipo | Função |
|---|---|---|
| `tarsila-abrindo` | Shell | Lançador universal: ampulheta, escolha de vaga, regra Openbox, espera pintar, aprendizado. |
| `tarsila_vaga.py` | Lib | 7 slots de posicionamento de janelas; ocupação conferida contra janelas vivas. |
| `tarsila_vetor.py` | Lib | Animação de abertura + cache de tamanhos medidos (`nascimento.txt`). |
| `tarsila_openbox.py` | Lib | Escreve/remove regras `<application>` de posição no `rc.xml` (com trava e troca atômica). |
| `tarsila-tela-estados` | Daemon | Desenha o retângulo de abertura (Cairo/Xlib) monitorando `tarsila-vetor.txt`. |
| `tarsila-monitor.sh` | Daemon | Consolida: contagem de janelas, estado "A" órfão, títulos amigáveis e `renice` — ciclo de 2s. |
| `tarsila-ajusta-janela` | Shell | Tiling manual: arrastar para borda redimensiona para metade da tela. |
| `tarsila-travar-janela` | Shell | Trava/desbloqueia a posição de uma janela. |
| `tarsila-uma-janela` | Shell | Garante uma única instância de um app. |
| `tarsila-goto.sh` | Shell | Navegação rápida entre áreas de trabalho. |
| `tarsila-alt-tab.sh` | Shell | Alternador de janelas personalizado. |

---

## 5. Aparência e Personalização

Temas, papel de parede, dock, resolução e periféricos de entrada.

| Item | Tipo | Função |
|---|---|---|
| `comum.sh` | Lib | Funções puras compartilhadas: tema, wallpaper, dock, altura da tela, `pinta_fundo()`. |
| `tarsila-tema-apply.sh` | Shell | Aplica tema completo (wallpaper + dock + polybar + notifica Openbox). |
| `tarsila-wallpaper-apply.sh` | Shell | Aplica papel de parede. |
| `tarsila-dock-apply.sh` | Shell | Aplica tema da dock e tamanho do ícone. |
| `tarsila-entrada-apply.sh` | Shell | Aplica mouse/teclado via `xinput`. |
| `tarsila-resolucao-apply.sh` | Shell | Troca resolução via `xrandr`. |
| `tarsila-pos-dock` | Shell | Calcula (x, y) para janela encostada na dock. |
| `tarsila-boot-cursor.sh` | Shell | Aplica cursor personalizado no boot (Plymouth). |
| `tarsila-dock-manager` | Shell | Gerencia itens da dock (adicionar/remover atalhos). |

---

## 6. Rede e Conectividade

Wi-Fi, indicador da barra, IP e VPN.

| Item | Tipo | Função |
|---|---|---|
| `tarsila-wifi` | GTK3 | Janela de conexões: scan `nmcli`, diálogo de senha, velocidade do link, estado de internet. |
| `tarsila-net-set` | Shell | Configuração IPv4 (DHCP ou manual) via `nmcli`. |
| `tarsila-vpn-importar` | Shell | Importa VPN (detecta WireGuard/OpenVPN) via `nmcli connection import`. |

---

## 7. Comunicação — Tarsila Email

Cliente de e-mail com backend HTTP local e três front-ends.

| Item | Tipo | Função |
|---|---|---|
| `tarsila-email-backend.py` | Py | Servidor HTTP local (`127.0.0.1:8475`) com as rotas `/api/*`. |
| `lib/api_client.py` | Lib | Cliente HTTP Python para a API local. |
| `lib/config.py` | Lib | Configuração multi-conta (JSON + senha ofuscada + migração do Claws). |
| `lib/db.py` | Lib | Cache SQLite de pastas/mensagens/sync (teto de 500). |
| `lib/imap_sync.py` | Lib | Sync IMAP (SPECIAL-USE, UTF-7 modificado, incremental, flags, rascunhos). |
| `lib/smtp_send.py` | Lib | Envio SMTP com anexos. |
| `lib/avatar.py` | Lib | Resolve avatar (unavatar/Google Photos/Gravatar) com cache local. |
| `tarsila-email-gtk.py` | GTK3 | UI nativa GTK3 (sem WebKit); gerencia backend e IDLE. |
| `tarsila-email-app.py` | GTK3 | Shell com `WebKit2.WebView` carregando a UI web. |
| `ui/index.html` + `ui/js/app.js` | JS | SPA vanilla que consome a API REST local. |
| `tarsila-email-setup.py` | GTK3 | Assistente de configuração (wizard de 2 telas). |
| `configurar-claws` | Shell | Motor legado de setup do Claws Mail. |
| `configurar-claws-gui` | GTK3 | Assistente GTK legado. |
| `tarsila-email-idle.py` | Daemon | Push de novos e-mails via IMAP IDLE + `notify-send`. |
| `tarsila-email-fetch-recent.py` | Py | Download inicial de e-mails para o Maildir do Claws. |

---

## 8. Produtividade — Agenda Tarsila

Calendário GTK3 com Google Agenda opcional.

| Item | Tipo | Função |
|---|---|---|
| `agenda_tarsila.py` | GTK3 | Arquivo único (~3k linhas): UI (dia/semana/mês), modelo SQLite, OAuth 2.0+PKCE, sync full/incremental, eventos locais. |

**Subcomponentes internos:** `MainWindow` (UI), `Store`/`Ev` (modelo SQLite),
`GooglePlugin` (OAuth + Google Calendar API), `Controller` (orquestração e
autosync 180s).

---

## 9. Mídia — Modo Cinema e Descanso

| Item | Tipo | Função |
|---|---|---|
| `cinema-ext/background.js` | JS | Service Worker MV3: Native Messaging, regras de User-Agent e content scripts. |
| `cinema-ext/ua-main.js` | JS | Simula dispositivo móvel (userAgent, platform, tela). |
| `cinema-ext/toque.js` | JS | Adapta eventos de toque/scroll. |
| `cinema-ext/sites-mobile.js` | JS | Lista de domínios com versão mobile. |
| `cinema-ext/fundo.js` `imagens.js` `modo_leve.js` `youtube.js` `cinema.js` | JS | Scripts auxiliares e regras de conteúdo. |
| `cinema_host.py` | Py | Host nativo: abre URL no `mpv` (fullscreen, hwdec, yt-dlp). |
| `tarsila-descanso` | Shell | Modo descanso: relógio em tela cheia + bloqueio de entrada (mpv). |
| `tarsila-descanso-vigia` | Daemon | Monitora tempo de atividade e sugere pausa. |

---

## 10. Distribuição de Software — Tarsila Store

| Item | Tipo | Função |
|---|---|---|
| `tarsila-store-gtk.py` | GTK3 | Interface da loja (Apps/Jogos, busca, temas, modal de detalhes). |
| `tarsila_store_dados.py` | Lib | Catálogo, estado do dpkg e ações de instalação em thread. |
| `tarsila_store_visual.py` | Lib | Renderização de capas (Cairo) e selos. |
| `tarsila-pkg` | Shell | Wrapper seguro para apt (valida whitelist; roda como root NOPASSWD). |
| `tarsila-store-handler.sh` | Shell | Handler do protocolo `tarsila://` (valida URI + whitelist + `pkexec`). |
| `tarsila-atalho-criar` | Shell | Gera/ajusta atalhos `.desktop` após instalar. |
| `tarsila-deb-gui.py` | GTK3 | Instalador de `.deb` avulso (mostra metadados via `dpkg-deb`). |
| `tarsila-deb-instalar` | Shell | Executa `dpkg -i` com `pkexec`. |
| `loja/` | — | Assets web: HTML/CSS/JS, catálogos, ~130 capas PNG e ícones. |

---

## 11. Configuração do Sistema — Painel de Ajustes

| Item | Tipo | Função |
|---|---|---|
| `tarsila_config.py` | GTK3 | Painel estilo "System Preferences" com 7 categorias fixas (construção lazy). |
| `tarsila-perfil` | Shell | Altera nome (GECOS via `chfn`) e foto do perfil (root). |
| `tarsila-idioma` | Shell | Troca idioma (`locale.gen` + `locale-gen` + `update-locale`) (root). |
| `tarsila-atualizar` | Shell | `apt-get update && upgrade` (chamado pelo botão "Verificar e Instalar"). |

**Categorias do painel:** Geral, Internet, Aparência, Som e Notificações,
Tela e Energia, Dispositivos, Acessibilidade e Avançado (oculto).

---

## 12. Utilitários e Acessórios

| Item | Tipo | Função |
|---|---|---|
| `tarsila-appfinder` | GTK3 | Buscador de aplicativos (varre `.desktop` files). |
| `tarsila-lixeira` | GTK3 | Gerenciador de lixeira. |
| `tarsila-calculadora` | Shell | Lançador do `galculator`. |
| `tarsila-dispositivos` | Shell | Abre o gerenciador de arquivos focado em dispositivos. |
| `tarsila-vermais.sh` | Shell | Abre gerenciador de arquivos em modo detalhes. |
| `tarsila-barra-menu` | Shell | Menu do sistema no Polybar (genmon). |
| `tarsila-topbar-dots.py` | Py | Indicador de estado das janelas (3 bolinhas). |
| `tarsila-greeter-power-gtk.py` | GTK3 | Diálogo de desligar/reiniciar na tela de login. |
| `tarsila-obs` | Shell | Lançador do OBS Studio com sanitização de cenas. |
| `tarsila-chromium` | Shell | Lançador do Chromium com perfil isolado + Modo Cinema. |

---

## 13. Cloud — Nextcloud

| Item | Tipo | Função |
|---|---|---|
| Validação de credenciais | Py | `GET {server}/ocs/v2.php/cloud/user` (Basic Auth). |
| `nc-edit-online.py` | Py | `PROPFIND` em `remote.php/webdav{path}` para abrir arquivo no navegador. |
| Montagem WebDAV | — | `davs://.../remote.php/webdav/` via GVFS (login/autostart). |

---

## 14. Arquivos de Configuração e Assets

| Item | Tipo | Função |
|---|---|---|
| `picom.conf` | Config | Compositor (sombras, transparência, vsync). |
| `aquecer.txt` | Config | Lista de apps pré-carregados no boot. |
| `native-apps.txt` | Config | Lista de aplicativos nativos. |
| `cinema-ext/manifest.json` | Config | Manifesto da extensão Chrome MV3. |
| `cinema-ext/rules.json` | Config | Regras declarativas da extensão. |
| `Tarsila-Contraste/` | Config | Tema GTK de alto contraste. |
| `Tarsila-icons/` | Config | Ícones personalizados (dispositivos e rede). |
| `plank/themes/Tarsila*/` | Config | Temas da dock (Tarsila, Brasileiro, Escuro, Gelo, Marítimo). |
| `plymouth/themes/tarsila-boot/` | Config | Tema de boot com animação e throbber. |
| `descanso/input.conf` + `relogio.lua` | Config | Configuração do mpv para o modo descanso. |

---

## Visão Transversal: Requisições de Rede

As rotas documentadas em `Mapa-requisições.md`, agrupadas por natureza:

| Categoria | Origem | Destino | Intervalo/Evento |
|---|---|---|---|
| Email — API local | GTK/Web | `127.0.0.1:8475` | Sob demanda (busca com debounce 300ms) |
| Email — IMAP | backend | `imap.gmail.com:993` | Sync, fetch, flags, IDLE (timeout 540s) |
| Email — SMTP | backend | `smtp.gmail.com:465` | Envio |
| Email — avatares | backend | unavatar.io / Google Photos / Gravatar | Adicionar conta / status |
| Loja — API local (legado WebKit) | WebView | `127.0.0.1:8474` | 60s + 2.5s (tarefas) |
| Agenda — OAuth | GTK | `accounts.google.com` / `oauth2.googleapis.com` | Conectar / refresh token |
| Agenda — Calendar API | GTK | `www.googleapis.com/calendar/v3/*` | Autosync 180s |
| Modo Cinema — Native Messaging | Chromium | `cinema_host.py` (stdin/stdout) | Clique |
| Nextcloud | systema | `{server}/ocs` e `remote.php/webdav` | Configurar / abrir / montar |
| Atualizações | systemd/GTK | Repositórios APT Debian | Timer (boot+3min) / botão |
