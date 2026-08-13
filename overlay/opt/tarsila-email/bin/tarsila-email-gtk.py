#!/usr/bin/env python3
"""Tarsila Email — UI 100% GTK3 (sem WebKit)."""
import base64
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from lib.api_client import Api, ApiError  # noqa: E402

PORT = int(os.environ.get("TARSILA_EMAIL_PORT", "8475"))
BACKEND = RAIZ / "bin" / "tarsila-email-backend.py"
IDLE = RAIZ / "bin" / "tarsila-email-idle.py"
CSS = RAIZ / "ui" / "css" / "gmail-gtk.css"
LOG_DIR = Path.home() / ".local" / "share" / "tarsila-email"
IDLE_PID = LOG_DIR / "idle.pid"
WIN_W, WIN_H = 960, 620
PAGE_SIZE = 10
FOLDER_ORDER = ["inbox", "sent", "drafts", "starred", "spam", "trash"]
FOLDER_ICONS = {
    "inbox": "mail-inbox-symbolic",
    "sent": "mail-sent-symbolic",
    "drafts": "mail-drafts-symbolic",
    "starred": "mail-flagged-symbolic",
    "spam": "mail-mark-junk-symbolic",
    "trash": "user-trash-symbolic",
}

_backend_proc = None
_we_backend = False


def fmt_date(s: str) -> str:
    if not s:
        return ""
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[:12]
    now = datetime.now(d.tzinfo) if d.tzinfo else datetime.now()
    if d.date() == now.date():
        return d.strftime("%H:%M")
    return d.strftime("%d %b")


