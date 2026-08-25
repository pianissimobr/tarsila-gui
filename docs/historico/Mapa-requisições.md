> **⚠️ DOCUMENTO HISTÓRICO — pode divergir do código atual.**
>
> Duas ressalvas:
>
> 1. O cliente de e-mail **não vive mais neste repositório** — foi para
>    `tarsila-email` na separação. Se estas rotas forem documentadas em
>    algum lugar, o lugar é lá.
> 2. As rotas mudaram em parte. Conferido em 25/08/2026: o backend tem hoje
>    `/api/bootstrap`, `/api/accounts`, `/api/drafts` e `/api/sync/status`,
>    que não constam abaixo. As principais (`/api/status`, `/api/folders`,
>    `/api/messages`) continuam valendo.

---

# Mapa de Rotas e Requisições — Tarsila

## 1. Cliente de Email (`tarsila-email`)

**Backend:** Servidor HTTP Python em `http://127.0.0.1:8475`

| Componente/Tela | Endpoint/Rota | Método | Frequência/Gatilho | Dados Retornados |
|---|---|---|---|---|
| Tela principal (mount) | `/api/status` | GET | Ao iniciar o app | `{configured, email, name, avatar, accounts[]}` — status da conta ativa |
| Tela principal (mount) | `/api/folders` | GET | Ao iniciar o app | `{folders: [{id, name, imap_name}]}` — lista de pastas IMAP |
| Tela principal (mount) | `/api/sync` | POST | Ao iniciar o app | `{ok, synced: {inbox: N, ...}}` — sincroniza emails novos |
| Tela principal (mount) | `/api/messages?folder=INBOX&page=1&limit=50` | GET | Após sync inicial | `{messages[], page, total, has_more}` — lista de emails |
| Lista de mensagens | `/api/messages?folder={f}&page={p}&limit=50` | GET | Ao clicar em pasta / paginação | `{messages[], page, total, has_more}` |
| Campo de busca | `/api/messages?folder={f}&q={termo}` | GET | Ao digitar (debounce 300ms) | `{messages[], page, total, has_more}` — resultados da busca |
| Leitura de email | `/api/messages/{id}?body=1` | GET | Ao clicar no email | `{message: {body_html, body_plain, ...}}` — corpo completo |
| Leitura de email | `/api/messages/{id}/read` | POST | Ao clicar no email | `{ok: true}` — marca como lido |
| Botão estrela | `/api/messages/{id}/star` | POST | Ao clicar no ícone ⭐ | `{ok, starred: bool}` — toggle favorito |
| Botão lixeira | `/api/messages/{id}/trash` | POST | Ao clicar no ícone 🗑 | `{ok: true}` — move para lixeira |
| Botão "Enviar" | `/api/messages/send` | POST | Ao clicar enviar no composer | `{ok: true}` — envia email via SMTP |
| Botão "Salvar rascunho" | `/api/drafts` | POST | Ao clicar salvar rascunho | `{ok: true}` — salva rascunho via IMAP APPEND |
| Botão "Sincronizar" | `/api/sync` | POST | Ao clicar botão sync | `{ok, synced: {folder: count}}` |
| Menu "Contas" | `/api/accounts` | GET | Ao clicar no menu de perfil | `{accounts: [{email, name, active, avatar}]}` |
| Botão "+ Adicionar conta" | `/api/accounts/open-setup` | POST | Ao clicar adicionar conta | `{ok: true}` — abre wizard de configuração |
| Linha de conta | `/api/accounts/switch` | POST | Ao clicar em outra conta | `{ok, email}` — troca conta ativa |
| Menu "Sair" | `/api/logout` | POST | Ao clicar em logout | `{ok: true}` — remove todas as contas |
| Avatar do perfil | `/api/avatar/local/{key}` | GET | Ao carregar perfil | PNG/JPEG binário — foto em cache local |

### Conexões IMAP/SMTP diretas (não HTTP):

| Componente | Conexão | Gatilho | Dados |
|---|---|---|---|
| Sincronização IMAP | `imap.gmail.com:993` (SSL) | Sync, fetch, flags, IDLE | Comandos IMAP: SEARCH, FETCH, STORE, APPEND, COPY |
| Envio SMTP | `smtp.gmail.com:465` (SSL) | Ao enviar email | Envio via SMTP |
| IMAP IDLE (daemon) | `imap.gmail.com:993` | Loop contínuo, timeout 540s | Notificações de novos emails em tempo real |

### Avatares externos:

| Componente | URL | Gatilho | Dados |
|---|---|---|---|
| Resolução de avatar | `https://unavatar.io/google/{email}` | Ao adicionar conta / carregar status | PNG/JPEG |
| Fallback 1 | `https://www.google.com/s2/photos/profile/{email}?sz=128` | Se unavatar.io falhar | PNG/JPEG |
| Fallback 2 | `https://www.gravatar.com/avatar/{md5}?d=mp&s=128` | Se Google Photos falhar | PNG/JPEG |

---

## 2. Loja de Aplicativos (`tarsila-store`)

**Backend:** Servidor HTTP Python em `http://127.0.0.1:8474` (modo WebKit legado)

