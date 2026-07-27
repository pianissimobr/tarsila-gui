#!/usr/bin/env python3
"""Ajustes — Tarsila OS.

Painel de configuração para usuário leigo, inspirado no modelo Apple:

* 8 categorias fixas com nomes de tarefa ("Internet", "Aparência"),
  nunca nomes de subsistema ("Rede e Internet", "Personalização").
* Zero jargão nos títulos: nada de NTP, APT, xfconf, kernel ou nomes de
  ferramentas como decisão de navegação. Nome técnico só em subtítulo,
  quando ajuda alguém no suporte por telefone.
* Hardware ausente = linha ausente. Sem "bateria não detectada" em TV box.
* Nenhuma ação de root sem clique explícito do usuário. Elevação via
  "sudo -n" com regra NOPASSWD restrita (/etc/sudoers.d/tarsila-config)
  em vez de pkexec/polkit — este equipamento não tem agente gráfico de
  autenticação para XFCE, então pkexec sempre falhava.
* Páginas construídas sob demanda (lazy) — importa em ARM com pouca RAM.
* Sidebar de ordem fixa: memória espacial vale mais que "favoritos".
* Opções avançadas ocultas; desbloqueio silencioso com 7 toques na versão.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

GLib.set_prgname("tarsila-config")
GLib.set_application_name("Ajustes")

import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "tarsila-config"
STATE_FILE = CONFIG_DIR / "state.json"
WALLPAPER_DEFAULT = "/usr/share/backgrounds/tarsila-wallpaper.png"

# Temas visuais (Aparência > Tema). Aplicados por tarsila-tema-apply.sh;
# a escolha fica em ~/.config/tarsila/tema. O "personalizado" não entra
# no seletor (tem linha própria com escolha de imagem).
TEMAS_VISUAIS = [
    ("padrao", "Padrão",
     "Visual claro com a barra superior transparente", WALLPAPER_DEFAULT),
    ("maritimo", "Marítimo",
     "Tons de azul-petróleo", "/usr/share/tarsila/wallpapers/tema-maritimo.png"),
    ("escuro", "Escuro",
     "Preto e grafite, descanso para os olhos", "/usr/share/tarsila/wallpapers/tema-escuro.png"),
    ("brasileiro", "Brasileiro",
     "Verde e amarelo", "/usr/share/tarsila/wallpapers/tema-brasileiro.png"),
]
TEMA_PERSONALIZADO = ("personalizado", "Personalizado",
                      "Sua imagem de fundo com a barra superior clara", None)

# Fusos do Brasil pós-2019 (sem horário de verão). A lista de sudoers
# (/etc/sudoers.d/tarsila-config) precisa ter uma linha NOPASSWD para
# cada um destes — ver 07-config-panel.sh no provisionamento.
TIMEZONES_BR = [
    ("America/Sao_Paulo", "Brasília (a maioria do Brasil)"),
    ("America/Manaus", "Manaus (AM, RO, RR, MT)"),
    ("America/Rio_Branco", "Rio Branco (AC)"),
    ("America/Fortaleza", "Fortaleza (CE e parte do Nordeste)"),
    ("America/Noronha", "Fernando de Noronha"),
]


# --------------------------------------------------------------------------
# Utilidades de sistema
# --------------------------------------------------------------------------

def which(cmd):
    return shutil.which(cmd) is not None


def run_bg(argv):
    """Dispara uma ferramenta gráfica externa sem bloquear a UI."""
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False


def run_ok(argv, timeout=8):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)


def xfconf_get(channel, prop, default=None):
    ok, out, _ = run_ok(["xfconf-query", "-c", channel, "-p", prop])
    return out if ok else default


def xfconf_set(channel, prop, value, vtype="string", create=False):
    argv = ["xfconf-query", "-c", channel, "-p", prop, "-s", str(value)]
    if create:
        argv += ["-n", "-t", vtype]
    return run_ok(argv)[0]


def load_state():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"dev_unlocked": False}


def save_state(state):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except OSError:
        pass


# --------------------------------------------------------------------------
# Widgets auxiliares
# --------------------------------------------------------------------------

# Idiomas oferecidos, com o nome escrito na propria lingua -- quem procura
# "Espanol" nao reconhece "es_ES.UTF-8". O ingles esta aqui e NUNCA e removido
# do sistema: e a lingua de recurso quando um programa nao tem traducao.
IDIOMAS = [
    ("pt_BR.UTF-8", "Português (Brasil)"),
    ("pt_PT.UTF-8", "Português (Portugal)"),
    ("en_US.UTF-8", "English (United States)"),
    ("es_ES.UTF-8", "Español (España)"),
    ("es_AR.UTF-8", "Español (Argentina)"),
    ("fr_FR.UTF-8", "Français (France)"),
    ("it_IT.UTF-8", "Italiano (Italia)"),
    ("de_DE.UTF-8", "Deutsch (Deutschland)"),
]


def nome_do_idioma(codigo):
    """"pt_BR.UTF-8" -> "Português (Brasil)". Sem isto a tela mostrava o
    codigo cru, que nao diz nada para quem so quer saber que idioma esta
    usando."""
    if not codigo:
        return "—"
    for cod, nome in IDIOMAS:
        if cod == codigo or cod.split(".")[0] == codigo.split(".")[0]:
            return nome
    return codigo


def reiniciar_barra():
    """Faz a barra de cima recarregar.

    Antes isto chamava "xfce4-panel -r". O pacote esta instalado, mas quem
    desenha a barra deste sistema e o polybar -- entao a chamada morria com
    "org.xfce.Panel was not provided by any .service files" e o usuario levava
    um dialogo de erro na cara toda vez que mexia na hora ou no fuso.
    O polybar recarrega ao receber SIGUSR1."""
    run_bg(["pkill", "-USR1", "-x", "polybar"])


# Uma cidade por faixa horária, não os 485 fusos que o sistema conhece --
# ninguém escolhe entre "America/Argentina/Catamarca" e "America/Cordoba".
# Nas quatro faixas que são do Brasil a referência é brasileira; nas outras,
# uma cidade que qualquer pessoa reconhece.
# O deslocamento NÃO está escrito aqui de propósito: é calculado na hora, se
# não o horário de verão de outros países deixaria o rótulo mentindo.
FUSOS = [
    ("Pacific/Pago_Pago",   "Pago Pago"),
    ("Pacific/Honolulu",    "Honolulu"),
    ("America/Anchorage",   "Anchorage"),
    ("America/Los_Angeles", "Los Angeles"),
    ("America/Denver",      "Denver"),
    ("America/Mexico_City", "Cidade do México"),
    ("America/Rio_Branco",  "Rio Branco"),
    ("America/Manaus",      "Manaus"),
    ("America/Sao_Paulo",   "São Paulo"),
    ("America/Noronha",     "Fernando de Noronha"),
    ("Atlantic/Azores",     "Açores"),
    ("Europe/London",       "Londres"),
    ("Europe/Paris",        "Paris"),
    ("Europe/Athens",       "Atenas"),
    ("Europe/Moscow",       "Moscou"),
    ("Asia/Dubai",          "Dubai"),
    ("Asia/Karachi",        "Carachi"),
    ("Asia/Dhaka",          "Daca"),
    ("Asia/Bangkok",        "Bangkok"),
    ("Asia/Shanghai",       "Xangai"),
    ("Asia/Tokyo",          "Tóquio"),
    ("Australia/Sydney",    "Sydney"),
    ("Pacific/Noumea",      "Numeá"),
    ("Pacific/Auckland",    "Auckland"),
]


def _deslocamento(zona):
    """O fuso BASE da zona, sem horário de verão.

    Usar o deslocamento do momento deixaria a lista torta metade do ano: em
    julho o horário de verão do hemisfério norte empurra Denver para -06, onde
    já está a Cidade do México, e Atenas para +03, onde já está Moscou -- duas
    colisões e dois buracos. Descontando o horário de verão sai uma faixa por
    hora, que é o que se espera de "GMT-3". É assim que Windows e Android
    rotulam."""
    try:
        agora = datetime.now(dt_timezone.utc).astimezone(ZoneInfo(zona))
        desloc = agora.utcoffset()
        verao = agora.dst()
    except Exception:
        return None
    if desloc is None:
        return None
    if verao:
        desloc -= verao
    return int(desloc.total_seconds()) // 60


def listar_fusos(atual=""):
    """As faixas horárias, como (id, "(GMT-03:00) São Paulo").

    Se o computador estiver num fuso fora da lista, ele entra também -- assim
    a janela nunca deixa de mostrar onde a máquina realmente está."""
    escolhas = list(FUSOS)
    if atual and atual not in dict(escolhas):
        escolhas.append((atual, atual.split("/")[-1].replace("_", " ")))
    itens = []
    for zona, cidade in escolhas:
        minutos = _deslocamento(zona)
        if minutos is None:
            continue
        sinal = "+" if minutos >= 0 else "-"
        horas, resto = divmod(abs(minutos), 60)
        itens.append((minutos, zona,
                      "(GMT%s%02d:%02d) %s" % (sinal, horas, resto, cidade)))
    itens.sort(key=lambda t: (t[0], t[2]))
    return [(z, rot) for _, z, rot in itens]


def make_card(title):
    frame = Gtk.Frame()
    frame.get_style_context().add_class("tarsila-card")
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    frame.add(outer)

    if title:
        head = Gtk.Label(xalign=0)
        head.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        head.set_margin_start(16)
        head.set_margin_top(12)
        head.set_margin_bottom(6)
        outer.pack_start(head, False, False, 0)

    listbox = Gtk.ListBox()
    listbox.set_selection_mode(Gtk.SelectionMode.NONE)
    listbox.get_style_context().add_class("tarsila-list")
    outer.pack_start(listbox, False, False, 0)
    return frame, listbox


def add_row(listbox, icon_name, title, subtitle="", widget=None):
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    row.set_activatable(False)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_margin_top(10)
    box.set_margin_bottom(10)
    row.add(box)

    if icon_name:
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR)
        box.pack_start(img, False, False, 0)

    text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.pack_start(text_box, True, True, 0)
    lbl = Gtk.Label(xalign=0)
    lbl.set_markup(GLib.markup_escape_text(title))
    lbl.set_line_wrap(True)
    text_box.pack_start(lbl, False, False, 0)
    if subtitle:
        sub = Gtk.Label(xalign=0)
        sub.set_markup(f'<small><span alpha="65%">{GLib.markup_escape_text(subtitle)}</span></small>')
        sub.set_line_wrap(True)
        text_box.pack_start(sub, False, False, 0)

    if widget is not None:
        widget.set_valign(Gtk.Align.CENTER)
        box.pack_start(widget, False, False, 0)

    listbox.add(row)
    row.show_all()
    return row


def open_tool_button(label, argv):
    """Botão '›' que abre uma ferramenta nativa. Retorna None se a
    ferramenta não existe — quem chama decide omitir a linha inteira,
    em vez de mostrar um controle morto."""
    if which(argv[0]):
        btn = Gtk.Button(label=label)
        btn.connect("clicked", lambda *_: run_bg(argv))
        return btn
    return None


def add_tool_row(listbox, icon, title, subtitle, argv, btn_label="Abrir ›"):
    """Adiciona a linha apenas se a ferramenta existir neste equipamento."""
    btn = open_tool_button(btn_label, argv)
    if btn is None:
        return None
    return add_row(listbox, icon, title, subtitle, btn)


# --------------------------------------------------------------------------
# Índice de busca global — estático, com sinônimos coloquiais.
# Registrado antes das páginas existirem (elas são lazy); a ativação
# navega para a categoria certa, que é curta o bastante após a
# consolidação para o usuário achar o ajuste de vista.
# --------------------------------------------------------------------------

SEARCH_TOPICS = [
    ("internet", "Wi-Fi e internet", "wifi internet conexao sem internet rede cabo roteador senha do wifi"),
    ("internet", "Modo avião", "modo aviao desligar wifi radio"),
    ("internet", "VPN e redes salvas", "vpn proxy ip dns rede salva"),
    ("internet", "IP do cabo de rede", "ip fixo manual cabo ethernet rj45 gateway dns configurar rede"),
    ("aparencia", "Tema", "tema cores estilo visual maritimo escuro brasileiro personalizar barra"),
    ("aparencia", "Papel de parede", "papel de parede plano de fundo wallpaper imagem foto tela de fundo"),
    ("aparencia", "Modo escuro", "modo escuro tema escuro claro dark cor aparencia noturno"),
    ("aparencia", "Tamanho do texto", "texto grande letra grande fonte aumentar letra zoom"),
    ("aparencia", "Ícones na área de trabalho", "icones area de trabalho desktop atalhos sumiu"),
    ("som", "Volume", "som volume audio alto falante caixa mudo sem som baixo alto"),
    ("som", "Fones e microfone", "fone microfone entrada saida headset nao funciona"),
    ("som", "Notificações", "notificacao aviso balao nao perturbe silenciar"),
    ("tela", "Tela e resolução", "tela monitor resolucao brilho segundo monitor tv espelhar itens grandes pequenos"),
    ("tela", "Energia e suspensão", "energia suspender dormir desligar tela apagar economizar"),
    ("dispositivos", "Mouse", "mouse ponteiro lento rapido touchpad rolagem botao"),
    ("dispositivos", "Teclado", "teclado layout acento cedilha idioma tecla"),
    ("dispositivos", "Impressora", "impressora imprimir scanner digitalizar papel"),
    ("dispositivos", "Câmera", "camera webcam video chamada filmar nao funciona imagem"),
    ("dispositivos", "Microfone", "microfone mic voz gravar nao funciona headset"),
    ("dispositivos", "USB e pendrive", "usb pendrive dispositivo conectado entrada porta nao reconhece"),
    ("dispositivos", "Bluetooth", "bluetooth parear fone sem fio caixinha controle"),
    ("acessibilidade", "Alto contraste", "alto contraste enxergar visao daltonismo"),
    ("acessibilidade", "Tamanho do texto", "texto grande letra grande fonte lupa"),
    ("geral", "Trocar senha", "senha trocar mudar password esqueci conta"),
    ("geral", "Atualizações", "atualizar atualizacao update sistema novo"),
    ("geral", "Data e hora", "data hora relogio errada fuso horario"),
    ("geral", "Idioma", "idioma lingua portugues"),
    ("geral", "Espaço no disco", "armazenamento disco espaco cheio memoria liberar"),
    ("geral", "O que está ocupando espaço", "espaco disco pesado analisar pastas grandes baobab"),
    ("geral", "Formatar disco ou pendrive", "formatar disco pendrive apagar particao usb"),
    ("geral", "Sobre este computador", "sobre versao sistema nome do computador memoria ram"),
]


class SearchIndex:
    def __init__(self, topics):
        self.entries = [
            {"cat_id": c, "label": l, "keywords": k.lower()} for c, l, k in topics
        ]

    def search(self, text):
        text = text.lower().strip()
        if not text:
            return []
        results = []
        for e in self.entries:
            haystack = f"{e['label'].lower()} {e['keywords']}"
            if text in haystack:
                results.append(e)
        return results[:10]


# --------------------------------------------------------------------------
# Categorias — ordem fixa, nomes de tarefa
# --------------------------------------------------------------------------

CATEGORIES = [
    ("geral", "computer", "Geral"),
    ("internet", "preferences-system-network", "Internet"),
    ("aparencia", "preferences-desktop-wallpaper", "Aparência"),
    ("som", "preferences-desktop-sound", "Som e Notificações"),
    ("tela", "video-display", "Tela e Energia"),
    ("dispositivos", "input-mouse", "Dispositivos Conectados"),
    ("acessibilidade", "preferences-desktop-accessibility", "Acessibilidade"),
    # "dev" fica fora da lista pública; entra na sidebar só quando desbloqueado.
    # Nomes de ícone escolhidos para cair na variante colorida "cheia" do
    # Papirus (categoria preferences-*/devices), não na fininha de status —
    # "network-wireless"/"audio-volume-high" puxavam a monocromática.
]

DEV_CATEGORY = ("dev", "utilities-terminal", "Opções Avançadas")


# Tamanho em que a janela abre -- o que o usuario deixou ao ajustar na mao.
LARGURA_JANELA, ALTURA_JANELA = 705, 600


def posicao_junto_da_dock(larg, alt):
    """Onde abrir para ficar encostada na Dock. O calculo mora no
    tarsila-pos-dock, compartilhado com a Lixeira e a tela de Aplicativos."""
    try:
        r = subprocess.run(["/usr/local/bin/tarsila-pos-dock",
                            str(larg), str(alt), "gtk-app"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            x, y = r.stdout.split()
            return int(x), int(y)
    except Exception:
        pass
    return None


class TarsilaConfigWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Ajustes")
        # Tamanho travado, como a Lixeira e a tela de Aplicativos: sem botao
        # de maximizar e sem arrastar as bordas. Janela nao-redimensionavel
        # ignora set_default_size (assume o tamanho natural), por isso o
        # tamanho vem de um pedido. Mover pela barra de titulo continua valendo.
        self.set_size_request(LARGURA_JANELA, ALTURA_JANELA)
        self.set_resizable(False)
        self.state = load_state()
        self.index = SearchIndex(SEARCH_TOPICS)
        self.built_pages = set()
        self.about_clicks = 0  # sessão atual; segredo não persiste pela metade
        self.category_titles = dict((c[0], c[2]) for c in CATEGORIES)
        self.category_titles[DEV_CATEGORY[0]] = DEV_CATEGORY[2]

        self._builders = {
            "internet": self._page_internet,
            "aparencia": self._page_aparencia,
            "som": self._page_som,
            "tela": self._page_tela,
            "dispositivos": self._page_dispositivos,
            "acessibilidade": self._page_acessibilidade,
            "geral": self._page_geral,
            "dev": self._page_dev,
        }

        self._build_css()
        self._build_header()
        self._build_body()
        self._build_sidebar()

        self.connect("key-press-event", self._on_key_press)
        # Nasce encostada na Dock, na mesma linha das outras telas do
        # Tarsila. Posicionar ANTES de mostrar e o que evita a janela aparecer
        # num lugar e pular para outro.
        onde = posicao_junto_da_dock(LARGURA_JANELA, ALTURA_JANELA)
        if onde:
            self.move(*onde)
        self.show_all()
        self._select_category("geral")

    # -- estrutura geral ----------------------------------------------------

    def _build_css(self):
        css = b"""
        .tarsila-card { border: none; }
        .tarsila-list { background: transparent; }
        .tarsila-sidebar row { padding: 8px 6px; border-radius: 6px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _build_header(self):
        # Sem Gtk.HeaderBar/CSD de proposito: essa janela deve usar a
        # MESMA decoracao nativa (xfwm4) que todo outro app do sistema -
        # uma HeaderBar desenha seu proprio botao de fechar e titulo,
        # duplicando a barra real do topbar (que ja mostra X/quadrado/
        # titulo quando maximizado) e ficando mais alta que a decoracao
        # nativa quando nao maximizado.
        self.header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.header_box.set_margin_start(12)
        self.header_box.set_margin_end(12)
        self.header_box.set_margin_top(8)
        self.header_box.set_margin_bottom(8)

        self.title_label = Gtk.Label()
        self.title_label.set_markup("<b>Ajustes</b>")
        self.title_label.set_xalign(0)
        self.header_box.pack_start(self.title_label, True, True, 0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar")
        self.search_entry.set_width_chars(24)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.header_box.pack_end(self.search_entry, False, False, 0)

        self.search_popover = Gtk.Popover()
        self.search_popover.set_relative_to(self.search_entry)
        self.search_popover.set_position(Gtk.PositionType.BOTTOM)
        self.search_popover.set_modal(False)
        self.search_results = Gtk.ListBox()
        self.search_results.connect("row-activated", self._on_search_result_activated)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_width(320)
        sw.set_max_content_height(320)
        sw.add(self.search_results)
        sw.show_all()
        self.search_popover.add(sw)

    def _build_body(self):
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer_box)
        outer_box.pack_start(self.header_box, False, False, 0)
        outer_box.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        self.root_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        outer_box.pack_start(self.root_box, True, True, 0)

        side_scroller = Gtk.ScrolledWindow()
        side_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        side_scroller.set_size_request(240, -1)
        self.sidebar = Gtk.ListBox()
        self.sidebar.get_style_context().add_class("tarsila-sidebar")
        self.sidebar.connect("row-selected", self._on_sidebar_row_selected)
        side_scroller.add(self.sidebar)
        self.root_box.pack_start(side_scroller, False, False, 0)

        self.root_box.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        self.root_box.pack_start(self.stack, True, True, 0)

    def _build_sidebar(self):
        for cat_id, icon, title in CATEGORIES:
            self._add_sidebar_row(cat_id, icon, title)
        if self.state.get("dev_unlocked"):
            self._add_sidebar_row(*DEV_CATEGORY)

    def _add_sidebar_row(self, cat_id, icon, title):
        row = Gtk.ListBoxRow()
        row.cat_id = cat_id
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        box.pack_start(img, False, False, 0)
        lbl = Gtk.Label(label=title, xalign=0)
        box.pack_start(lbl, True, True, 0)
        row.add(box)
        row.show_all()
        self.sidebar.add(row)
        return row

    # -- páginas (construção sob demanda) -----------------------------------

    def _ensure_page(self, cat_id):
        if cat_id in self.built_pages:
            return
        scroller = Gtk.ScrolledWindow()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(20)
        content.set_margin_bottom(30)
        scroller.add(content)
        self.stack.add_named(scroller, cat_id)
        builder = self._builders.get(cat_id)
        if builder:
            builder(content)
        scroller.show_all()
        self.built_pages.add(cat_id)

    # ---- Internet ----
    def _page_internet(self, box):
        card, lb = make_card("Conexão")
        box.pack_start(card, False, False, 0)

        TYPE_NAMES = {"wifi": ("network-wireless", "Wi-Fi"),
                      "ethernet": ("network-wired", "Cabo de rede")}
        STATE_NAMES = {"connected": "Conectado", "disconnected": "Desconectado",
                       "unavailable": "Indisponível", "connecting": "Conectando…",
                       "unmanaged": "Não gerenciado"}

        ok, out, _ = run_ok(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION",
                             "device", "status"])
        shown = 0
        has_wifi = False
        if ok:
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) < 2:
                    continue
                dtype = parts[0]
                if dtype not in TYPE_NAMES:  # esconde loopback, bridge, p2p...
                    continue
                if dtype == "wifi":
                    has_wifi = True
                icon, name = TYPE_NAMES[dtype]
                state = STATE_NAMES.get(parts[1], parts[1])
                conn = parts[2] if len(parts) > 2 and parts[2] else ""
                subtitle = f"{state} · {conn}" if conn else state
                if dtype == "wifi":
                    self._wifi_row(lb, add_row, icon, name, parts[1], conn)
                else:
                    add_row(lb, icon, name, subtitle)
                shown += 1
        if not has_wifi:
            add_row(lb, "network-wireless-offline", "Wi-Fi",
                    "Nenhuma placa de Wi-Fi reconhecida")
        if not shown:
            add_row(lb, "network-offline", "Rede",
                    "Nenhuma conexão de rede encontrada neste computador")

        add_tool_row(lb, "network-workgroup", "Redes salvas e VPN",
                     "Conexões conhecidas, VPN e proxy",
                     ["nm-connection-editor"], "Gerenciar ›")

        # Cabo de rede: IP/gateway/DNS direto pelo painel via "sudo -n" —
        # o nm-connection-editor (botão acima) sofre do mesmo problema do
        # pkexec (exige agente gráfico de polkit, que este equipamento não
        # tem), então salvar uma conexão do sistema por ele trava/falha.
        eth_dev, eth_conn = self._find_ethernet_connection()
        if eth_conn and which("sudo"):
            method, ip, gw, dns = self._read_ethernet_ipv4(eth_dev)
            card, lb = make_card("Cabo de rede (Ethernet)")
            box.pack_start(card, False, False, 0)
            add_row(lb, "network-wired", "Endereço IP", ip or "—")
            add_row(lb, "network-wired", "Portão de entrada (gateway)", gw or "—")
            add_row(lb, "network-wired", "DNS", dns or "—")
            self._eth_conn = eth_conn
            eth_btn = Gtk.Button(label="Configurar ›")
            eth_btn.connect("clicked", self._on_ethernet_manual_clicked)
            add_row(lb, "preferences-system-network",
                    "IP automático (DHCP)" if method != "manual" else "IP manual",
                    "Toque para trocar entre automático e manual", eth_btn)

        # Modo avião com semântica de celular: LIGAR o modo avião DESLIGA
        # os rádios. O original invertia isso ("Rádios ativos"), que obriga
        # o usuário a pensar em dupla negação.
        # Só aparece se houver rádio Wi-Fi de verdade: "nmcli radio wifi"
        # responde enabled/disabled mesmo em equipamento sem placa Wi-Fi
        # (é um estado de software do NetworkManager), então checar apenas
        # which("nmcli") mostrava o controle em TV box só com cabo de rede.
        if has_wifi:
            card, lb = make_card("Modo avião")
            box.pack_start(card, False, False, 0)
            ok, out, _ = run_ok(["nmcli", "radio", "wifi"])
            airplane_on = ok and "disabled" in out.lower()
            sw = Gtk.Switch()
            sw.set_active(airplane_on)
            sw.connect("state-set", lambda s, state: run_ok(
                ["nmcli", "radio", "all", "off" if state else "on"]) and False)
            add_row(lb, "airplane-mode-symbolic", "Modo avião",
                    "Desliga o Wi-Fi e outras conexões sem fio", sw)

    # ---- Wi-Fi: linha contextual + janela "Conexões de rede" ----
    def _wifi_row(self, lb, add_row, icon, name, estado, conn):
        """Monta a linha do Wi-Fi conforme o estado da placa/conexão."""
        conectado = (estado == "connected")
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        if conectado:
            b1 = Gtk.Button.new_with_label("Desconectar Wi-Fi")
            b1.connect("clicked", lambda *_a: self._wifi_desconectar())
            b2 = Gtk.Button.new_with_label("Conectar a outra rede Wi-Fi")
            b2.connect("clicked", lambda *_a: self._wifi_janela())
            caixa.pack_start(b1, False, False, 0)
            caixa.pack_start(b2, False, False, 0)
            sub = conn or "Conectado"
        else:
            b = Gtk.Button.new_with_label("Conectar ao Wi-Fi")
            b.connect("clicked", lambda *_a: self._wifi_janela())
            caixa.pack_start(b, False, False, 0)
            sub = "Desconectado"
        add_row(lb, icon, name, sub, caixa)

    @staticmethod
    def _wifi_janela():
        """Abre a janela Conexões de rede (seção Wi-Fi)."""
        try:
            subprocess.Popen(["/usr/local/bin/tarsila-wifi"])
        except Exception as e:
            print("tarsila-config: nao abriu tarsila-wifi:", e)

    def _wifi_desconectar(self):
        ok, out, _ = run_ok(["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"])
        dev = None
        if ok:
            for line in out.splitlines():
                p = line.split(":")
                if len(p) >= 2 and p[1] == "wifi":
                    dev = p[0]
                    break
        if dev:
            run_ok(["nmcli", "device", "disconnect", dev], timeout=20)
        GLib.timeout_add_seconds(1, self._wifi_recarregar_pagina)

    def _wifi_recarregar_pagina(self):
        """Reconstrói a página Internet para refletir o novo estado."""
        try:
            antigo = self.stack.get_child_by_name("internet")
            if antigo is not None:
                self.stack.remove(antigo)
            self.built_pages.discard("internet")
            self._ensure_page("internet")
            self.stack.set_visible_child_name("internet")
        except Exception as e:
            print("tarsila-config: refresh internet:", e)
        return False

    @staticmethod
    def _find_ethernet_connection():
        ok, out, _ = run_ok(["nmcli", "-t", "-f", "DEVICE,TYPE,CONNECTION", "device", "status"])
        if not ok:
            return None, None
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1] == "ethernet":
                conn = parts[2] if len(parts) > 2 and parts[2] else None
                return parts[0], conn
        return None, None

    @staticmethod
    def _read_ethernet_ipv4(dev):
        method = "auto"
        ok, out, _ = run_ok(["nmcli", "-g", "ipv4.method", "connection", "show", dev])
        if ok and out.strip():
            method = out.strip()
        ip = gw = dns = None
        ok, out, _ = run_ok(["nmcli", "-g", "IP4.ADDRESS", "device", "show", dev])
        if ok and out.strip():
            ip = out.splitlines()[0].split("|")[0].strip()
        ok, out, _ = run_ok(["nmcli", "-g", "IP4.GATEWAY", "device", "show", dev])
        if ok and out.strip():
            gw = out.strip()
        ok, out, _ = run_ok(["nmcli", "-g", "IP4.DNS", "device", "show", dev])
        if ok and out.strip():
            dns = out.splitlines()[0].split("|")[0].strip()
        return method, ip, gw, dns

    def _on_ethernet_manual_clicked(self, *_a):
        method, ip, gw, dns = self._read_ethernet_ipv4(self._eth_conn)

        dlg = Gtk.Dialog(title="Configurar IP da rede cabeada", transient_for=self, modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Aplicar", Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(10)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        auto_switch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        auto_switch_row.pack_start(Gtk.Label(label="IP automático (DHCP)", xalign=0), True, True, 0)
        auto_switch = Gtk.Switch()
        auto_switch.set_active(method != "manual")
        auto_switch_row.pack_start(auto_switch, False, False, 0)
        content.pack_start(auto_switch_row, False, False, 0)

        ip_entry = Gtk.Entry()
        ip_entry.set_placeholder_text("Ex.: 192.168.1.50/24")
        gw_entry = Gtk.Entry()
        gw_entry.set_placeholder_text("Ex.: 192.168.1.1")
        dns_entry = Gtk.Entry()
        dns_entry.set_placeholder_text("Ex.: 8.8.8.8")
        if method == "manual":
            ip_entry.set_text(ip or "")
            gw_entry.set_text(gw or "")
            dns_entry.set_text(dns or "")
        for label_text, entry in (("Endereço IP/prefixo", ip_entry),
                                   ("Gateway", gw_entry), ("DNS", dns_entry)):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            lbl = Gtk.Label(label=label_text, xalign=0)
            lbl.set_size_request(140, -1)
            row.pack_start(lbl, False, False, 0)
            row.pack_start(entry, True, True, 0)
            content.pack_start(row, False, False, 0)

        def _update_sensitivity(*_a):
            manual = not auto_switch.get_active()
            for e in (ip_entry, gw_entry, dns_entry):
                e.set_sensitive(manual)
        auto_switch.connect("notify::active", _update_sensitivity)
        _update_sensitivity()

        content.show_all()
        response = dlg.run()
        result = None
        if response == Gtk.ResponseType.OK:
            if auto_switch.get_active():
                result = ("auto", "", "", "")
            else:
                result = ("manual", ip_entry.get_text().strip(),
                          gw_entry.get_text().strip(), dns_entry.get_text().strip())
        dlg.destroy()
        if result:
            self._apply_ethernet_config(result)

    def _apply_ethernet_config(self, result):
        method = result[0]

        def worker():
            argv = ["sudo", "-n", "/usr/local/bin/tarsila-net-set", self._eth_conn, method]
            if method == "manual":
                argv += list(result[1:])
            ok, _out, _err = run_ok(argv, timeout=30)
            GLib.idle_add(self._after_ethernet_config, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _after_ethernet_config(self, ok):
        if ok:
            self._info_dialog("Rede atualizada", "A configuração da rede cabeada foi aplicada.")
        else:
            self._info_dialog("Não foi possível aplicar",
                              "O comando falhou. Confira o endereço IP e tente de novo.")
        return False

    # ---- Aparência ----
    def _page_aparencia(self, box):
        card, lb = make_card("Tema")
        box.pack_start(card, False, False, 0)
        # Linha "tema atual": somente leitura (estilo formulário), com o
        # botão que abre o seletor com miniaturas. Montada na mão (não
        # via add_row) para guardar referências aos rótulos e poder
        # atualizá-los na hora quando o tema muda.
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hb.set_margin_start(16)
        hb.set_margin_end(16)
        hb.set_margin_top(10)
        hb.set_margin_bottom(10)
        row.add(hb)
        hb.pack_start(Gtk.Image.new_from_icon_name(
            "preferences-desktop-wallpaper", Gtk.IconSize.LARGE_TOOLBAR),
            False, False, 0)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        hb.pack_start(tb, True, True, 0)
        self._tema_nome = Gtk.Label(xalign=0)
        tb.pack_start(self._tema_nome, False, False, 0)
        self._tema_desc = Gtk.Label(xalign=0)
        self._tema_desc.set_line_wrap(True)
        tb.pack_start(self._tema_desc, False, False, 0)
        alterar = Gtk.Button(label="Alterar tema ›")
        alterar.set_valign(Gtk.Align.CENTER)
        alterar.connect("clicked", self._on_alterar_tema)
        hb.pack_start(alterar, False, False, 0)
        lb.add(row)
        row.show_all()
        self._mostrar_tema_atual()

        b = Gtk.Button(label="Escolher imagem ›")
        b.connect("clicked", self._on_tema_personalizado)
        add_row(lb, "insert-image", "Personalizar com seu Papel de Parede",
                "Sua imagem de fundo com a barra superior clara", b)

        card, lb = make_card("Cores e texto")
        box.pack_start(card, False, False, 0)
        current_theme = xfconf_get("xsettings", "/Net/ThemeName", "Xfce")
        dark_switch = Gtk.Switch()
        dark_switch.set_active("dark" in current_theme.lower()
                               or current_theme == "HighContrast")
        dark_switch.connect("state-set", self._on_dark_toggle)
        add_row(lb, "weather-clear-night", "Modo escuro",
                "Cores escuras, mais confortáveis à noite", dark_switch)

        self._add_font_size_row(lb)


        if which("xfce4-appearance-settings"):
            card, lb = make_card("Mais opções")
            box.pack_start(card, False, False, 0)
            add_tool_row(lb, "preferences-desktop-theme", "Aparência avançada",
                         "Ícones, fontes e estilo das janelas",
                         ["xfce4-appearance-settings"])

    def _add_font_size_row(self, lb):
        """Tamanho do texto — usado em Aparência e em Acessibilidade,
        porque o usuário procura "letra grande" nos dois lugares."""
        font_scale = Gtk.SpinButton.new_with_range(8, 24, 1)
        cur_font = xfconf_get("xsettings", "/Gtk/FontName", "Sans 10")
        try:
            size = int(cur_font.split()[-1])
        except (ValueError, IndexError):
            size = 10
        font_scale.set_value(size)
        font_scale.connect("value-changed", self._on_font_size_changed, cur_font)
        add_row(lb, "zoom-in", "Tamanho do texto",
                "Aumenta as letras em todo o sistema", font_scale)

    def _on_dark_toggle(self, switch, state):
        theme = "Adwaita-dark" if state else "Adwaita"
        if not Path(f"/usr/share/themes/{theme}").exists():
            theme = "HighContrast" if state else "Xfce"
        xfconf_set("xsettings", "/Net/ThemeName", theme, "string", create=True)
        return False

    def _on_font_size_changed(self, spin, base_font):
        family = " ".join(base_font.split()[:-1]) or "Sans"
        xfconf_set("xsettings", "/Gtk/FontName",
                   f"{family} {int(spin.get_value())}", "string", create=True)

    def _tema_atual(self):
        try:
            tid = (Path.home() / ".config" / "tarsila" / "tema").read_text().strip()
        except OSError:
            tid = "padrao"
        for t in TEMAS_VISUAIS + [TEMA_PERSONALIZADO]:
            if t[0] == tid:
                return t
        return TEMAS_VISUAIS[0]

    def _mostrar_tema_atual(self, tema_id=None):
        if tema_id:
            tema = next((t for t in TEMAS_VISUAIS + [TEMA_PERSONALIZADO]
                         if t[0] == tema_id), TEMAS_VISUAIS[0])
        else:
            tema = self._tema_atual()
        _tid, nome, desc, _wp = tema
        self._tema_nome.set_markup(
            f"Tema atual:  <b>{GLib.markup_escape_text(nome)}</b>")
        self._tema_desc.set_markup(
            f'<small><span alpha="65%">{GLib.markup_escape_text(desc)}</span></small>')

    def _on_alterar_tema(self, *_a):
        dlg = Gtk.Dialog(title="Escolher tema", transient_for=self, modal=True)
        dlg.add_buttons("Fechar", Gtk.ResponseType.CLOSE)
        dlg.set_default_size(420, -1)
        ca = dlg.get_content_area()
        ca.set_spacing(4)
        ca.set_margin_start(10)
        ca.set_margin_end(10)
        ca.set_margin_top(10)
        ca.set_margin_bottom(6)
        lista = Gtk.ListBox()
        lista.set_selection_mode(Gtk.SelectionMode.NONE)
        lista.get_style_context().add_class("tarsila-list")
        atual = self._tema_atual()[0]
        for tid, nome, desc, wp in TEMAS_VISUAIS:
            r = Gtk.ListBoxRow()
            r.set_activatable(True)
            r.tema_id = tid
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hb.set_margin_start(8)
            hb.set_margin_end(8)
            hb.set_margin_top(8)
            hb.set_margin_bottom(8)
            r.add(hb)
            # miniatura do papel de parede do tema
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(wp, 120, 68, False)
                hb.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
            except GLib.Error:
                hb.pack_start(Gtk.Image.new_from_icon_name(
                    "image-missing", Gtk.IconSize.DIALOG), False, False, 0)
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vb.set_valign(Gtk.Align.CENTER)
            hb.pack_start(vb, True, True, 0)
            t1 = Gtk.Label(xalign=0)
            marca = "   ✓" if tid == atual else ""
            t1.set_markup(f"<b>{GLib.markup_escape_text(nome)}</b>{marca}")
            vb.pack_start(t1, False, False, 0)
            t2 = Gtk.Label(xalign=0)
            t2.set_markup(f'<small><span alpha="65%">'
                          f"{GLib.markup_escape_text(desc)}</span></small>")
            t2.set_line_wrap(True)
            vb.pack_start(t2, False, False, 0)
            lista.add(r)
        lista.connect("row-activated", self._on_tema_escolhido, dlg)
        ca.pack_start(lista, True, True, 0)
        dica = Gtk.Label(xalign=0)
        dica.set_markup('<small><span alpha="55%">Toque em um tema para '
                        "aplicá-lo.</span></small>")
        ca.pack_start(dica, False, False, 0)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _on_tema_escolhido(self, _lista, row, dlg):
        run_bg(["/usr/local/bin/tarsila-tema-apply.sh", row.tema_id])
        self._mostrar_tema_atual(row.tema_id)
        dlg.response(Gtk.ResponseType.CLOSE)

    def _on_tema_personalizado(self, *_a):
        dlg = Gtk.FileChooserDialog(title="Escolher papel de parede",
                                    transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        "Escolher", Gtk.ResponseType.OK)
        img_filter = Gtk.FileFilter()
        img_filter.set_name("Imagens")
        img_filter.add_mime_type("image/png")
        img_filter.add_mime_type("image/jpeg")
        dlg.add_filter(img_filter)
        if dlg.run() == Gtk.ResponseType.OK:
            run_bg(["/usr/local/bin/tarsila-tema-apply.sh",
                    "personalizado", dlg.get_filename()])
            self._mostrar_tema_atual("personalizado")
        dlg.destroy()

    # ---- Som e Notificações ----
    def _page_som(self, box):
        card, lb = make_card("Volume")
        box.pack_start(card, False, False, 0)
        vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        vol_scale.set_size_request(160, -1)
        vol_scale.set_draw_value(False)
        ok, out, _ = run_ok(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        current = 50
        if ok and "%" in out:
            try:
                current = int(out.split("%")[0].split()[-1])
            except (ValueError, IndexError):
                pass
        vol_scale.set_value(current)
        vol_scale.connect("value-changed", lambda s: run_ok(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@",
             f"{int(s.get_value())}%"]))
        # audio-volume-high mora em actions/panel do Papirus, que e a variante
        # fininha monocromatica -- por isso saia mais claro que as vizinhas.
        # audio-speakers esta em devices, a variante colorida cheia.
        add_row(lb, "audio-speakers", "Volume principal", "", vol_scale)

        # Seletor de saída de som (amigável): lista os destinos disponíveis
        # (TV/HDMI, Fone P2 ou qualquer placa de som USB conectada) e deixa o
        # usuário escolher por onde o som toca, com um toque. Resolve o caso
        # da tvbox, que só oferecia HDMI como opção gráfica.
        card, lb = make_card("Onde o som toca")
        box.pack_start(card, False, False, 0)
        self._som_saidas(lb, add_row)

        card, lb = make_card("Ajustes avançados")
        box.pack_start(card, False, False, 0)
        add_tool_row(lb, "audio-headphones", "Fones, caixas e microfone",
                     "Ajuste fino de entradas, saídas e microfone",
                     ["pavucontrol"], "Abrir ›")

        if which("xfce4-notifyd-config"):
            card, lb = make_card("Notificações")
            box.pack_start(card, False, False, 0)
            add_tool_row(lb, "preferences-system-notifications",
                         "Avisos na tela",
                         "Quais aplicativos podem mostrar avisos e por quanto tempo",
                         ["xfce4-notifyd-config"], "Configurar ›")

    @staticmethod
    def _sink_amigavel(name, desc):
        """Nome/ícone/subtítulo amigável para um sink do PipeWire."""
        n = name.lower()
        if name == "tarsila_fone_p2" or "headphone" in n:
            return ("audio-headphones", "Fone de ouvido (P2)",
                    "Som pela entrada de fone (P2) do aparelho")
        if "hdmi" in n:
            return ("video-display", "TV ou Monitor (HDMI)",
                    "Som pela TV ou monitor, pelo cabo HDMI")
        if "usb" in n:
            return ("audio-card", desc or "Som USB",
                    "Placa de som conectada pela USB")
        if "bluez" in n or "bluetooth" in n:
            return ("audio-headphones", desc or "Fone Bluetooth",
                    "Som por um fone ou caixa Bluetooth")
        return ("audio-card", desc or name, "")

    def _som_saidas(self, lb, add_row):
        """Lista as saídas de som com escolha por toque (rádio)."""
        _, defout, _ = run_ok(["pactl", "get-default-sink"])
        default = defout.strip()
        ok, out, _ = run_ok(["pactl", "list", "sinks", "short"])
        nomes = []
        if ok:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and parts[1].strip():
                    nomes.append(parts[1].strip())
        # descrições (para placas USB que trazem nome próprio)
        desc = {}
        ok2, out2, _ = run_ok(["pactl", "list", "sinks"])
        if ok2:
            cur = None
            for l in out2.splitlines():
                s = l.strip()
                if s.startswith("Name:"):
                    cur = s.split(":", 1)[1].strip()
                elif s.startswith("Description:") and cur:
                    desc[cur] = s.split(":", 1)[1].strip()
        if not nomes:
            add_row(lb, "audio-volume-muted", "Som",
                    "Nenhuma saída de som encontrada neste computador")
            return
        grupo = None
        for name in nomes:
            icon, titulo, sub = self._sink_amigavel(name, desc.get(name, name))
            rb = Gtk.RadioButton.new_from_widget(grupo)
            if grupo is None:
                grupo = rb
            rb.set_active(name == default)
            rb.connect("toggled", lambda w, n=name:
                       w.get_active() and self._som_definir_saida(n))
            add_row(lb, icon, titulo, sub, rb)

    def _som_definir_saida(self, name):
        """Torna 'name' a saída padrão e move o que já está tocando."""
        run_ok(["pactl", "set-default-sink", name])
        ok, out, _ = run_ok(["pactl", "list", "sink-inputs", "short"])
        if ok:
            for line in out.splitlines():
                sid = line.split("\t")[0].strip() if "\t" in line \
                    else (line.split()[0] if line.split() else "")
                if sid.isdigit():
                    run_ok(["pactl", "move-sink-input", sid, name])

    # ---- Tela e Energia ----
    def _page_tela(self, box):
        card, lb = make_card("Tela")
        box.pack_start(card, False, False, 0)
        add_tool_row(lb, "video-display", "Ajustar a tela",
                     "Tamanho dos itens, segundo monitor ou TV",
                     ["xfce4-display-settings"], "Ajustar ›")

        card, lb = make_card("Energia")
        box.pack_start(card, False, False, 0)
        add_tool_row(lb, "battery", "Economia de energia",
                     "Quando apagar a tela ou suspender o computador",
                     ["xfce4-power-manager-settings"], "Configurar ›")

        # Bateria: só aparece se existir. Em TV box e desktop, nada.
        # "upower -e" também lista baterias de periféricos (teclado/mouse
        # sem fio via receptor hidpp) — o próprio upower marca essas como
        # "power supply: no" e diz para ignorar a porcentagem. Sem filtrar
        # por power-supply, um teclado sem fio virava "bateria do
        # computador" na tela de Energia.
        bat_paths = []
        ok, out, _ = run_ok(["upower", "-e"])
        if ok:
            for l in out.splitlines():
                if "battery" not in l.lower():
                    continue
                ok2, info, _ = run_ok(["upower", "-i", l])
                is_power_supply = any(
                    line.strip().lower().startswith("power supply:")
                    and line.split(":", 1)[1].strip().lower() == "yes"
                    for line in info.splitlines())
                if ok2 and is_power_supply:
                    bat_paths.append(l)
        if bat_paths:
            ok, out, _ = run_ok(["upower", "-i", bat_paths[0]])
            pct = "—"
            if ok:
                for line in out.splitlines():
                    if "percentage" in line:
                        pct = line.split(":")[-1].strip()
            add_row(lb, "battery-good", "Bateria", f"Carga atual: {pct}")

    # ---- Mouse, Teclado e Impressora ----
    def _page_dispositivos(self, box):
        card, lb = make_card("Mouse e teclado")
        box.pack_start(card, False, False, 0)
        add_tool_row(lb, "input-mouse", "Mouse",
                     "Velocidade do ponteiro e rolagem",
                     ["xfce4-mouse-settings"], "Ajustar ›")
        add_tool_row(lb, "input-keyboard", "Teclado",
                     "Idioma do teclado e acentuação",
                     ["xfce4-keyboard-settings"], "Ajustar ›")

        card, lb = make_card("Impressora")
        box.pack_start(card, False, False, 0)
        if which("system-config-printer"):
            btn = open_tool_button("Gerenciar ›", ["system-config-printer"])
            add_row(lb, "printer", "Impressoras e scanners",
                    "Adicionar impressora e ver fila de impressão", btn)
        else:
            link = Gtk.LinkButton.new_with_label("http://localhost:631",
                                                 "Gerenciar ›")
            add_row(lb, "printer", "Impressoras e scanners",
                    "Adicionar impressora e ver fila de impressão", link)

        # Câmera e microfone: no Linux, webcams padrão (UVC) funcionam sem
        # instalar nada — então o painel é status + teste, não configuração.
        # O cartão só aparece se houver câmera de verdade (/dev/video*).
        has_camera = bool(sorted(Path("/dev").glob("video*")))
        if has_camera or which("pavucontrol"):
            card, lb = make_card("Câmera e microfone")
            box.pack_start(card, False, False, 0)
            if has_camera:
                test_argv = None
                for app in ("cheese", "guvcview"):
                    if which(app):
                        test_argv = [app]
                        break
                if test_argv:
                    btn = open_tool_button("Testar ›", test_argv)
                    add_row(lb, "camera-web", "Câmera",
                            "Conectada e pronta para usar", btn)
                else:
                    add_row(lb, "camera-web", "Câmera",
                            "Conectada e pronta para usar")
            add_tool_row(lb, "audio-input-microphone", "Microfone",
                         "Volume de entrada e escolha do microfone",
                         ["pavucontrol"], "Ajustar ›")

        # USB: contagem simples, útil para diagnóstico por telefone
        # ("quantos dispositivos aparecem aí?").
        if which("lsusb"):
            ok, out, _ = run_ok(["lsusb"])
            if ok:
                devices = [l for l in out.splitlines()
                           if l and "root hub" not in l.lower()]
                n = len(devices)
                if n == 0:
                    subtitle = "Nenhum dispositivo conectado nas entradas USB"
                elif n == 1:
                    subtitle = "1 dispositivo conectado nas entradas USB"
                else:
                    subtitle = f"{n} dispositivos conectados nas entradas USB"
                card, lb = make_card("USB")
                box.pack_start(card, False, False, 0)
                add_row(lb, "drive-removable-media", "Entradas USB", subtitle)

        # Bluetooth: só aparece se o gerenciador existir neste equipamento.
        if which("blueman-manager"):
            card, lb = make_card("Bluetooth")
            box.pack_start(card, False, False, 0)
            add_tool_row(lb, "bluetooth-symbolic", "Bluetooth",
                         "Conectar fones, caixas de som e controles sem fio",
                         ["blueman-manager"], "Gerenciar ›")

    # ---- Acessibilidade ----
    def _page_acessibilidade(self, box):
        card, lb = make_card("Visão")
        box.pack_start(card, False, False, 0)

        contrast_switch = Gtk.Switch()
        current_theme = xfconf_get("xsettings", "/Net/ThemeName", "Xfce")
        contrast_switch.set_active(current_theme == "HighContrast")
        contrast_switch.connect("state-set", lambda s, state: xfconf_set(
            "xsettings", "/Net/ThemeName",
            "HighContrast" if state else "Xfce", "string", create=True) and False)
        add_row(lb, "video-display-symbolic", "Alto contraste",
                "Cores mais fortes, para enxergar melhor", contrast_switch)

        self._add_font_size_row(lb)

        if which("xfce4-accessibility-settings"):
            card, lb = make_card("Mais opções")
            box.pack_start(card, False, False, 0)
            add_tool_row(lb, "preferences-desktop-accessibility",
                         "Outras opções de acessibilidade",
                         "Teclas de aderência e teclado na tela",
                         ["xfce4-accessibility-settings"])

    # ---- Conta e Segurança ----
    # ---- Geral ----
    def _page_geral(self, box):
        # Sobrou da antiga aba "Conta e Segurança": o nome da conta e, na
        # propria linha, o botao de trocar a senha. Bloquear a tela, o estado
        # do firewall e a lista de outros usuarios foram retirados a pedido do
        # usuario, e com eles a aba inteira -- nao valia uma secao so para
        # mostrar o nome de quem esta usando.
        card, lb = make_card("Sua conta")
        box.pack_start(card, False, False, 0)
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or "?"
        pw_btn = Gtk.Button(label="Trocar senha")
        pw_btn.connect("clicked", lambda *_: run_bg(
            ["xfce4-terminal", "--title=Trocar senha", "-e", "passwd"]))
        add_row(lb, "avatar-default", user, "Conta deste computador", pw_btn)

        card, lb = make_card("Atualizações")
        box.pack_start(card, False, False, 0)
        check_btn = Gtk.Button(label="Verificar e Instalar")
        self._check_btn = check_btn
        self._updates_lbl = Gtk.Label(label="", xalign=0)
        self._updates_lbl.set_margin_start(16)
        self._updates_lbl.set_margin_bottom(8)
        add_row(lb, "system-software-update", "Atualizações do sistema",
                "Correções e melhorias para este computador", check_btn)
        card.get_child().pack_start(self._updates_lbl, False, False, 0)
        check_btn.connect("clicked", lambda *_: self._check_updates())

        card, lb = make_card("Data, hora e idioma")
        box.pack_start(card, False, False, 0)
        tz, ntp = self._read_timedate()

        if which("sudo"):
            self._ntp_switch = Gtk.Switch()
            self._ntp_switch.set_active(ntp == "yes")
            self._ntp_switch.set_state(ntp == "yes")
            self._ntp_switch.connect("state-set", self._on_ntp_toggle)
            add_row(lb, "appointment-soon", "Acertar a hora automaticamente",
                    "Mantém o relógio certo pela internet", self._ntp_switch)
        else:
            self._ntp_switch = None
            add_row(lb, "appointment-soon", "Acertar a hora automaticamente",
                    "Sem permissão para alterar neste equipamento")

        # O fuso saiu da grade: virou um campo dentro da janela de ajuste.
        # Ele so importa quando alguem vai mexer na hora, e ocupava uma linha
        # inteira da tela principal para uma escolha que se faz uma vez na vida.
        self._manual_btn = Gtk.Button(label="Ajustar hora e data manualmente")
        self._manual_btn.connect("clicked", self._on_manual_time_clicked)
        # Desligado enquanto o relogio se acerta sozinho: mexer na mao com o
        # ajuste automatico ligado nao adianta, o NTP desfaz em segundos.
        self._atualiza_botao_manual(ntp == "yes")
        # Linha montada a mao em vez de add_row: aquela funcao sempre poe um
        # icone a esquerda e empurra o controle para a direita. Aqui o botao ja
        # diz tudo sozinho, entao nao ha icone nem texto -- e ele fica encostado
        # a esquerda, alinhado com os titulos das outras linhas.
        linha = Gtk.ListBoxRow()
        linha.set_selectable(False)
        linha.set_activatable(False)
        caixa_btn = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        caixa_btn.set_margin_start(16)
        caixa_btn.set_margin_end(16)
        caixa_btn.set_margin_top(10)
        caixa_btn.set_margin_bottom(10)
        caixa_btn.pack_start(self._manual_btn, False, False, 0)
        linha.add(caixa_btn)
        lb.add(linha)

        # Idioma: mostra o nome por extenso e deixa trocar ali mesmo.
        lang = os.environ.get("LANG", "")
        self._idioma_combo = Gtk.ComboBoxText()
        escolhido = 0
        conhecidos = [c for c, _ in IDIOMAS]
        if lang and lang not in conhecidos:
            self._idioma_combo.append(lang, nome_do_idioma(lang))
        for i, (cod, nome) in enumerate(IDIOMAS):
            self._idioma_combo.append(cod, nome)
            if cod.split(".")[0] == lang.split(".")[0]:
                escolhido = i + (0 if lang in conhecidos else 1)
        self._idioma_combo.set_active(escolhido)
        self._idioma_combo.set_sensitive(which("sudo"))
        self._idioma_atual = lang
        self._idioma_combo.connect("changed", self._on_idioma_changed)
        add_row(lb, "preferences-desktop-locale", "Idioma do sistema",
                "As telas do Tarsila seguem em português",
                self._idioma_combo)

        card, lb = make_card("Espaço no disco")
        box.pack_start(card, False, False, 0)
        try:
            total, used, _free = shutil.disk_usage("/")
            bar = Gtk.LevelBar()
            bar.set_min_value(0)
            bar.set_max_value(100)
            bar.set_value(used / total * 100)
            bar.set_size_request(160, -1)
            add_row(lb, "drive-harddisk", "Armazenamento",
                    f"{used / 2**30:.1f} GB usados de {total / 2**30:.1f} GB", bar)
        except OSError:
            pass
        add_tool_row(lb, "folder", "Meus arquivos",
                     "Ver e organizar seus documentos e fotos",
                     ["thunar"])
        add_tool_row(lb, "baobab", "Ver o que está ocupando espaço",
                     "Mapa visual de pastas e arquivos grandes",
                     ["baobab"], "Analisar ›")
        # Formatar é destrutivo (apaga tudo do disco/pendrive escolhido);
        # o GNOME Disks já tem as próprias telas de confirmação e escolha
        # de sistema de arquivos — não vale a pena reimplementar isso aqui
        # chamando mkfs na mão.
        add_tool_row(lb, "drive-harddisk", "Formatar um disco ou pendrive",
                     "Apaga tudo no disco escolhido — use com cuidado",
                     ["gnome-disks"], "Abrir ›")

        card, lb = make_card("Sobre este computador")
        box.pack_start(card, False, False, 0)
        hostname = os.uname().nodename
        pretty_os = "Tarsila OS"
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    pretty_os = line.split("=", 1)[1].strip('"')
        except OSError:
            pass
        mem_total = "—"
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal"):
                    kb = int(line.split()[1])
                    mem_total = f"{kb / 2**20:.1f} GB"
        except (OSError, ValueError):
            pass

        add_row(lb, "computer", "Nome do computador", hostname)
        # "RAM" e o nome que a pessoa ve em anuncio e caixa de aparelho.
        # O icone antigo (media-flash) e um cartao de memoria, que e outra
        # coisa -- gnome-dev-memory desenha um pente de RAM.
        add_row(lb, "gnome-dev-memory", "RAM", mem_total)

        # 7 toques na linha da versão desbloqueiam as Opções Avançadas.
        # Silencioso até os 2 últimos toques; sem linha anunciando o segredo.
        version_lb = Gtk.ListBox()
        version_lb.set_selection_mode(Gtk.SelectionMode.NONE)
        version_lb.get_style_context().add_class("tarsila-list")
        card.get_child().pack_start(version_lb, False, False, 0)
        vrow = add_row(version_lb, "dialog-information", "Sistema", pretty_os)
        vrow.set_activatable(True)
        version_lb.connect("row-activated", self._on_version_activated)

        # Numa lista separada de proposito: a de cima tem o segredo dos 7
        # toques na linha "Sistema", e qualquer linha nova ali entraria no
        # caminho desse gesto.
        uso_lb = Gtk.ListBox()
        uso_lb.set_selection_mode(Gtk.SelectionMode.NONE)
        uso_lb.get_style_context().add_class("tarsila-list")
        card.get_child().pack_start(uso_lb, False, False, 0)
        uso_btn = Gtk.Button(label="Abrir ›")
        uso_btn.connect("clicked", lambda *_: run_bg(
            ["xfce4-terminal", "--title=Uso de CPU e RAM", "-e", "htop"]))
        add_row(uso_lb, "utilities-system-monitor", "Verificar uso de CPU e RAM",
                "Mostra o que está consumindo o computador agora", uso_btn)

    def _check_updates(self):
        self._updates_lbl.set_text("Procurando atualizações…")
        # Trava o botao: a instalacao demora, e clicar de novo no meio dela
        # dispararia um segundo apt que so ficaria preso esperando a trava.
        self._check_btn.set_sensitive(False)

        def worker():
            # Sem pkexec aqui: a checagem usa o cache existente e não
            # interrompe o usuário com pedido de senha só para "verificar".
            # Todo o trabalho e do tarsila-atualizar, que roda como root e
            # devolve "FEITAS=<n>" ou "ERRO=...". Assim a tela nao repete a
            # logica que o arranque tambem usa.
            ok, out, _ = run_ok(["sudo", "-n", "/usr/local/sbin/tarsila-atualizar"],
                                timeout=3600)
            feitas = None
            for linha in out.splitlines():
                if linha.startswith("FEITAS="):
                    try:
                        feitas = int(linha.split("=", 1)[1])
                    except ValueError:
                        feitas = None
            if feitas is None:
                msg = "Não foi possível atualizar agora"
            elif feitas == 0:
                msg = "Sem atualizações"
            elif feitas == 1:
                msg = "1 atualização foi feita"
            else:
                msg = "%d atualizações foram feitas" % feitas
            GLib.idle_add(self._updates_lbl.set_text, msg)
            GLib.idle_add(self._check_btn.set_sensitive, True)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _read_timedate():
        # "--property=Timezone,NTP" (lista separada por vírgula) responde
        # vazio nesta versão do systemd; precisa repetir a flag por campo.
        ok, out, _ = run_ok(["timedatectl", "show",
                             "--property=Timezone", "--property=NTP"])
        tz, ntp = "—", "—"
        if ok:
            for line in out.splitlines():
                if line.startswith("Timezone="):
                    tz = line.split("=", 1)[1]
                elif line.startswith("NTP="):
                    ntp = line.split("=", 1)[1]
        return tz, ntp

    def _on_ntp_toggle(self, switch, state):
        # Retornar True tira do GTK a decisão de refletir o clique na hora:
        # o switch só assume a posição nova quando o comando confirmar (ou
        # volta para a de antes se falhar). Antes o GTK sempre mostrava
        # sucesso mesmo com o comando falhando por trás — e o pkexec falhava
        # sempre neste equipamento por falta de agente gráfico de polkit
        # para XFCE. Usamos "sudo -n" com uma regra NOPASSWD bem restrita
        # (só esse comando exato) em vez de depender do polkit.
        switch.set_sensitive(False)

        def worker():
            ok, _out, _err = run_ok(
                ["sudo", "-n", "timedatectl", "set-ntp", "true" if state else "false"],
                timeout=30)
            GLib.idle_add(self._after_ntp_toggle, switch, state, ok)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _atualiza_botao_manual(self, automatico):
        """O ajuste manual so faz sentido com o automatico desligado."""
        botao = getattr(self, "_manual_btn", None)
        if botao is None:
            return
        pode = which("sudo") and not automatico
        botao.set_sensitive(bool(pode))
        botao.set_tooltip_text(
            "Desligue \"Acertar a hora automaticamente\" para ajustar na mão"
            if automatico else "")

    def _after_ntp_toggle(self, switch, state, ok):
        switch.set_sensitive(True)
        switch.set_state(state if ok else not state)
        self._atualiza_botao_manual(state if ok else not state)
        if not ok:
            self._info_dialog(
                "Não foi possível alterar",
                "O comando falhou. O ajuste automático de hora continua "
                "como estava.")
        return False

    def _on_manual_time_clicked(self, *_a):
        dlg = Gtk.Dialog(title="Ajustar data e hora", transient_for=self, modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        "Aplicar", Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(10)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        # Fuso horario aqui dentro, antes do calendario: ele muda o que o
        # calendario e o relogio significam, entao vem primeiro na leitura.
        fuso_atual, _ = self._read_timedate()
        fusos = listar_fusos(fuso_atual)
        combo_fuso = Gtk.ComboBoxText()
        escolhido = 0
        for i, (zona, rotulo) in enumerate(fusos):
            combo_fuso.append(zona, rotulo)
            if zona == fuso_atual:
                escolhido = i
        if fusos:
            combo_fuso.set_active(escolhido)
        linha_fuso = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        linha_fuso.pack_start(Gtk.Label(label="Fuso horário"), False, False, 0)
        linha_fuso.pack_start(combo_fuso, True, True, 0)
        content.pack_start(linha_fuso, False, False, 0)

        now = time.localtime()
        cal = Gtk.Calendar()
        cal.select_month(now.tm_mon - 1, now.tm_year)
        cal.select_day(now.tm_mday)
        content.pack_start(cal, False, False, 0)

        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hour = Gtk.SpinButton.new_with_range(0, 23, 1)
        hour.set_value(now.tm_hour)
        minute = Gtk.SpinButton.new_with_range(0, 59, 1)
        minute.set_value(now.tm_min)
        second = Gtk.SpinButton.new_with_range(0, 59, 1)
        second.set_value(now.tm_sec)
        for label_text, widget in (("Hora", hour), ("Minuto", minute), ("Segundo", second)):
            time_box.pack_start(Gtk.Label(label=label_text), False, False, 0)
            time_box.pack_start(widget, False, False, 0)
        content.pack_start(time_box, False, False, 0)

        content.show_all()
        response = dlg.run()
        stamp = None
        novo_fuso = None
        if response == Gtk.ResponseType.OK:
            year, month, day = cal.get_date()  # mês vem 0-indexado
            stamp = (f"{year:04d}-{month + 1:02d}-{day:02d} "
                     f"{int(hour.get_value()):02d}:{int(minute.get_value()):02d}:"
                     f"{int(second.get_value()):02d}")
            escolha = combo_fuso.get_active_id()
            if escolha and escolha != fuso_atual:
                novo_fuso = escolha
        dlg.destroy()
        # O fuso vai PRIMEIRO: trocá-lo depois de acertar a hora deslocaria o
        # horário que o usuário acabou de digitar.
        if novo_fuso:
            self._aplicar_fuso(novo_fuso)
        if stamp:
            self._apply_manual_time(stamp)

    def _apply_manual_time(self, stamp):
        def worker():
            # timedatectl recusa "set-time" com o ajuste automático ligado;
            # desligar antes é o mesmo comportamento de trocar a hora na mão
            # em outros sistemas.
            run_ok(["sudo", "-n", "timedatectl", "set-ntp", "false"], timeout=30)
            ok, _out, _err = run_ok(["sudo", "-n", "timedatectl", "set-time", stamp],
                                    timeout=30)
            GLib.idle_add(self._after_manual_time, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _after_manual_time(self, ok):
        if self._ntp_switch is not None:
            self._ntp_switch.set_active(False)
            self._ntp_switch.set_state(False)
        if ok:
            # A barra de cima não percebe um salto abrupto de hora sozinha:
            # só recalcula no próprio ciclo. Recarregá-la mostra a hora nova
            # na hora, em vez de só quando o usuário reparar.
            reiniciar_barra()
            self._info_dialog("Hora ajustada", "A data e a hora foram atualizadas.")
        else:
            self._info_dialog("Não foi possível ajustar", "O comando falhou.")
        return False

    def _on_idioma_changed(self, combo):
        escolha = combo.get_active_id()
        if not escolha or escolha == self._idioma_atual:
            return
        combo.set_sensitive(False)

        def worker():
            ok, saida, _ = run_ok(
                ["sudo", "-n", "/usr/local/sbin/tarsila-idioma", escolha],
                timeout=300)
            aplicado = any(l.startswith("OK=") for l in saida.splitlines())
            GLib.idle_add(self._after_idioma, combo, escolha, ok and aplicado)

        threading.Thread(target=worker, daemon=True).start()

    def _after_idioma(self, combo, escolha, ok):
        combo.set_sensitive(True)
        if ok:
            self._idioma_atual = escolha
            # Pergunta em vez de avisar: o idioma so vale de verdade depois de
            # reiniciar, e deixar o usuario descobrir isso sozinho seria deixa-lo
            # achando que a troca nao funcionou.
            dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                    message_type=Gtk.MessageType.QUESTION,
                                    text="Reiniciar agora?")
            dlg.format_secondary_text(
                "Para que as alterações de idioma possam ser feitas, é "
                "necessário reiniciar o sistema. Fazer isso agora?")
            dlg.add_button("Não", Gtk.ResponseType.NO)
            dlg.add_button("Sim", Gtk.ResponseType.YES)
            dlg.set_default_response(Gtk.ResponseType.NO)
            dlg.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
            resposta = dlg.run()
            dlg.destroy()
            if resposta == Gtk.ResponseType.YES:
                run_bg(["systemctl", "reboot"])
        else:
            # Volta o combo para onde estava: deixar mostrando a escolha nova
            # com o sistema no idioma velho seria mentir para o usuário.
            for i, (cod, _) in enumerate(IDIOMAS):
                if cod == self._idioma_atual:
                    combo.set_active(i)
                    break
            self._info_dialog("Não foi possível trocar o idioma",
                              "O comando falhou. O idioma continua o mesmo.")
        return False

    def _aplicar_fuso(self, zona):
        """Troca o fuso e espera terminar: quem chama precisa acertar a hora
        logo em seguida, e as duas coisas na ordem errada se atrapalham."""
        ok, _out, _err = run_ok(["sudo", "-n", "timedatectl", "set-timezone", zona],
                                timeout=30)
        if ok:
            reiniciar_barra()
        else:
            self._info_dialog("Não foi possível trocar o fuso",
                              "O comando falhou. O fuso continua como estava.")
        return ok

    def _on_timezone_changed(self, combo):
        tz = combo.get_active_id()
        if not tz:
            return
        combo.set_sensitive(False)

        def worker():
            ok, _out, _err = run_ok(["sudo", "-n", "timedatectl", "set-timezone", tz],
                                    timeout=30)
            GLib.idle_add(self._after_timezone_change, combo, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _after_timezone_change(self, combo, ok):
        combo.set_sensitive(True)
        if ok:
            # Mesma razão do ajuste manual de hora: o relógio da barra não
            # recalcula o deslocamento sozinho quando o fuso muda.
            reiniciar_barra()
        else:
            self._info_dialog("Não foi possível trocar o fuso", "O comando falhou.")
        return False

    def _on_version_activated(self, listbox, row):
        if self.state.get("dev_unlocked"):
            return
        self.about_clicks += 1
        remaining = 7 - self.about_clicks
        if remaining <= 0:
            self.state["dev_unlocked"] = True
            save_state(self.state)
            self._add_sidebar_row(*DEV_CATEGORY)
            self._info_dialog("Opções Avançadas ativadas",
                              "Um novo item apareceu no fim da lista à esquerda.")
        elif remaining <= 2:
            self.title_label.set_markup(
                f"<b>Faltam {remaining} toques…</b>")
            GLib.timeout_add(1500, self._restore_title)

    def _restore_title(self):
        cat_id = self.stack.get_visible_child_name()
        title = self.category_titles.get(cat_id, "Ajustes")
        self.title_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        return False

    def _info_dialog(self, title, text):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.INFO,
                                buttons=Gtk.ButtonsType.OK, text=title)
        dlg.format_secondary_text(text)
        dlg.run()
        dlg.destroy()

    # ---- Opções Avançadas (oculto por padrão) ----
    def _page_dev(self, box):
        card, lb = make_card("Ferramentas")
        box.pack_start(card, False, False, 0)
        add_tool_row(lb, "utilities-terminal", "Terminal", "",
                     ["xfce4-terminal"])
        add_tool_row(lb, "utilities-system-monitor", "Gerenciador de tarefas", "",
                     ["xfce4-taskmanager"])
        add_tool_row(lb, "applications-utilities",
                     "Editor de configurações (xfconf)", "",
                     ["xfce4-settings-editor"])

        card, lb = make_card("Painel e Dock")
        box.pack_start(card, False, False, 0)
        restart_panel_btn = Gtk.Button(label="Reiniciar")
        restart_panel_btn.connect("clicked", lambda *_: reiniciar_barra())
        add_row(lb, "view-refresh", "Reiniciar painel superior", "",
                restart_panel_btn)
        restart_dock_btn = Gtk.Button(label="Reiniciar")
        restart_dock_btn.connect("clicked", lambda *_: (
            subprocess.run(["pkill", "-u", os.environ.get("USER", ""), "plank"]),
            run_bg(["plank"])))
        add_row(lb, "view-refresh", "Reiniciar dock (Plank)", "",
                restart_dock_btn)
        add_tool_row(lb, "user-desktop", "Preferências do dock", "",
                     ["plank", "--preferences"])

        card, lb = make_card("Inicialização automática")
        box.pack_start(card, False, False, 0)
        autostart_dir = Path.home() / ".config" / "autostart"
        found = False
        if autostart_dir.exists():
            for f in sorted(autostart_dir.glob("*.desktop")):
                try:
                    text = f.read_text()
                except OSError:
                    continue
                found = True
                name = f.stem
                for line in text.splitlines():
                    if line.startswith("Name="):
                        name = line.split("=", 1)[1]
                        break
                enabled = "X-GNOME-Autostart-enabled=false" not in text
                sw = Gtk.Switch()
                sw.set_active(enabled)
                sw.connect("state-set", self._on_autostart_toggle, f)
                add_row(lb, "system-run", name, f.name, sw)
        if not found:
            add_row(lb, "system-run", "Inicialização automática",
                    "Nenhum aplicativo configurado")

        card, lb = make_card("Diagnóstico")
        box.pack_start(card, False, False, 0)
        logs_btn = Gtk.Button(label="Ver ›")
        logs_btn.connect("clicked", lambda *_: run_bg(
            ["xfce4-terminal", "-e", "journalctl -xe"]))
        add_row(lb, "text-x-generic", "Logs do sistema (journalctl)", "",
                logs_btn)
        add_row(lb, "applications-system", "Kernel", os.uname().release)

    def _on_autostart_toggle(self, switch, state, path):
        try:
            text = path.read_text()
        except OSError:
            return False
        lines = [l for l in text.splitlines()
                 if not l.startswith("X-GNOME-Autostart-enabled=")]
        lines.append(f"X-GNOME-Autostart-enabled={'true' if state else 'false'}")
        try:
            path.write_text("\n".join(lines) + "\n")
        except OSError:
            pass
        return False

    # -- navegação / busca --------------------------------------------------

    def _on_sidebar_row_selected(self, listbox, row):
        if row is None or not hasattr(row, "cat_id"):
            return
        self._select_category(row.cat_id, from_sidebar=True)

    def _select_category(self, cat_id, from_sidebar=False):
        self._ensure_page(cat_id)
        self.stack.set_visible_child_name(cat_id)
        title = self.category_titles.get(cat_id, cat_id)
        self.title_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")

        if not from_sidebar:
            for row in self.sidebar.get_children():
                if getattr(row, "cat_id", None) == cat_id:
                    self.sidebar.select_row(row)
                    break

    def _on_search_changed(self, entry):
        text = entry.get_text()
        for child in self.search_results.get_children():
            self.search_results.remove(child)
        results = self.index.search(text)
        if not results:
            self.search_popover.popdown()
            return
        for r in results:
            row = Gtk.ListBoxRow()
            row.result = r
            lbl = Gtk.Label(xalign=0)
            cat_title = self.category_titles.get(r["cat_id"], r["cat_id"])
            lbl.set_markup(
                f"{GLib.markup_escape_text(r['label'])}\n"
                f"<small><span alpha='65%'>{GLib.markup_escape_text(cat_title)}"
                f"</span></small>")
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(4)
            lbl.set_margin_bottom(4)
            row.add(lbl)
            row.show_all()
            self.search_results.add(row)
        self.search_popover.popup()

    def _on_search_result_activated(self, listbox, row):
        result = getattr(row, "result", None)
        self.search_popover.popdown()
        self.search_entry.set_text("")
        if result:
            self._select_category(result["cat_id"])

    def _on_key_press(self, widget, event):
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        if ctrl and event.keyval in (Gdk.KEY_f, Gdk.KEY_slash):
            self.search_entry.grab_focus()
            return True
        return False


class TarsilaConfigApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="br.org.tarsila.config")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = TarsilaConfigWindow(self)
        win.present()


if __name__ == "__main__":
    TarsilaConfigApp().run(None)