def html_to_plain(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()


def _api_ok() -> bool:
    return Api(PORT).ok()


def _start_backend():
    global _backend_proc, _we_backend
    if _api_ok():
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / "backend.log", "a", encoding="utf-8")  # noqa: SIM115
    _backend_proc = subprocess.Popen(
        [sys.executable, "-u", str(BACKEND)],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _we_backend = True
    for _ in range(40):
        if _api_ok():
            return
        time.sleep(0.25)
    raise RuntimeError("Backend não respondeu")


def _stop_backend():
    global _backend_proc, _we_backend
    if not _we_backend or _backend_proc is None:
        return
    if _backend_proc.poll() is None:
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()


def _ensure_idle():
    if not IDLE.is_file():
        return
    subprocess.run(
        ["pkill", "-f", "/opt/tarsila-email/bin/tarsila-email-idle.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.25)
    IDLE_PID.unlink(missing_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / "idle.log", "a", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(
        [sys.executable, "-u", str(IDLE)],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    IDLE_PID.write_text(str(proc.pid))


def _load_css():
    if not CSS.is_file():
        return
    provider = Gtk.CssProvider()
    provider.load_from_path(str(CSS))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def _run_bg(fn, on_done):
    def worker():
        err = None
        result = None
        try:
            result = fn()
        except Exception as e:
            err = e
        GLib.idle_add(on_done, result, err)

    threading.Thread(target=worker, daemon=True).start()


def _set_class(widget, name: str, active: bool):
    ctx = widget.get_style_context()
    if active:
        ctx.add_class(name)
    else:
        ctx.remove_class(name)


    def __init__(self, parent, api: Api, on_sent):
        super().__init__(
            title="Nova mensagem",
            transient_for=parent,
            modal=True,
            default_width=560,
        )
        self.api = api
        self.on_sent = on_sent
        self.attachments = []
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        box = self.get_content_area()
        box.set_spacing(0)
        box.get_style_context().add_class("tarsila-compose-dialog")

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.get_style_context().add_class("tarsila-compose-head")
        head.set_margin_bottom(0)
        lbl = Gtk.Label(label="Nova mensagem", xalign=0)
        lbl.get_style_context().add_class("tarsila-compose-head")
        head.pack_start(lbl, True, True, 0)
        head.pack_end(Gtk.Label(), False, False, 0)
        box.pack_start(head, False, False, 0)

        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        fields.set_border_width(16)
        self.entry_to = Gtk.Entry()
        self.entry_to.set_placeholder_text("Para")
        self.entry_subj = Gtk.Entry()
        self.entry_subj.set_placeholder_text("Assunto")
        self.text_body = Gtk.TextView()
        self.text_body.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_body.set_size_request(-1, 260)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.text_body)
        self.attach_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        btn_attach = Gtk.Button(label="📎 Anexar")
        btn_attach.connect("clicked", self._on_attach)
        fields.pack_start(self.entry_to, False, False, 0)
        fields.pack_start(self.entry_subj, False, False, 0)
        fields.pack_start(scroll, True, True, 0)
        fields.pack_start(btn_attach, False, False, 0)
        fields.pack_start(self.attach_box, False, False, 0)
        box.pack_start(fields, True, True, 0)

        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_border_width(12)
        foot.set_halign(Gtk.Align.END)
        btn_draft = Gtk.Button(label="Rascunho")
        btn_draft.get_style_context().add_class("tarsila-btn-secondary")
        btn_draft.connect("clicked", self._on_draft)
        btn_send = Gtk.Button(label="Enviar")
        btn_send.get_style_context().add_class("tarsila-btn-primary")
        btn_send.connect("clicked", self._on_send)
        foot.pack_end(btn_send, False, False, 0)
        foot.pack_end(btn_draft, False, False, 0)
        box.pack_start(foot, False, False, 0)
        box.show_all()

    def set_content(self, to="", subject="", body=""):
        self.entry_to.set_text(to)
        self.entry_subj.set_text(subject)
        self.text_body.get_buffer().set_text(body)

    def _body_text(self):
        return self.text_body.get_buffer().get_text(
            self.text_body.get_buffer().get_start_iter(),
            self.text_body.get_buffer().get_end_iter(),
            False,
        )

    def _on_attach(self, _btn):
        dlg = Gtk.FileChooserDialog(
            "Anexar arquivos",
            self,
            Gtk.FileChooserAction.OPEN,
            ("Cancelar", Gtk.ResponseType.CANCEL, "Anexar", Gtk.ResponseType.OK),
        )
        dlg.set_select_multiple(True)
        if dlg.run() == Gtk.ResponseType.OK:
            for path in dlg.get_filenames():
                data = Path(path).read_bytes()
                self.attachments.append({
                    "name": Path(path).name,
                    "data": base64.b64encode(data).decode(),
                })
                self.attach_box.pack_start(Gtk.Label(label=Path(path).name, xalign=0), False, False, 0)
                self.attach_box.show_all()
        dlg.destroy()

    def _on_draft(self, _btn):
        _run_bg(
            lambda: self.api.post("/api/drafts", {
                "to": self.entry_to.get_text(),
                "subject": self.entry_subj.get_text(),
                "body": self._body_text(),
            }),
            lambda _r, err: self._alert(err, "Rascunho salvo no Gmail", "Erro"),
        )

    def _on_send(self, _btn):
        to = [s.strip() for s in re.split(r"[,;]", self.entry_to.get_text()) if s.strip()]
        if not to:
            self._alert(None, None, "Informe o destinatário")
            return
        dest = ", ".join(to)
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Confirma o envio desse e-mail para {dest}?",
        )
        if dlg.run() != Gtk.ResponseType.YES:
            dlg.destroy()
            return
        dlg.destroy()

        payload = {
            "to": to,
            "subject": self.entry_subj.get_text(),
            "body": self._body_text(),
            "attachments": self.attachments,
        }

        def done(_r, err):
            if err:
                self._alert(err, None, "Erro ao enviar")
                return
            self.destroy()
            self.on_sent()

        _run_bg(lambda: self.api.post("/api/messages/send", payload), done)

    def _alert(self, err, ok_msg, err_title):
        if err:
            Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"{err_title}: {err}",
            ).run()
        elif ok_msg:
            Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=ok_msg,
            ).run()


class AccountsDialog(Gtk.Dialog):
    def __init__(self, parent, api: Api, accounts, on_changed):
        super().__init__(
            title="Contas",
            transient_for=parent,
            modal=True,
            default_width=400,
        )
        self.api = api
        self.accounts = accounts
        self.on_changed = on_changed
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        box = self.get_content_area()
        box.set_border_width(0)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        head.set_border_width(14)
        head.pack_start(Gtk.Label(label="Contas", xalign=0), True, True, 0)
        box.pack_start(head, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(280)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll.add(self.listbox)
        box.pack_start(scroll, True, True, 0)

        btn_add = Gtk.Button(label="+ Adicionar conta")
        btn_add.set_margin_left(16)
        btn_add.set_margin_right(16)
        btn_add.set_margin_bottom(16)
        btn_add.connect("clicked", self._on_add)
        box.pack_start(btn_add, False, False, 0)

        self._render()
        box.show_all()

    def _render(self):
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        for acc in self.accounts:
            row = Gtk.ListBoxRow()
            if acc.get("active"):
                row.get_style_context().add_class("tarsila-account-row")
                row.get_style_context().add_class("active")
            h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            h.set_border_width(12)
            av = Gtk.Image.new_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DIALOG)
            EmailWindow.apply_profile_avatar(
                av, self.api, acc.get("avatar", ""), acc.get("email", ""), 36
            )
            h.pack_start(av, False, False, 0)
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            em = Gtk.Label(label=acc.get("email", ""), xalign=0)
            em.get_style_context().add_class("tarsila-msg-from")
            nm = Gtk.Label(
                label=(acc.get("name") or "") + (" · ativa" if acc.get("active") else ""),
                xalign=0,
            )
            nm.get_style_context().add_class("tarsila-msg-snippet")
            info.pack_start(em, False, False, 0)
            info.pack_start(nm, False, False, 0)
            h.pack_start(info, True, True, 0)
            row.add(h)
            row.email = acc.get("email")
            row.active = acc.get("active")
            row.connect("button-press-event", self._on_row_click)
            self.listbox.add(row)
        self.listbox.show_all()

    def _on_row_click(self, row, _ev):
        if row.active:
            self.destroy()
            return
        _run_bg(
            lambda: self.api.post("/api/accounts/switch", {"email": row.email}),
            lambda _r, err: GLib.idle_add(self._after_switch, err),
        )

    def _after_switch(self, err):
        if err:
            Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=str(err),
            ).run()
            return
        self.destroy()
        self.on_changed()

    def _on_add(self, _btn):
        self.destroy()
        _run_bg(lambda: self.api.post("/api/accounts/open-setup"), lambda _r, _e: None)


