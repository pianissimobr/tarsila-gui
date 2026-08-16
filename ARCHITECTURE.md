# Arquitetura do Tarsila OS

Como as peças se encaixam, por que estão separadas assim, e o que cada
repositório pode ou não assumir sobre os outros.

Escrito em 16/08/2026. Se algo aqui divergir do código, o código está certo e
este arquivo está velho — conserte-o.

---

## A ideia central

O Tarsila OS **não é uma distribuição**. É uma camada gráfica mais um conjunto
de aplicativos, instaláveis sobre um Debian ARM que já existe.

A premissa é essa: a pessoa já tem um Debian rodando num aparelho ARM barato
(TV box Amlogic, celular Qualcomm) e instala o Tarsila por cima. Não há imagem
própria de sistema, não há kernel próprio, não há fork do Debian.

Isso força uma disciplina útil: **nada pode depender de hardware específico**.
O que é específico de chip (kernel, device tree, firmware, scripts de boot)
vive fora destes repositórios, por aparelho. O que está aqui roda igual em
qualquer ARM com Debian.

## Os seis repositórios

Um repositório monta o desktop. Os outros cinco são aplicativos, e cada um
gera um `.deb` que funciona sozinho.

```
                        ┌──────────────────┐
                        │   tarsila-gui    │   a camada gráfica:
                        │                  │   Openbox + Plank + picom,
                        │  overlay/        │   temas, Ajustes, Dock,
                        │  openbox/deploy/ │   OOBE, papel de parede
                        │  skel/           │
                        └────────┬─────────┘
                                 │ install.sh clona e instala
                 ┌───────────────┼───────────────┬───────────────┐
                 ▼               ▼               ▼               ▼
        ┌────────────────┐ ┌───────────┐ ┌──────────────┐ ┌─────────────┐
        │ tarsila-store  │ │tarsila-   │ │tarsila-      │ │tarsila-     │
        │                │ │email      │ │agenda        │ │chromium     │
        │ catálogo curado│ │cliente    │ │Google        │ │launcher +   │
        │ + tarsila-pkg  │ │Gmail GTK  │ │Agenda GTK    │ │extensões    │
        └────────────────┘ └───────────┘ └──────────────┘ └─────────────┘
                 ▲
                 │ usa o "motor" de atalhos
        ┌────────┴─────────────┐
        │ tarsila-app-         │  instalar .deb por duplo clique,
        │ management           │  desinstalar, e o "Ver mais"
        └──────────────────────┘
```

| Repositório | Pacote `.deb` | Versão | O que é |
|---|---|---|---|
| `tarsila-gui` | *(não é `.deb`)* | — | A camada gráfica. Instala por `install.sh`. |
| `tarsila-store` | `tarsila-store` | 4.0.0 | Loja de apps de catálogo curado |
| `tarsila-email` | `tarsila-email` | 2.1.0 | Cliente Gmail nativo em GTK3 |
| `tarsila-agenda` | **`agenda-tarsila`** | 4.0.0 | Google Agenda nativo em GTK3 |
| `tarsila-chromium` | `tarsila-chromium` | 2.0.0 | Chromium com flags e extensões |
| `tarsila-app-management` | `tarsila-app-management` | 1.1.0 | Instalador/desinstalador gráfico |

Todos os `.deb` são **`Architecture: all`**. Isso é correto e não é preguiça:
são Python e shell puros, sem nada compilado. O mesmo arquivo instala em
armhf, arm64 e x86 sem rebuild.

> **Inconsistência conhecida:** o pacote da agenda chama-se `agenda-tarsila`,
> invertido em relação aos outros quatro. Renomear quebra atualização de quem
> já tem, então precisa de `Provides`/`Replaces`/`Conflicts` bem-feitos, ou
> fica como está.

## Por que separado

O repositório único original acumulou tudo até virar impossível de raciocinar.
A separação resolve três coisas concretas:

1. **Cada app tem ciclo de vida próprio.** A agenda está na 4.0.0 e o
   `app-management` na 1.1.0 porque evoluíram em ritmos diferentes.
2. **Os apps servem fora do Tarsila.** Um `.deb` de `Architecture: all` sem
   dependência de hardware roda em qualquer Debian. O cliente de e-mail é útil
   sozinho.
3. **A camada gráfica pode ser trocada sem tocar nos apps.** A remoção da
   polybar mexeu em 61 arquivos do `tarsila-gui` e em **zero** dos outros
   cinco.

## Como o `tarsila-gui` monta o sistema

O `install.sh` roda como root sobre um Debian já instalado, em seis passos:

