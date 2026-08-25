> **⚠️ DOCUMENTO HISTÓRICO — este plano já foi executado.**
>
> O `Status: planejamento` abaixo é de antes da execução, em agosto de 2026.
> A separação aconteceu, mas com um nome diferente do previsto: o repositório
> que aqui se chama `tarsila-core` existe hoje como **`tarsila-gui`**.
>
> Os cinco repositórios de aplicativo saíram como planejado: `tarsila-store`,
> `tarsila-email`, `tarsila-agenda`, `tarsila-chromium` e
> `tarsila-app-management`.
>
> Para o estado atual, ver [`../MAPA.md`](../MAPA.md).

---

# Plano de Migração — Extração de Apps do Monorepo

**Objetivo:** Extrair Tarsila Store, Email e Agenda para repositórios independentes,
criar um pacote nativo de gerenciamento de apps, e transformar o monorepo atual
em `tarsila-core` (apenas o SO base).

**Data:** ago/2026 | **Status:** planejamento

---

## 1. Arquitetura Final

```
┌─────────────────────────────────────────────────────┐
│                   tarsila-core                       │
│  SO base: Openbox, polybar, Plank, Picom, Dunst,    │
│  xsettingsd, devilspie2, tema, scripts de sessão     │
│                                                      │
│  Depende de (instala automaticamente):               │
│  ├── tarsila-app-management (≥ 1.0)                  │
│  ├── tarsila-store (≥ versão)                        │
│  ├── tarsila-email (≥ versão)                        │
│  └── agenda-tarsila (≥ versão)                       │
└──────┬──────────┬──────────┬─────────────────────────┘
       │          │          │
       ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ app-mgmt │ │  store   │ │  email   │  agenda (autocontido)
│ (nativo) │ │          │ │          │
│          │ │ depende  │ │          │
│          │ │ de app-  │ │          │
│          │ │ mgmt ────┘ │          │
└──────────┘ └──────────┘ └──────────┘
```

---

## 2. Repositórios (5 gits independentes)

| Repo | Pacote .deb | Descritivo |
|---|---|---|
| `tarsila-core` (este) | `tarsila-core` | SO base: Openbox, polybar, scripts de sessão, temas, dock, utilitários |
| `tarsila-app-management` (novo) | `tarsila-app-management` | Nativo do SO: instalar .deb (duplo clique), desinstalar (botão direito), gerenciador visual de apps |
| `tarsila-store` (extrair) | `tarsila-store` | Catálogo comunitário, one-click install, `tarsila://` protocol |
| `tarsila-email` (extrair) | `tarsila-email` | Cliente de e-mail (GTK + backend REST + IMAP IDLE) |
| `tarsila-agenda` (extrair) | `agenda-tarsila` | Calendário (OAuth Google + CalDAV) |

---

## 3. Cadeia de Dependências

```
tarsila-core
├── Depends: tarsila-app-management (>= 1.0)
├── Depends: tarsila-store (>= versão)
├── Depends: tarsila-email (>= versão)
└── Depends: agenda-tarsila (>= versão)

tarsila-store
└── Depends: tarsila-app-management (>= 1.0)

tarsila-email
└── (autocontido — sem dependência de app-mgmt ou store)

agenda-tarsila
└── (autocontido — sem dependência de app-mgmt ou store)
```

**Por que o core instala todos?** Porque uma instalação limpa do Tarsila OS (`install.sh`)
deve entregar o sistema completo: SO + gerenciador de apps + loja + email + agenda.
O `install.sh` vira essencialmente:
```bash
apt-get install -y tarsila-core tarsila-app-management tarsila-store \
  tarsila-email agenda-tarsila
```

---

## 4. O que cada app expõe (contrato público)

### tarsila-app-management

| Binário | Caminho | Função |
|---|---|---|
| `tarsila-app-uninstall.sh` | `/usr/local/bin/` | Desinstalar .deb (botão direito no dock/appfinder) |
| `tarsila-appfinder-yad.sh` | `/usr/local/bin/` | Gerenciador visual de apps (lista, busca, lança, desinstala) |
| `tarsila-deb-gui.py` | `/usr/local/bin/` | Instalador gráfico de .deb (duplo clique) |
| `tarsila-deb-instalar` | `/usr/local/bin/` | Backend shell do instalador de .deb |

**Chamado por:** `.desktop` files (Desktop Actions), menu Openbox ("Ver mais aplicativos"),
Thunar (MIME handler para `.deb`).