class MessageRow(Gtk.ListBoxRow):
    def __init__(self, msg, on_star):
        super().__init__()
        self.msg_id = msg["id"]
        self.on_star = on_star
        self.get_style_context().add_class("tarsila-msg-row")
        if not msg.get("is_read"):
            self.get_style_context().add_class("unread")

        grid = Gtk.Grid(column_spacing=8, row_spacing=4)
        grid.set_margin_top(12)
        grid.set_margin_bottom(12)
        grid.set_margin_start(16)
        grid.set_margin_end(16)

        star = Gtk.Button(label="★")
        star.get_style_context().add_class("tarsila-star-btn")
        if msg.get("is_starred"):
            star.get_style_context().add_class("on")
        star.connect("clicked", self._star_clicked)
        grid.attach(star, 0, 0, 1, 3)

        from_lbl = Gtk.Label(label=msg.get("sender", ""), xalign=0)
        from_lbl.set_hexpand(True)
        from_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        from_lbl.get_style_context().add_class("tarsila-msg-from")
        if not msg.get("is_read"):
            from_lbl.get_style_context().add_class("unread")

        date_lbl = Gtk.Label(label=fmt_date(msg.get("date_str", "")))
        date_lbl.set_halign(Gtk.Align.END)
        date_lbl.get_style_context().add_class("tarsila-msg-date")

        subj = Gtk.Label(label=msg.get("subject", "(sem assunto)"), xalign=0)
        subj.set_ellipsize(Pango.EllipsizeMode.END)
        subj.get_style_context().add_class("tarsila-msg-subject")
        if not msg.get("is_read"):
            subj.get_style_context().add_class("unread")

        snippet = Gtk.Label(label=msg.get("snippet", ""), xalign=0)
        snippet.set_ellipsize(Pango.EllipsizeMode.END)
        snippet.get_style_context().add_class("tarsila-msg-snippet")

        grid.attach(from_lbl, 1, 0, 1, 1)
        grid.attach(date_lbl, 2, 0, 1, 1)
        grid.attach(subj, 1, 1, 2, 1)
        grid.attach(snippet, 1, 2, 2, 1)
        self.add(grid)

    def _star_clicked(self, btn):
        _run_bg(
            lambda: Api(PORT).post(f"/api/messages/{self.msg_id}/star"),
            lambda _r, err: GLib.idle_add(self.on_star, err) if not err else None,
        )
        _set_class(btn, "on", True)


class EmailWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Tarsila Email", default_width=WIN_W, default_height=WIN_H)
        self.api = Api(PORT)
        self.folder = "inbox"
        self.page = 1
        self.search_query = ""
        self.selected_id = None
        self.accounts = []
        self.has_more = False
        self._search_timer = None

        self.set_icon_name("internet-mail")
        GLib.set_application_name("Tarsila Email")
        Gdk.set_program_class("tarsila-email")
        self.get_style_context().add_class("tarsila-window")
        self.connect("delete-event", self._on_close)

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(outer)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(220, -1)
        sidebar.get_style_context().add_class("tarsila-sidebar")
        logo = Gtk.Label(label="Tarsila Email", xalign=0)
        logo.get_style_context().add_class("tarsila-logo")
        sidebar.pack_start(logo, False, False, 0)

        btn_compose = Gtk.Button(label="✎ Escrever")
        btn_compose.get_style_context().add_class("tarsila-compose-btn")
        btn_compose.connect("clicked", lambda *_: self._show_compose())
        sidebar.pack_start(btn_compose, False, False, 0)

        self.folder_list = Gtk.ListBox()
        self.folder_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.folder_list.connect("row-activated", self._on_folder_activated)
        sidebar.pack_start(self.folder_list, True, True, 0)

        foot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        foot.set_border_width(8)
        self.sync_msg = Gtk.Label(label="", xalign=0)
        self.sync_msg.get_style_context().add_class("tarsila-msg-snippet")
        self.sync_msg.set_no_show_all(True)
        btn_sync = Gtk.Button(label="↻ Sincronizar e-mail")
        btn_sync.get_style_context().add_class("tarsila-sync-btn")
        btn_sync.connect("clicked", lambda *_: self._sync_and_load())
        foot.pack_start(self.sync_msg, False, False, 0)
        foot.pack_start(btn_sync, False, False, 0)
        sidebar.pack_start(foot, False, False, 0)
        outer.pack_start(sidebar, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.pack_start(main, True, True, 0)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toolbar.get_style_context().add_class("tarsila-toolbar")
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar e-mails")
        self.search.get_style_context().add_class("tarsila-search")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", self._on_search)
        toolbar.pack_start(self.search, True, True, 0)

        self.account_label = Gtk.Label(label="")
        self.account_label.get_style_context().add_class("tarsila-account-label")
        self.account_label.set_max_width_chars(28)
        self.account_label.set_ellipsize(Pango.EllipsizeMode.END)
        toolbar.pack_start(self.account_label, False, False, 0)

        self.profile_img = Gtk.Image.new_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DIALOG)
        self.profile_btn = Gtk.MenuButton()
        self.profile_btn.set_image(self.profile_img)
        menu = Gtk.Menu()
        item_accounts = Gtk.MenuItem(label="Adicionar/Alterar conta")
        item_accounts.connect("activate", self._on_accounts)
        item_logout = Gtk.MenuItem(label="Sair")
        item_logout.connect("activate", self._on_logout)
        menu.append(item_accounts)
        menu.append(item_logout)
        menu.show_all()
        self.profile_btn.set_popup(menu)
        toolbar.pack_start(self.profile_btn, False, False, 0)
        main.pack_start(toolbar, False, False, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(380)
        main.pack_start(paned, True, True, 0)

        list_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        list_wrap.get_style_context().add_class("tarsila-list-pane")
        self.loading_lbl = Gtk.Label(label="Carregando…")
        self.loading_lbl.get_style_context().add_class("tarsila-loading")
        list_wrap.pack_start(self.loading_lbl, False, False, 0)
        scroll_list = Gtk.ScrolledWindow()
        scroll_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.msg_list = Gtk.ListBox()
        self.msg_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.msg_list.connect("row-activated", self._on_msg_activated)
        scroll_list.add(self.msg_list)
        list_wrap.pack_start(scroll_list, True, True, 0)
        self.btn_more = Gtk.Button(label="Mais antigos")
        self.btn_more.get_style_context().add_class("tarsila-more-btn")
        self.btn_more.set_no_show_all(True)
        self.btn_more.connect("clicked", self._on_more)
        list_wrap.pack_start(self.btn_more, False, False, 0)
        paned.pack1(list_wrap, False, False)

        read_scroll = Gtk.ScrolledWindow()
        read_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        read_scroll.get_style_context().add_class("tarsila-read-pane")
        self.read_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.read_box.set_border_width(24)
        self.read_empty = Gtk.Label(label="Selecione um e-mail")
        self.read_empty.get_style_context().add_class("tarsila-read-empty")
        self.read_box.pack_start(self.read_empty, False, False, 0)
        read_scroll.add(self.read_box)
        paned.pack2(read_scroll, True, False)

        self.show_all()
        _run_bg(self._load_status, self._after_status)

    @staticmethod
    def load_avatar_pixbuf(api: Api, avatar_path: str, email: str = "", size: int = 40):
        from lib import avatar as avmod

        data = avmod.read_cache_for_email(email) if email else None
        if not data and avatar_path:
            if avatar_path.startswith("http"):
                try:
                    req = urllib.request.Request(avatar_path, headers={"User-Agent": "TarsilaEmail/2.1"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        data = r.read()
                except Exception:
                    data = None
            elif avatar_path.startswith("/"):
                data = api.fetch_bytes(avatar_path)
        if not data:
            return None
        try:
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(data)
            loader.close()
            pix = loader.get_pixbuf()
            if pix:
                return pix.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        except Exception:
            pass
        return None

    @staticmethod
    def apply_profile_avatar(widget: Gtk.Image, api: Api, avatar_path: str, email: str, size: int = 40):
        def render(pix):
            if pix:
                widget.set_from_pixbuf(pix)
            else:
                widget.set_from_icon_name("avatar-default-symbolic", Gtk.IconSize.DIALOG)

        # Cache quente: desenha na hora, sem rede. O read_cache_for_email e
        # leitura de disco (rapida) e o fetch_bytes so roda quando o avatar
        # local ja existe — nunca bloqueia.
        pix = EmailWindow.load_avatar_pixbuf(api, avatar_path, email, size)
        if pix:
            render(pix)
            return
        if not email:
            render(None)
            return

        # Cache frio: resolve_avatar baixa (bloqueante) e re-le a partir do
        # cache. Roda em thread de fundo e volta via idle_add — a UI nao trava.
        def work():
            from lib import avatar as avmod
            avmod.resolve_avatar(email)
            return EmailWindow.load_avatar_pixbuf(api, avatar_path, email, size)

        _run_bg(work, lambda p, _err: render(p))

    def _on_close(self, *_):
        _stop_backend()
        Gtk.main_quit()
        return False

    def _toast(self, msg, is_error=False):
        self.sync_msg.set_text(msg)
        self.sync_msg.show()
        if hasattr(self, "_toast_src") and self._toast_src:
            GLib.source_remove(self._toast_src)
        self._toast_src = GLib.timeout_add_seconds(10, self._hide_toast)

    def _hide_toast(self):
        self.sync_msg.hide()
        return False

    def _load_status(self):
        st = self.api.get("/api/bootstrap")
        if not st.get("configured"):
            raise ApiError("Não configurado")
        return st

    def _after_status(self, st, err):
        if err:
            Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=str(err),
            ).run()
            Gtk.main_quit()
            return
        self.accounts = st.get("accounts") or []
        self.account_label.set_text(st.get("email", ""))
        EmailWindow.apply_profile_avatar(
            self.profile_img, self.api, st.get("avatar", ""), st.get("email", ""), 40
        )
        self._render_folders(st.get("folders") or [{"id": "inbox", "name": "Caixa de entrada"}])

    def _render_folders(self, folders):
        for row in self.folder_list.get_children():
            self.folder_list.remove(row)
        folders.sort(
            key=lambda f: FOLDER_ORDER.index(f["id"]) if f["id"] in FOLDER_ORDER else 99
        )
        for i, f in enumerate(folders):
            row = Gtk.ListBoxRow()
            row.folder_id = f["id"]
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(16)
            box.set_margin_end(16)
            icon = Gtk.Image.new_from_icon_name(
                FOLDER_ICONS.get(f["id"], "folder-symbolic"), Gtk.IconSize.MENU
            )
            lbl = Gtk.Label(label=f.get("name", f["id"]), xalign=0)
            lbl.get_style_context().add_class("tarsila-folder-label")
            box.pack_start(icon, False, False, 0)
            box.pack_start(lbl, True, True, 0)
            row.add(box)
            row.get_style_context().add_class("tarsila-folder-row")
            if f["id"] == self.folder:
                row.get_style_context().add_class("active")
                self.folder_list.select_row(row)
            self.folder_list.add(row)
        self.folder_list.show_all()
        self._sync_and_load()

    def _on_folder_activated(self, _lb, row):
        self.folder = row.folder_id
        self.page = 1
        self.selected_id = None
        self.search_query = ""
        self.search.set_text("")
        for r in self.folder_list.get_children():
            _set_class(r, "active", r.folder_id == self.folder)
        self._clear_read()
        self._load_messages()

    def _on_search(self, entry):
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        text = entry.get_text().strip()

        def fire():
            self.search_query = text
            self.page = 1
            self._load_messages()
            return False

        self._search_timer = GLib.timeout_add(300, fire)

    def _sync_and_load(self):
        self.loading_lbl.set_text("Sincronizando…")
        self.loading_lbl.show()

        def work():
            return self.api.post("/api/sync", {"folder": self.folder, "limit": PAGE_SIZE})

        def done(data, err):
            if err:
                self._toast(f"Erro de sincronização: {err}", True)
                self._load_messages()
                return
            self._toast("Sincronização feita")
            if self.search_query:
                self._load_messages()
                return
            self.loading_lbl.hide()
            for row in self.msg_list.get_children():
                self.msg_list.remove(row)
            for m in data.get("messages") or []:
                row = MessageRow(m, on_star=lambda e: self._load_messages() if not e else None)
                if m["id"] == self.selected_id:
                    row.get_style_context().add_class("selected")
                self.msg_list.add(row)
            self.msg_list.show_all()
            self.has_more = data.get("has_more", False)
            if self.has_more:
                self.btn_more.show()
            else:
                self.btn_more.hide()

        _run_bg(work, done)

    def _load_messages(self, append=False):
        if not append:
            for row in self.msg_list.get_children():
                self.msg_list.remove(row)
            if not self.search_query:
                self.page = 1

        def work():
            p = f"/api/messages?folder={self.folder}&page={self.page}&limit={PAGE_SIZE}"
            if self.search_query:
                p += f"&q={urllib.parse.quote(self.search_query)}"
            return self.api.get(p)

        def done(data, err):
            self.loading_lbl.hide()
            if err:
                self.loading_lbl.set_text(f"Erro: {err}")
                self.loading_lbl.show()
                return
            for m in data.get("messages") or []:
                row = MessageRow(m, on_star=lambda e: self._load_messages() if not e else None)
                if m["id"] == self.selected_id:
                    row.get_style_context().add_class("selected")
                self.msg_list.add(row)
            self.msg_list.show_all()
            self.has_more = data.get("has_more", False) and not self.search_query
            if self.has_more:
                self.btn_more.show()
            else:
                self.btn_more.hide()

        _run_bg(work, done)

    def _on_more(self, _btn):
        self.page += 1
        self._load_messages(append=True)

    def _on_msg_activated(self, _lb, row):
        self._open_message(row.msg_id)

    def _clear_read(self):
        for child in self.read_box.get_children():
            if child is not self.read_empty:
                self.read_box.remove(child)
        self.read_empty.show()

    def _open_message(self, msg_id):
        self.selected_id = msg_id
        for row in self.msg_list.get_children():
            _set_class(row, "selected", row.msg_id == msg_id)
        self.read_empty.hide()
        for child in self.read_box.get_children():
            if child is not self.read_empty:
                self.read_box.remove(child)
        loading = Gtk.Label(label="Abrindo…")
        loading.get_style_context().add_class("tarsila-loading")
        self.read_box.pack_start(loading, False, False, 0)
        loading.show_all()

        def work():
            self.api.post(f"/api/messages/{msg_id}/read", {"read": True})
            return self.api.get(f"/api/messages/{msg_id}?body=1&fmt=plain")

        def done(data, err):
            for child in self.read_box.get_children():
                if child is not self.read_empty:
                    self.read_box.remove(child)
            if err:
                self.read_box.pack_start(Gtk.Label(label=str(err)), False, False, 0)
                self.read_box.show_all()
                return
            m = data.get("message") or {}
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            btn_reply = Gtk.Button(label="Responder")
            btn_reply.get_style_context().add_class("tarsila-action-btn")
            btn_star = Gtk.Button(label="★ Estrela")
            btn_star.get_style_context().add_class("tarsila-action-btn")
            btn_trash = Gtk.Button(label="Apagar")
            btn_trash.get_style_context().add_class("tarsila-action-btn")
            btn_trash.get_style_context().add_class("tarsila-action-danger")
            actions.pack_start(btn_reply, False, False, 0)
            actions.pack_start(btn_star, False, False, 0)
            actions.pack_start(btn_trash, False, False, 0)

            subj = Gtk.Label(label=m.get("subject", ""), xalign=0)
            subj.get_style_context().add_class("tarsila-read-subject")
            subj.set_line_wrap(True)

            meta = Gtk.Label(
                label=f"{m.get('sender', '')}\n{m.get('date_str', '')}",
                xalign=0,
            )
            meta.get_style_context().add_class("tarsila-read-meta")

            body_txt = m.get("body_plain") or html_to_plain(m.get("body_html") or "") or m.get("snippet", "")
            body = Gtk.TextView()
            body.set_editable(False)
            body.set_cursor_visible(False)
            body.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            body.get_style_context().add_class("tarsila-read-body")
            body.get_buffer().set_text(body_txt)
            body_scroll = Gtk.ScrolledWindow()
            body_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            body_scroll.set_min_content_height(200)
            body_scroll.add(body)

            self.read_box.pack_start(actions, False, False, 0)
            self.read_box.pack_start(subj, False, False, 0)
            self.read_box.pack_start(meta, False, False, 0)
            self.read_box.pack_start(body_scroll, True, True, 0)

            btn_trash.connect("clicked", lambda *_: self._trash_message(msg_id))
            btn_star.connect("clicked", lambda *_: self._star_message(msg_id))
            btn_reply.connect(
                "clicked",
                lambda *_: self._show_compose(
                    re.sub(r"<.*>", "", m.get("sender", "")).strip(),
                    "Re: " + (m.get("subject") or ""),
                    "\n\n---\n" + body_txt,
                ),
            )
            self.read_box.show_all()

        _run_bg(work, done)

    def _trash_message(self, msg_id):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Você deseja apagar esse e-mail?",
        )
        if dlg.run() != Gtk.ResponseType.YES:
            dlg.destroy()
            return
        dlg.destroy()

        def done(_r, err):
            if err:
                self._toast(str(err), True)
                return
            self._clear_read()
            self._load_messages()

        _run_bg(lambda: self.api.post(f"/api/messages/{msg_id}/trash"), done)

    def _star_message(self, msg_id):
        _run_bg(
            lambda: self.api.post(f"/api/messages/{msg_id}/star"),
            lambda _r, err: self._open_message(msg_id) if not err else self._toast(str(err), True),
        )

    def _show_compose(self, to="", subject="", body=""):
        dlg = ComposeDialog(self, self.api, on_sent=lambda: self._after_sent())
        dlg.set_content(to, subject, body)
        dlg.show_all()

    def _after_sent(self):
        self.folder = "sent"
        for row in self.folder_list.get_children():
            _set_class(row, "active", row.folder_id == self.folder)
        self._sync_and_load()

    def _on_accounts(self, _item):
        def done(data, err):
            if err:
                self._toast(str(err), True)
                return
            self.accounts = data.get("accounts") or []
            AccountsDialog(self, self.api, self.accounts, on_changed=self._reload_account).show_all()

        _run_bg(lambda: self.api.get("/api/accounts"), done)

    def _reload_account(self):
        def done(st, err):
            if err:
                return
            self.accounts = st.get("accounts") or []
            self.account_label.set_text(st.get("email", ""))
            EmailWindow.apply_profile_avatar(
                self.profile_img, self.api, st.get("avatar", ""), st.get("email", ""), 40
            )
            self.folder = "inbox"
            self.page = 1
            self.selected_id = None
            self._render_folders(st.get("folders") or [{"id": "inbox", "name": "Caixa de entrada"}])

        _run_bg(self._load_status, done)

    def _on_logout(self, _item):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Sair apaga todas as contas e dados locais. Continuar?",
        )
        if dlg.run() != Gtk.ResponseType.YES:
            dlg.destroy()
            return
        dlg.destroy()

        def done(_r, err):
            if err:
                Gtk.MessageDialog(
                    transient_for=self, modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"Não foi possível sair: {err}",
                ).run()
                return
            # Volta ao assistente de configuração (não reabrir o GTK vazio).
            setup = RAIZ / "bin" / "tarsila-email-setup.py"
            if setup.is_file():
                subprocess.Popen(
                    [sys.executable, str(setup)],
                    env={
                        **os.environ,
                        "DISPLAY": os.environ.get("DISPLAY", ":0"),
                        "TARSILA_EMAIL_FROM_APP": "1",
                    },
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            Gtk.main_quit()

        _run_bg(lambda: self.api.post("/api/logout"), done)


def main():
    if not BACKEND.is_file():
        sys.stderr.write(f"Backend ausente: {BACKEND}\n")
        sys.exit(1)
    _load_css()
    _start_backend()
    _ensure_idle()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    EmailWindow()
    Gtk.main()


if __name__ == "__main__":
    main()
