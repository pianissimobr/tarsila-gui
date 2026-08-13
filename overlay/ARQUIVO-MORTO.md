# Arquivo Morto — Scripts e Componentes Removidos (ago/2026)

## 1. `tarsila-net.sh` (`usr/local/bin/`)

**Indicador do Polybar (genmon).** Exibia ícone de rede: X (sem internet), RJ45
(cabo), Wi-Fi com barras proporcionais ao sinal. Tooltip com descrição. Clique
abria `tarsila-wifi`. Usava ícones do tema quando disponíveis, fallback para
Papirus.

Referenciado apenas pelas configurações do painel XFCE (`skel/.config/xfce4/…`)
e não pelo polybar da sessão Openbox. Ficou como legado.

---

## 2. `tarsila-appfinder.sh` (`usr/local/bin/`)

**Launcher legado** (zenity, caminho `/root/.config/plank` fixo e `sudo apt
remove` direto). Já havia sido substituído pelo `tarsila-appfinder-yad.sh` —
os `.desktop` e o menu apontavam todos para o `-yad`.

---

## 3. `tarsila-visual-config.py` (`usr/local/bin/`)

**Configurador visual legado (GTK3).** Controlava tema, dock, barra e fonte.
Substituído pelo `tarsila-config` (web-based).

---

## 4. `configurar-claws` e `configurar-claws-gui` (`usr/bin/`)

**Configuradores do Claws Mail.** Configuração inicial (texto) e interface
gráfica de configuração de contas. A cópia em `/opt/tarsila-email/bin/`
permanece para uso interno do pacote de e-mail. O launcher do menu Openbox
foi removido.

---

## 5. `skel/.config/xfce4/` (árvore completa, ago/2026)

Configurações legadas de uma sessão XFCE que coexistia com Openbox. Removidas
porque o Openbox se mostrou estável (meses sem falhas) e os arquivos eram
puramente peso morto:

| Arquivo | Por que foi |
|---|---|
| `panel/genmon-36.rc` → `tarsila-title.sh` | Script não existe |
| `panel/genmon-37.rc` → `tarsila-dot1.sh` | Script não existe |
| `panel/genmon-38.rc` → `tarsila-dot2.sh` | Script não existe |
| `panel/genmon-39.rc` → `tarsila-dot3.sh` | Script não existe |
| `panel/genmon-40.rc` → `tarsila-restore-btn.sh` | Script não existe |
| `panel/genmon-41.rc` → `tarsila-close-btn.sh` | Script não existe |
| `panel/genmon-43.rc` → `tarsila-spacer-right.sh` | Script não existe |
| `panel/launcher-13` a `16` | `OnlyShowIn=XFCE`, sem utilidade no Openbox |
| `desktop/accels.scm` | Atalhos do xfdesktop (não roda) |
| `desktop/icons.screen0.yaml` | Ícones do xfdesktop (não roda) |
| `helpers.rc`, `help.rc` | Preferências XFCE inúteis |
| `xfce4-screenshooter` | Config de screenshot do XFCE |
| `xfwm4/` | Diretório vazio |
| `appfinder/bookmarks` | Arquivo vazio |
| `xfconf/.../xfce4-panel.xml.bak-*` | Backup do painel antigo (130 linhas) |

**Fallback real mantido:** os pacotes XFCE (`xfce4-session`, `xfwm4`,
`xfdesktop4`, `xfce4-panel`, `xfce4-settings`, `xfce4-power-manager`,
`xfce4-notifyd`, `xfce4-genmon-plugin`, `xfce4-pulseaudio-plugin`) continuam
no `install.sh`. Se o Openbox falhar, basta trocar a sessão no LightDM.

**Motivo:** custo é só disco (~22 MB) + tempo de upgrade. O autostart XDG não
roda na sessão Openbox, então nenhum desses daemons ocupa RAM ou CPU em uso
normal. Vale a rede de segurança.

---

## 6. `skel/.xinitrc` (ago/2026)