**Não usa whitelist** — desinstala qualquer .deb que não seja app de sistema (`native-apps.txt`).
Se a Store estiver instalada e o `tarsila-pkg` disponível, delega para ele
(preserva a segurança do catálogo). Se não, usa `apt-get remove` direto.

### tarsila-store

| Binário | Caminho | Função |
|---|---|---|
| `tarsila-store` | `/usr/bin/` (symlink) | UI da loja (GTK3) |
| `tarsila-pkg` | `/opt/tarsila-store/bin/` | Wrapper de apt com whitelist |
| `tarsila-store-handler.sh` | `/opt/tarsila-store/` | Handler do protocolo `tarsila://` |
| `tarsila-deb-gui.py` | `/opt/tarsila-store/bin/` | (será movido para app-management) |

### tarsila-email

| Binário | Caminho | Função |
|---|---|---|
| `tarsila-email` | `/usr/local/bin/` | Launcher (setup ou GTK) |
| `tarsila-email-gtk.py` | `/opt/tarsila-email/bin/` | UI principal GTK3 |
| `tarsila-email-backend.py` | `/opt/tarsila-email/bin/` | API REST (porta 8475) |
| `tarsila-email-idle.py` | `/opt/tarsila-email/bin/` | Daemon IMAP IDLE + notify-send |
| `tarsila-email-setup.py` | `/opt/tarsila-email/bin/` | Assistente de configuração |
| `configurar-claws` | `/opt/tarsila-email/bin/` | Motor shell legado (accountrc + MH) |

### agenda-tarsila

| Binário | Caminho | Função |
|---|---|---|
| `agenda-tarsila` | `/usr/bin/` | Launcher → `/opt/agenda-tarsila/agenda_tarsila.py` |

---

## 5. O que sai do core (por app)

### Agenda — Extração (Esforço: 1-2h)

| Arquivo no overlay | Ação | Motivo |
|---|---|---|
| `overlay/opt/agenda-tarsila/agenda_tarsila.py` | **Deletar** | Vem do .deb |
| `overlay/usr/local/bin/tarsila-agenda` | **Deletar** | .deb instala `/usr/bin/agenda-tarsila` |

**Ajustes no core:**
- `overlay/usr/share/tarsila/applications/agenda-tarsila.desktop`:
  `Exec=/usr/local/bin/tarsila-abrindo tarsila-agenda` → `Exec=/usr/local/bin/tarsila-abrindo agenda-tarsila`
- `skel/plank-dconf.ini`: corrigir `05-agenda-google` → `05-agenda-tarsila` (nome do arquivo real)
- `install.sh`: adicionar `agenda-tarsila` na lista de pacotes apt

**O .deb já existe** em `pacotes/agenda-tarsila/`. Fontes canônicas já estão lá. Build:
```bash
dpkg-deb --build pacotes/agenda-tarsila
```

### Email — Extração (Esforço: 3-4h)

| Arquivo no overlay | Ação | Motivo |
|---|---|---|
| `overlay/opt/tarsila-email/` (árvore inteira) | **Deletar** | Vem do .deb |
| `overlay/usr/local/bin/tarsila-email` (launcher) | **Deletar** | .deb instala versão própria |
| `skel/.config/plank/dock1/launchers/15-configurar-claws.dockitem` | **Deletar** | Referência quebrada (.desktop não existe mais) |

**Ajustes no core:**
- `overlay/usr/share/tarsila/applications/tarsila-email.desktop`: verificar `Exec=` (já aponta pra `/usr/local/bin/tarsila-email` — OK se .deb instalar lá)
- `openbox/deploy/home/openbox/autostart`: limpar comentários mortos do claws-auto-trigger (linhas 82-86 → remover)
- `openbox/deploy/home/openbox/menu.xml`: item `Claws Mail` → `claws-mail` fica (é o cliente puro, não o assistente)
- `install.sh`: adicionar `tarsila-email` na lista de pacotes apt

**Correções no .deb (pendências):**
- `build-on-remote.sh`: referência quebrada ao `tarsila-email.desktop` (não existe dentro de `/opt/tarsila-email/`, está em `/usr/share/tarsila/applications/`)
- Unificar fork do `configurar-claws`: overlay (`protocol=1`, `config_version=5`, `--testar-imap`) vs .deb heredoc (`protocol=3`, sem `config_version`, sem `--testar-imap`). **Fonte canônica = .deb.**
- `pacotes/verificar.sh`: corrigir caminho de `overlay/usr/bin/configurar-claws*` → `overlay/opt/tarsila-email/bin/configurar-claws*`

