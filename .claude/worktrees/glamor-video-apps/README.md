# Tarsila

**Uma interface amigável para quem nunca usou computador — sobre Debian.**

Tarsila transforma um Debian 13 (XFCE) em um ambiente pensado para usuários
totalmente leigos: zero linha de comando, uma dock com os aplicativos
essenciais, uma loja de aplicativos curada e uma barra superior simples com
espaços de trabalho em "bolinhas". Nasceu para rodar em tvboxes ARM64 com 2 GB
de RAM — então é leve por obrigação.

> **Status: BETA.** Este repositório contém a *camada gráfica* da Tarsila,
> extraída da imagem de referência (tvbox Amlogic S905W2, Debian 13 arm64,
> kernel 6.18). A instalação em um Debian ARM genérico funciona pelo
> `install.sh`, mas ainda está em validação — abra issues!

## O que vem

| Componente | O que faz |
|---|---|
| **Dock (Plank)** | Apps essenciais fixos, ordem gerenciável pelo próprio usuário |
| **Top bar** | Título da janela + botões fechar/restaurar, 3 workspaces em bolinhas, som/rede/sair/relógio |
| **Ver Mais** | Grade de todos os apps (yad) com Executar / Desinstalar / Gerenciar Dock |
| **Tarsila Store** | Loja local (web app) com catálogo curado de ~170 apps e jogos, instalação em 1 clique |
| **Ajustes** | Painel de configuração simplificado (temas, wallpaper, rede, conta) |
| **Temas** | Marítimo, Escuro, Brasileiro, Gelo + personalização com wallpaper próprio |
| **Instalador de .deb** | Duplo clique em um .deb → confirmação com senha → atalho criado |
| **Janelas comportadas** | devilspie2 garante que janelas novas abram no lugar certo |
| **Splash de boot** | Tema plymouth `tarsila-boot` (opcional, `--with-plymouth`) |

## Instalação

Em um Debian 13 (trixie) com acesso root:

```bash
git clone https://github.com/SEU_USUARIO/tarsila.git
cd tarsila
sudo ./install.sh <usuario>            # usuário leigo que vai usar a interface
sudo ./install.sh <usuario> --with-plymouth   # com splash de boot
```

Reinicie e faça login com o usuário indicado.

**Requisitos:** Debian 13, ~1 GB de espaço para as dependências, X11 (não
testado em Wayland). Alvo primário: ARM64; os scripts não dependem de
arquitetura.

## Estrutura do repositório

```
overlay/   → copiado sobre o sistema (/usr/local/bin, /opt/tarsila-store,
             /usr/share/tarsila, temas do Plank, ícones, plymouth, lightdm)
skel/      → configurações por usuário (painel XFCE, dock, autostart,
             devilspie2, gtk) + plank-dconf.ini (ordem da dock)
install.sh → instalador (beta)
```

## Filosofia

- **O usuário leigo nunca vê um terminal.** Instalação/remoção de apps passa
  por caminhos controlados (Store com whitelist, instalador gráfico de .deb).
- **Leve de verdade.** Roda em 2 GB de RAM; o daemon residente da sessão é um
  único loop de shell.
- **Nada de mágica escondida:** tudo é shell script e Python/GTK legível, em
  caminhos padrão do sistema.

## Roadmap

- [ ] Validar o instalador em SBCs comuns (Raspberry Pi, Orange Pi) e x86
- [ ] Empacotar como .deb
- [ ] Imagem pronta para gravar (golden image) da tvbox de referência
- [ ] Aceleração de vídeo (VPU) e WiFi no hardware de referência

## Licença

Ainda não definida — em breve.