1. **Dependências** — `apt-get install` do núcleo gráfico: `xorg openbox dunst
   xsettingsd picom feh plank devilspie2 yad lightdm …`
2. **Apps Tarsila** — clona os cinco repositórios, roda o `build-deb.sh` de
   cada um e instala o `.deb` resultante. Se houver `.deb` em `pacotes/`, usa
   esses e nem toca na rede (modo offline).
3. **Arquivos de sistema** — despeja `overlay/` e `openbox/deploy/` na raiz.
4. **`skel/`** — configuração inicial do usuário (Openbox, Plank, devilspie2).
5. **Provisionamento** — `tarsila-user-provision` monta o `~/.config` da conta.
6. **OOBE** — primeiro uso.

### Os dois troncos que viram `/usr`

Aqui mora uma bagunça histórica que vale conhecer:

```
overlay/usr/local/bin/            33 scripts  →  tar para /
openbox/deploy/usr/local/bin/     12 scripts  →  cp -a para /usr/
openbox/deploy/home/…                         →  /usr/share/tarsila/openbox-home/
skel/.config/…                                →  ~/.config do usuário
```

Os dois primeiros terminam no mesmo lugar e **não têm regra** dizendo o que vai
onde. O `tarsila-dock-apply.sh` está num, o `tarsila-tela-estados` está no
outro, sendo o mesmo subsistema. Conferido em 16/08: **não há colisão de
arquivos** entre eles, então nada é sobrescrito em silêncio — é só arbitrário.
Unificar em `overlay/` é dívida técnica conhecida.

## Aquisição dos pacotes: o furo da premissa

> **Hoje só o autor consegue instalar o Tarsila.**

Os seis repositórios são privados. O `install.sh` clona com `GITHUB_TOKEN` e,
sem ele, imprime um aviso e segue sem instalar app nenhum:

```
AVISO: sem .deb locais e sem GITHUB_TOKEN
```

Isso contradiz a premissa de "qualquer um instala sobre o seu Debian ARM". As
saídas, em ordem de esforço:

- **`.deb` como assets de GitHub Releases** — públicos mesmo com o código
  privado. O `install.sh` vira `curl` + `dpkg -i`, sem token e sem buildar na
  máquina do usuário (que é lenta: é uma TV box de 2 GB).
- **Repositório APT próprio** — o caminho definitivo, com atualização pelo
  `apt upgrade` normal.
- **Manter `pacotes/*.deb` no repositório** — funciona hoje (o modo offline),
  mas engorda o git com binários.

## Contratos entre os pacotes

As integrações são **detectadas em tempo de execução**, nunca assumidas. Um
`.deb` instalado sozinho num Debian limpo tem que funcionar, com menos
recursos, e não quebrar.

| Quem | Precisa de | Se não existir |
|---|---|---|
| `app-management` | `tarsila-pos-dock` (do `tarsila-gui`) | Janelas abrem centralizadas em vez de encostadas na Dock |
| `app-management` | `tarsila-pkg` (da Store) | Remoção passa pelo `apt-get`, pedindo a senha |
| `app-management` | `plank` | Não mexe em ícone de Dock |
| `app-management` | `dconf` | Não reordena a Dock |
| Store | `tarsila-atalho-criar` | Instala a própria cópia *headless* (ver abaixo) |
| `tarsila-gui` | os cinco `.deb` | Desktop sobe sem os apps |

Isso está declarado como `Suggests`, não `Depends`, de propósito: `Depends`
puxaria o `tarsila-gui` inteiro para quem só quer o gerenciador de aplicativos.

### A pasta de atalhos curados

O ponto de encontro de todos eles:

```
/usr/share/tarsila/applications/     .desktop dos apps que aparecem na Dock
/usr/share/tarsila/games/            idem, aba de jogos
/usr/share/tarsila/icons/            ícones extraídos dos pacotes
/usr/share/tarsila/native-apps.txt   os que nunca podem ser desinstalados
```

Criada pelo `postinst` do `app-management`. O fluxo do duplo clique:

```
duplo clique no .deb
  → tarsila-deb-gui.py      caixa GTK, pede e valida a senha
    → sudo -S tarsila-deb-instalar        (root)
      → apt-get install
      → tarsila-atalho-criar <pacote>     (root)
        → /usr/share/tarsila/applications/<app>.desktop
          → tarsila-dock-apply.sh e o "Ver mais" leem daqui
```

Conferido em 16/08: **todos os componentes usam este mesmo caminho.** Nenhum
usa caminho na home do usuário.

### Privilégio: quem pode o quê sem senha

Regra geral: **nada de `NOPASSWD` genérico.** Cada regra aponta para um
executável de caminho fixo que valida a própria entrada.

