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

## O que NÃO mudou (já estava correto)

- **Agenda**: sync já roda em thread de fundo e publica via `GLib.idle_add`
  (`_sync_worker`, `save_event`, `delete_event`, `push_local_to_google`).
- **Store GTK**: não usa HTTP — `tarsila_store_dados.instalados()` faz um único
  `dpkg-query` batelado e as ações (`sudo -n tarsila-pkg`) rodam em thread.

## Pendências (futuro)

- **Store WebKit legado**: `GET /api/instalados` a cada 60s e `/api/tarefas` a
  cada 2.5s (polling). A versão GTK já substituiu isso; o backend WebKit pode
  ser desligado quando a migração estiver completa.
- **IDLE (`tarsila-email-idle.py`)**: o `fetch_one_new()` ainda usa `sync_folder`
  com `SEARCH` completo no primeiro toque (o caminho incremental só cobre o
  sync principal).

## Verificação

- `python3 -m py_compile` em todos os `.py` alterados: sem erro.
- `node --check` no `app.js`: sintaxe válida.