Chamava `exec startxfce4`. Inútil — o LightDM já gerencia a sessão via
`.xsession`, que força Openbox.

---

## 7. Extração para `tarsila-app-management` (ago/2026)

Scripts movidos do core para o repositório separado `tarsila-app-management`
(pacote nativo do Tarsila OS — instalador/desinstalador de .deb + AppFinder):

| Arquivo (no overlay) | Destino |
|---|---|
| `usr/local/bin/tarsila-app-uninstall.sh` | `tarsila-app-management` |
| `usr/local/bin/tarsila-appfinder-yad.sh` | `tarsila-app-management` |
| `opt/tarsila-store/bin/tarsila-deb-gui.py` | `tarsila-app-management` |
| `opt/tarsila-store/bin/tarsila-deb-instalar` | `tarsila-app-management` |
| `usr/share/applications/tarsila-deb-installer.desktop` | `tarsila-app-management` |
| `usr/share/applications/tarsila-appfinder-yad.desktop` | `tarsila-app-management` |
| `usr/share/applications/tarsila-appfinder.desktop` | **Deletado** (duplicata legada) |

Mudança de comportamento: os desinstaladores agora funcionam **sem a Store**.
Se a Store estiver instalada E o pacote estiver em sua whitelist, delegam
para ela; se não, usam `apt-get remove` direto.
Ver `PLANO-MIGRACAO.md` na raiz do repo.

---

## 8. Extração para `agenda-tarsila` (ago/2026)

App movido do core para o repositório `.deb` em `pacotes/agenda-tarsila/`.

| Arquivo (no overlay) | Destino |
|---|---|
| `opt/agenda-tarsila/agenda_tarsila.py` | `.deb` em `pacotes/agenda-tarsila/` |
| `usr/local/bin/tarsila-agenda` | **Deletado** (.deb instala `/usr/bin/agenda-tarsila`) |

Ajustes: `.desktop` corrigido (`Exec=tarsila-agenda` → `agenda-tarsila`;
nome do binário do .deb), `plank-dconf.ini` corrigido (`agenda-google` →
`agenda-tarsila`, nome real do dockitem), `install.sh` adiciona o pacote
com fallback para build local.

---

## 9. Extração para `tarsila-email` + limpeza do Claws (ago/2026)

App extraído do core para o repositório separado `tarsila-email/`. O cliente
é 100% standalone (GTK3, sem WebKit, sem Claws Mail).

**Resíduos do Claws removidos do código do email:**

| Arquivo/função | O que era |
|---|---|
| `bin/configurar-claws` | Motor shell legado (testava IMAP, abria navegador, gravava `accountrc`) |
| `bin/configurar-claws-gui` | Assistente GTK legado (3 telas, integração com Claws) |
| `lib/config.py:migrate_from_claws()` | Migração de credenciais do `~/.claws-mail/accountrc` |
| `lib/config.py:SKIP_CLAWS_MIGRATE` | Marcador de "Sair" para não reimportar Claws |
| `bin/tarsila-email-fetch-recent.py` | Download inicial para `~/Mail/inbox` (formato MH do Claws) |
| `bin/tarsila-email-app.py` | Shell WebKit2 (a antiga "capa visual" sobre o Claws) |

**Substituições no `tarsila-email-setup.py`:**
- Teste IMAP agora é direto em Python (`imaplib`), sem o motor shell
- Abertura da página de senha Google agora via `xdg-open`

**Outras mudanças:**
- `.desktop` ganhou `X-Package=tarsila-email` (desinstalação correta; antes
  resolvia o pacote errado via `dpkg -S tarsila-abrindo`)
- `menu.xml`: "Claws Mail" → "Tarsila Email"
- `autostart`: marcador `claws-mail-suite` e comentários mortos removidos
- `install.sh`: adiciona `tarsila-email` com fallback para .deb local
- `verificar.sh`: conferências `configurar-claws`/`agenda` removidas (apps
  extraídos têm o .deb como fonte canônica)