### Store — Extração (Esforço: 6-8h)

| Arquivo no overlay | Ação | Motivo |
|---|---|---|
| `overlay/usr/local/lib/tarsila/tarsila_store_dados.py` | **Mover** para `/opt/tarsila-store/lib/` (via .deb) | Não pertence ao core |
| `overlay/usr/local/lib/tarsila/tarsila_store_visual.py` | **Mover** para `/opt/tarsila-store/lib/` (via .deb) | Não pertence ao core |
| `overlay/opt/tarsila-store/` (árvore inteira) | **Deletar** | Vem do .deb |
| `overlay/usr/local/bin/tarsila-store` (symlink) | **Deletar** | .deb cria |
| `overlay/usr/share/applications/tarsila-store.desktop` | **Deletar** | .deb instala |
| `overlay/usr/share/applications/tarsila-deb-installer.desktop` | **Deletar** | .deb instala |
| `overlay/usr/share/applications/tarsila-protocol.desktop` | **Deletar** | .deb instala |

**Ajustes no core:**
- `overlay/usr/share/tarsila/applications/tarsila-store.desktop`: verificar `Exec=` (já aponta pra `/usr/bin/tarsila-store` — OK)
- `install.sh:39`: remover `chmod 755 /opt/tarsila-store/bin/*` (desnecessário com .deb)
- `install.sh:42`: remover `install ... sudoers.d/tarsila-store` (arquivo não existe, .deb gera)
- `install.sh`: adicionar `tarsila-store` na lista de pacotes apt

**Ajustes no .deb da Store:**
- `sys.path.insert(0, "/usr/local/lib/tarsila")` → `sys.path.insert(0, "/opt/tarsila-store/lib")`
- Mover `tarsila_store_dados.py` e `tarsila_store_visual.py` para dentro do .deb
- `postinst`: verificar se `tarsila-app-uninstall.sh` existe (dependência de `tarsila-app-management`)

### App-Management — Criação (Esforço: 3-4h)

**Novo repositório.** Código que hoje está no core mas não pertence a ele.

**Arquivos que saem do core e vão para o novo repo:**

| De (overlay) | Para (novo repo) |
|---|---|
| `overlay/usr/local/bin/tarsila-app-uninstall.sh` | `src/usr/local/bin/tarsila-app-uninstall.sh` |
| `overlay/usr/local/bin/tarsila-appfinder-yad.sh` | `src/usr/local/bin/tarsila-appfinder-yad.sh` |
| `overlay/opt/tarsila-store/bin/tarsila-deb-gui.py` | `src/usr/local/bin/tarsila-deb-gui.py` |
| `overlay/opt/tarsila-store/bin/tarsila-deb-instalar` | `src/usr/local/bin/tarsila-deb-instalar` |
| `overlay/usr/share/applications/tarsila-deb-installer.desktop` | `src/usr/share/applications/` |

**Ajustes no `tarsila-app-uninstall.sh`:**
- Remover dependência hardcoded de `tarsila-pkg` + whitelist:
  ```bash
  # Se a Store está instalada, delega (respeita whitelist do catálogo)
  if [ -x /opt/tarsila-store/bin/tarsila-pkg ]; then
    sudo -n /opt/tarsila-store/bin/tarsila-pkg remove "$pkg"
  else
    # Sem Store: apt direto (só bloqueia apps de sistema)
    apt-get remove -y "$pkg"
  fi
  ```

**Ajustes no core:**
- `openbox/deploy/home/openbox/menu.xml:5`: `tarsila-appfinder-yad.sh` continua funcionando
  (será instalado pelo pacote app-management, que o core depende)
- `install.sh`: adicionar `tarsila-app-management` na lista de pacotes apt

---

## 6. O que fica no core (permanente)

### Scripts que NÃO saem do core

| Script | Motivo |
|---|---|
| `tarsila-dock-manager` | Gerencia dock (Plank), zero dependência da Store |
| `tarsila-dock-item.sh` | Adiciona/remove item do dock |
| `tarsila-dock-apply.sh` | Aplica tema/ordem do dock |
| `tarsila-icon-cache` | Cache de ícones, independente |
| `tarsila-abrindo` | Animação de abertura (cursor + vetor) — contrato público |
| `tarsila-uma-janela` | Single-instance — contrato público |
| `tarsila-aprender-janelas` | Aprende classes de janela — contrato público |
| `tarsila-vetor.py` | Dimensões de nascimento — contrato público |
| `tarsila-openbox.py` | Regras do Openbox — contrato público |
| `tarsila-config.py` | Painel de Ajustes |
| `tarsila-monitor.sh` | Daemon de sessão |
| Demais scripts de sessão | Polybar, wallpaper, tema, entrada, resolução, etc. |

