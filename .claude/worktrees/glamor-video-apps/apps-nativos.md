# Tarsila — Apps nativos por categoria (substituindo web apps)

Estratégia: trocar web app pesado por app **nativo minimalista** por categoria.
**Lição medida na box:** "nativo" não basta — tem que ser MINIMALISTA (apps
full-featured carregam WebKit/GTK4/Qt e pesam igual WebView).

## Medições (PSS, app aberto, na box de referência 2 GB)
| App | RAM | Nota |
|---|---|---|
| Gmail web (WebView) | ~150-250 MB | baseline |
| Geary | 118 MB | embute WebKit (é WebView por dentro) |
| GNOME Calendar | 138 MB | GTK4/libadwaita/Evolution |
| Liferea | 119 MB | embute WebKit |
| Telegram Desktop | 209 MB | Qt full |
| **Claws Mail** | **26 MB** | GTK sem web — o ganho real |
| **tarsila-agenda** | **46 MB** | custom, ICS/CalDAV |
| **tarsila-noticias** | **41 MB** | custom, sem web engine |

## Implementado (na Dock, ícones Papirus)
- **E-mail** = Claws Mail (26 MB).
- **Arquivos/Drive** = Thunar + `gvfs-backends` (Google Drive/OneDrive/Nextcloud
  via GNOME Online Accounts).
- **Agenda** = `tarsila-agenda` (GTK3): lê URL .ics (segredo iCal do Google/
  Nextcloud/Outlook, sem OAuth) ou CalDAV (usuário+senha de app); expande
  recorrências (recurring_ical_events) e lista os próximos dias. Read-only.
  Config: `~/.config/tarsila/agenda-sources.json`.
- **Notícias** = `tarsila-noticias` (GTK3 + feedparser): lista de manchetes,
  abre a matéria no navegador do sistema (sem WebKit embutido). Feeds em
  `~/.config/tarsila/noticias-feeds.json` (padrão: G1, BBC Brasil).
- **Redes** = `tarsila-redes` (chooser) + `tarsila-rede-abrir`: abre Facebook/
  Instagram/X/WhatsApp com otimizações LEGÍTIMAS — user-agent **mobile**
  (versão leve; exceção: WhatsApp Web exige desktop), adblock (extensão
  `cinema-ext`), modo `--app` (PWA-like), **motor compartilhado** (FB/Insta/X
  num perfil; WhatsApp isolado), login persistente por rede. Sem API privada,
  sem modificar sites → não viola ToS.

## Por que redes sociais NÃO viram cliente nativo
Insta/Face/WhatsApp/X não têm API pública de usuário. Cachear CSS/JS não deixa
leve (o peso é EXECUTAR o JS + o motor web, não baixar). Cliente nativo
exigiria API privada = frágil + viola ToS + BANE a conta (WhatsApp bane na
hora). Por isso ficam no WebView otimizado (mobile UA + adblock + app + motor
compartilhado).

## Observação / próximos builds
- **Telegram**: nativizável de verdade (TDLib oficial), mas o client pronto
  (Telegram Desktop) = 209 MB → precisa de client minimal sobre TDLib (build).
- Agenda: escrita de eventos (CalDAV PUT) é enhancement futuro.

## Dependências (apt)
```
sudo apt install --no-install-recommends claws-mail gvfs-backends \
  python3-gi gir1.2-gtk-3.0 python3-icalendar python3-caldav \
  python3-recurring-ical-events python3-dateutil python3-feedparser
```
(GNOME Online Accounts opcional p/ Drive: `gnome-online-accounts`.)