| Regra | Vem de | Por que é segura |
|---|---|---|
| `/opt/tarsila-store/bin/tarsila-pkg` | Store | Só age em pacotes da whitelist |
| `/usr/local/sbin/tarsila-atualizar` | gui | Só faz `apt-get update/upgrade` |
| `/usr/local/sbin/tarsila-idioma` | gui | Só idiomas que a libc reconhece |
| `/usr/local/sbin/tarsila-vpn-importar` | gui | Só `nmcli connection import` |
| `/usr/local/bin/tarsila-perfil` | gui | Descobre a conta pelo `SUDO_USER` |
| `/usr/bin/timedatectl set-*` | gui | O próprio comando valida |

**Não existe, e não deve existir, regra para `apt-get remove`.** Ela daria a
qualquer processo do usuário o poder de remover o `sudo`, o `openbox` ou o
`network-manager`. Por isso remover um app fora do catálogo pede a senha numa
caixa gráfica (`tarsila-pedir-senha`), e apps do catálogo saem sem senha pelo
`tarsila-pkg`, que valida antes de agir.

## Problemas conhecidos

### Duplicação entre a Store e o `app-management`

A Store carrega em `motor/` uma cópia de dois arquivos do `app-management`:

| Arquivo | Situação |
|---|---|
| `tarsila-atalho-criar` | **Idêntico** nos dois repositórios |
| `tarsila-app-uninstall.sh` | **Divergiu**: Store 70 linhas, app-mgmt 90 |

O `postinst` da Store é guardado — só instala o motor se
`command -v tarsila-atalho-criar` falhar — então **não há sobrescrita
silenciosa**, e é um desenho deliberado: a Store precisa criar atalhos mesmo
sem a interface gráfica do `app-management`.

O custo é que os dois envelhecem separado. **Já aconteceu:** a correção de
16/08, que fez a desinstalação pedir a senha em vez de falhar calada com
`sudo -n`, entrou no `app-management` e **não** na cópia da Store. Num sistema
com a Store e sem o `app-management`, o bug continua.

Saídas possíveis: a Store declarar `Depends: tarsila-app-management`; ou o
motor virar um sexto pacote (`tarsila-motor`) do qual os dois dependem.

### A Store tem layout próprio

Os outros quatro seguem `DEBIAN/control` + `src/` espelhando o sistema. A Store
usa `backend/`, `desktop/`, `loja/`, `motor/`, `src/`, `etc/`, e gera o
`control` por *heredoc* dentro do `build-deb.sh` — não há arquivo para revisar.
Foi por isso que a duplicação acima passou despercebida numa varredura que
procurava só por `src/`.

Ela também mantém uma pasta `legado/` com a implementação antiga em WebKit.

### Outros

- **`Maintainer` inconsistente** entre os pacotes: `tarsila@local` (inválido),
  `tarsila@tarsila.org` (domínio provavelmente não registrado) e
  `adm@pianolabribeirao.com.br` (o real). Padronizar no último.
- **A Store não declara relação com o `app-management`**, embora instale o
  motor dele.
- **`clone.py`** (criador de LiveUSB) está solto na raiz do `tarsila-gui`, sem
  versionamento e sem casa.

## Onde as coisas ficam, no sistema instalado

```
/usr/local/bin/tarsila-*          scripts da sessão (gui + app-management)
/usr/local/lib/tarsila/           comum.sh e módulos Python compartilhados
/usr/local/share/tarsila/         tarsila_config.py (a tela de Ajustes)
/usr/local/sbin/tarsila-*         ajudantes que rodam como root
/usr/share/tarsila/applications/  atalhos curados que alimentam a Dock
/usr/share/tarsila/openbox-home/  modelo do ~/.config, usado no provisionamento
/opt/tarsila-store/               loja, catálogo, whitelist e o tarsila-pkg
/opt/tarsila-email/               cliente de e-mail
/opt/agenda-tarsila/              agenda
/etc/sudoers.d/tarsila-*          uma regra por ação privilegiada
~/.config/openbox/                rc.xml e autostart
~/.config/plank/dock1/launchers/  os .dockitem, na ordem da Dock
```

## Camada de chip: o que não está aqui

Por aparelho, fora destes repositórios:

- Kernel compilado para o SoC e o device tree (`.dtb`)
- Firmware de Wi-Fi, Bluetooth e GPU
- Scripts de boot e partição (EDL no Qualcomm, u-boot no Amlogic)
- Ajustes de vídeo específicos, como o `10-modeset-panfrost.conf` da Mali-G31

É o mesmo modelo de Armbian e postmarketOS: base agnóstica de hardware, com
uma camada fina por chip.