### Diretórios que ficam

| Diretório | Função |
|---|---|
| `/usr/share/tarsila/applications/` | `.desktop` files curados (contrato público para apps) |
| `/usr/share/tarsila/native-apps.txt` | Lista de apps de sistema (imunes a desinstalação) |
| `/usr/local/lib/tarsila/` | Libs do core (`tarsila_vetor.py`, `tarsila_openbox.py`, `tarsila_vaga.py`, `comum.sh`) |
| `~/.config/plank/dock1/launchers/` | Ícones do dock (instalados pelo core) |
| `skel/plank-dconf.ini` | Ordem inicial do dock |

### O que o core garante como contrato

| Contrato | Como apps externos usam |
|---|---|
| `.desktop` em `/usr/share/tarsila/applications/` | Registro de atalho com `Exec=`, `StartupWMClass=`, `X-Tarsila-Nascimento=`, `X-Tarsila-Vetor-Se=`, `X-Package=`, Desktop Actions |
| `.dockitem` em `skel/.../launchers/` | Ícone no dock |
| `plank-dconf.ini` | Ordem inicial do dock |
| `tarsila-abrindo <comando>` | Animação de abertura |
| `tarsila-uma-janela <key> <regex> <comando>` | Single-instance |
| `notify-send` | Notificações desktop |
| `native-apps.txt` | Proteção contra desinstalação |

---

## 7. Ordem de Execução

### Fase 1 — App-Management (primeiro, é dependência)
1. Criar repositório `tarsila-app-management`
2. Mover 5 arquivos do core para o novo repo
3. Remover dependência de whitelist do `tarsila-app-uninstall.sh` (fallback para apt)
4. Criar `build-deb.sh` e gerar `.deb`
5. Adicionar `tarsila-app-management` no `install.sh` do core
6. Remover os 5 arquivos do overlay do core

### Fase 2 — Agenda (mais simples, ensina o processo)
1. Ajustar `.desktop` (`tarsila-agenda` → `agenda-tarsila`)
2. Corrigir `plank-dconf.ini` (nome do dockitem)
3. Remover `overlay/opt/agenda-tarsila/` e `overlay/usr/local/bin/tarsila-agenda`
4. Adicionar `agenda-tarsila` no `install.sh`
5. Atualizar `ARQUIVO-MORTO.md`

### Fase 3 — Email
1. Corrigir `build-on-remote.sh` (referência ao .desktop)
2. Unificar fork do `configurar-claws`
3. Corrigir `verificar.sh`
4. Limpar `autostart` (comentários mortos)
5. Remover arquivos do overlay
6. Adicionar `tarsila-email` no `install.sh`

### Fase 4 — Store (a mais complexa)
1. Mover `tarsila_store_*.py` para dentro do .deb
2. Ajustar `sys.path` no `tarsila-store-gtk.py`
3. Remover `chmod` e `sudoers` fantasmas do `install.sh`
4. Remover arquivos do overlay
5. Adicionar `tarsila-store` no `install.sh`

---

## 8. Riscos e Cuidados

| Risco | Mitigação |
|---|---|
| Quebrar "Desinstalar" se app-management não instalado | Core depende de app-management → `apt` recusa instalar core sem ele |
| Fork de `configurar-claws` entre overlay e .deb | Unificar ANTES de extrair Email, fonte canônica = .deb |
| Store referenciar libs em caminho errado | `sys.path.insert` usa caminho dentro de `/opt/tarsila-store/lib/` |
| `install.sh` quebrar ao referenciar pacotes não publicados | Publicar .debs em repo apt antes de atualizar `install.sh` |
| Ordem errada: extrair Store antes do app-management | App-management primeiro (Fase 1) — Store depende dele |
| `pacotes/verificar.sh` apontar para caminhos deletados | Atualizar após cada extração |

---

## 9. Linha do Tempo Estimada

| Fase | Esforço | Depende de |
|---|---|---|
| 1. App-Management | 3-4h | Nada |
| 2. Agenda | 1-2h | Fase 1 |
| 3. Email | 3-4h | Fase 1 |
| 4. Store | 6-8h | Fases 1, 2, 3 |
| **Total** | **13-18h** | |

As fases 2 e 3 podem ser paralelizadas (não dependem entre si).
A fase 4 deve ser a última — é a mais complexa e depende de todas as anteriores como prova de conceito.