| Componente/Tela | Endpoint/Rota | Método | Frequência/Gatilho | Dados Retornados |
|---|---|---|---|---|
| Tela principal (mount) | `/api/instalados` | GET | Ao iniciar + a cada 60s | `{instalados: ["pkg1", ...]}` — pacotes instalados |
| Botão "Instalar" | `/api/instalar/{pkg}` | POST | Ao clicar no botão instalar | `{}` — inicia instalação em background |
| Botão "Desinstalar" | `/api/desinstalar/{pkg}` | POST | Ao clicar no botão desinstalar | `{}` — inicia remoção em background |
| Progresso de tarefas | `/api/tarefas` | GET | Polling a cada 2.5s durante operações | `{tarefas: {pkg: {acao, estado}}}` — status instalação/remoção |

**Obs:** A versão GTK3 (`tarsila-store-gtk.py`) **não usa HTTP** — chama `tarsila_store_dados.py` diretamente e reescaneia dpkg a cada 60s via `GLib.timeout_add_seconds(60)`.

---

## 3. Agenda (`agenda-tarsila`)

| Componente/Tela | Endpoint/Rota | Método | Frequência/Gatilho | Dados Retornados |
|---|---|---|---|---|
| Botão "Conectar Google Agenda" | `https://accounts.google.com/o/oauth2/v2/auth` | GET (navegador) | Ao clicar conectar | Redireciona para `127.0.0.1:{porta}` com `?code=` |
| Callback local | `http://127.0.0.1:{porta_aleatoria}/` | Servidor HTTP temporário | Redirecionamento OAuth | Extrai `code` e `state` |
| Troca de token | `https://oauth2.googleapis.com/token` | POST | Após receber auth code | `{access_token, refresh_token, expires_in}` |
| Revogação | `https://oauth2.googleapis.com/revoke` | POST | Ao desconectar conta | Remove acesso do app |
| Sincronização automática | `https://www.googleapis.com/calendar/v3/calendars/{id}/events?syncToken=...` | GET | **A cada 180s (3min)** + refresh manual | `{items[], nextSyncToken}` |
| Criar evento | `https://www.googleapis.com/calendar/v3/calendars/{id}/events` | POST | Ao criar evento | Objeto do evento criado |
| Editar evento | `https://www.googleapis.com/calendar/v3/calendars/{id}/events/{id}` | PATCH | Ao editar evento | Objeto do evento atualizado |
| Excluir evento | `https://www.googleapis.com/calendar/v3/calendars/{id}/events/{id}` | DELETE | Ao excluir evento | `204 No Content` |

---

## 4. Extensão Chromium — Modo Cinema

| Componente/Tela | Endpoint/Rota | Gatilho | Dados |
|---|---|---|---|
| Botão "Modo Cinema" (injetado em páginas de vídeo) | `chrome.runtime.sendNativeMessage("br.tarsila.cinema", ...)` | Ao clicar no botão overlay | `{url, titulo, qualidade}` → Python host → abre `mpv` |
| Regra de User-Agent (youtube, facebook, instagram, x.com) | `declarativeNetRequest.updateDynamicRules()` | Ao instalar/extensão iniciar | Altera `User-Agent` para iPad Safari nesses domínios |

**Obs:** Não é HTTP — é Native Messaging do Chrome (stdin/stdout JSON) e regras declarativas de rede.

---

## 5. Nextcloud

| Componente | Endpoint/Rota | Método | Gatilho | Dados Retornados |
|---|---|---|---|---|
| Validação de credenciais | `{server}/ocs/v2.php/cloud/user` | GET (Basic Auth) | Ao configurar conexão | Dados do usuário (valida login) |
| Abrir arquivo online | `{server}/remote.php/webdav{path}` | PROPFIND | Ao executar `nc-edit-online.py` | `{fileid}` → abre no navegador |
| Montar WebDAV | `davs://{user}@{host}/remote.php/webdav/` | GVFS mount | Ao fazer login / autostart | Monta sistema de arquivos remoto |

---

## 6. Atualizações do Sistema

| Componente | Endpoint/Rota | Gatilho | Dados |
|---|---|---|---|
| `tarsila-atualizar.service` | Repositórios APT do Debian (HTTP/HTTPS) | Timer systemd + botão "Verificar e Instalar" | `apt-get update && apt-get upgrade` |

---

## Resumo de Intervalos de Polling Ativos

| Módulo | Intervalo | O que dispara |
|---|---|---|
| Loja (WebKit) — sincronização | **60 segundos** | `GET /api/instalados` |
| Loja (WebKit) — tarefas | **2.5 segundos** | `GET /api/tarefas` (apenas durante operações) |
| Loja (GTK3) — sincronização | **60 segundos** | Reescaneio dpkg (sem HTTP) |
| Agenda Google | **180 segundos** | `GET .../events?syncToken=...` |
| Email — IMAP IDLE | **540 segundos** (timeout) | Reconexão IDLE |
| Email — busca | **300ms** (debounce) | `GET /api/messages?q=...` |
| Loja — busca | **160ms** (debounce) | Filtro local (sem rede) |