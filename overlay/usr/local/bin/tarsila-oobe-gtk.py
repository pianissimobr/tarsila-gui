#!/usr/bin/env python3
"""Tarsila OOBE — assistente de primeiro boot.

Roda como tarsila-oobe, sem WM, em tela cheia. Lê o estado da senha do
root de /etc/tarsila/oobe-root-state (escrito pelo tarsila-oobe-init).
Ao concluir chama sudo tarsila-user-provision, que cria o usuário, aplica
skel + openbox, gera sudoers e reinicia o lightdm.
"""
import re
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

CSS = b"""
* { font-family: Sans, sans-serif; }
window { background-color: #1a1a1a; }
.title { font-size: 22px; font-weight: bold; color: #ffffff; }
.subtitle { font-size: 12px; color: #aaaaaa; }
.info { font-size: 11px; color: #888888; }
.danger { font-size: 13px; color: #ff5544; font-weight: bold; }
.step-label { font-size: 10px; color: #666666; }
.field-title { font-size: 12px; color: #cccccc; }
.entry-field {
    font-size: 16px; padding: 8px 12px;
    border-radius: 6px;
    background-color: #2a2a2a; color: #ffffff;
    border: 2px solid #444444;
    caret-color: #ffffff;
}
.entry-field:focus { border-color: #4488ff; }
.btn-primary {
    font-size: 16px; font-weight: bold;
    padding: 10px 24px; border-radius: 8px;
    background-color: #4488ff; color: #ffffff;
    border: none;
}
.btn-primary:hover { background-color: #5599ff; }
.btn-primary:disabled { background-color: #2a2a2a; color: #555555; }
.btn-secondary {
    font-size: 14px;
    padding: 8px 20px; border-radius: 8px;
    background-color: #333333; color: #cccccc;
    border: none;
}
.btn-secondary:hover { background-color: #444444; }
.btn-danger {
    font-size: 14px; font-weight: bold;
    padding: 8px 24px; border-radius: 8px;
    background-color: #cc3333; color: #ffffff;
    border: none;
}
.btn-danger:hover { background-color: #dd4444; }
.error-msg { font-size: 12px; color: #ff5544; }
.progress-msg { font-size: 14px; color: #cccccc; }
"""


def _apply_css():
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _read_root_state():
    try:
        with open("/etc/tarsila/oobe-root-state") as f:
            return f.read().strip()
    except Exception:
        return "ok"


def _password_strength(pw):
    if len(pw) < 6:
        return 0
    score = 0
    if len(pw) >= 8:
        score += 1
    if len(pw) >= 12:
        score += 1
    if re.search(r"[a-z]", pw):
        score += 1
    if re.search(r"[A-Z]", pw):
        score += 1
    if re.search(r"\d", pw):
        score += 1
    if re.search(r"[^a-zA-Z0-9]", pw):
        score += 1
    return min(score, 4)


def _center_label(text, css_class):
    lbl = Gtk.Label(label=text)
    lbl.get_style_context().add_class(css_class)
    lbl.set_halign(Gtk.Align.CENTER)
    lbl.set_justify(Gtk.Justification.CENTER)
    return lbl


def _make_entry(placeholder=""):
    e = Gtk.Entry()
    e.set_placeholder_text(placeholder)
    e.set_has_frame(False)
    e.get_style_context().add_class("entry-field")
    return e


def _make_password_entry(placeholder="Senha"):
    e = _make_entry(placeholder)
    e.set_visibility(False)
    e.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "dialog-password")
    e.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Mostrar/ocultar senha")
    e.connect("icon-press", lambda ent, pos, ev: (
        ent.set_visibility(not ent.get_visibility())))
    return e


class _StrengthBar(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(-1, 8)
        self.strength = 0
        self.connect("draw", self._draw)

    def set_strength(self, s):
        self.strength = s
        self.queue_draw()

    def _draw(self, widget, cr):
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        cr.set_source_rgba(0.27, 0.27, 0.27, 1)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if self.strength > 0:
            colors = [
                (0.80, 0.20, 0.20), (0.80, 0.53, 0.20),
                (0.53, 0.80, 0.20), (0.20, 0.80, 0.20),
            ]
            r, g, b = colors[min(self.strength - 1, 3)]
            cr.set_source_rgba(r, g, b, 1)
            cr.rectangle(0, 0, max(w // 4, 1) * self.strength, h)
            cr.fill()


class _RootPage(Gtk.Box):
    """Etapa 1 — senha do root. Dois estados internos: warning (fraca) e form."""

    def __init__(self, root_state):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.root_state = root_state
        self.root_password = ""

        step = _center_label("1 / 2 — Senha de Administrador", "step-label")
        self.pack_start(step, False, False, 24)

        title = _center_label("Cadastre uma senha de Administrador", "title")
        self.pack_start(title, False, False, 8)

        subtitle = _center_label(
            "Essa senha é muito importante.\n"
            "Grave-a bem ou guarde-a em um local seguro.", "subtitle")
        self.pack_start(subtitle, False, False, 24)

        # --- aviso de senha fraca ---
        warn = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        warn.pack_start(_center_label("Sua senha de administrador é fraca.", "danger"), False, False, 0)
        warn.pack_start(_center_label("O seu sistema corre perigo!", "danger"), False, False, 0)
        self.warning_box = warn
        self.pack_start(warn, False, False, 8)

        # --- formulário (senha + confirmação) ---
        self.form = self._build_form()
        self.pack_start(self.form, False, False, 8)

        # --- mensagem de erro (fora do form, não empurra botões) ---
        self.error_label = _center_label("", "error-msg")
        self.pack_start(self.error_label, False, False, 2)

        # --- botões ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.setup_btn = Gtk.Button(label="Cadastrar nova senha")
        self.setup_btn.get_style_context().add_class("btn-danger")
        self.setup_btn.connect("clicked", lambda b: self._show_form())
        btn_box.pack_start(self.setup_btn, False, False, 0)

        self.next_btn = Gtk.Button(label="Próximo")
        self.next_btn.get_style_context().add_class("btn-primary")
        self.next_btn.connect("clicked", lambda b: self._on_next())
        btn_box.pack_start(self.next_btn, False, False, 0)

        self.pack_start(btn_box, False, False, 24)

        if root_state == "weak":
            self._show_warning()
        else:
            self._show_form()

    def _build_form(self):
        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        lbl = Gtk.Label(label="Senha:")
        lbl.get_style_context().add_class("field-title")
        lbl.set_halign(Gtk.Align.START)
        f.pack_start(lbl, False, False, 0)

        self.pw_entry = _make_password_entry("Digite a senha de administrador")
        self.pw_entry.connect("changed", self._on_pw_changed)
        f.pack_start(self.pw_entry, False, False, 0)

        lbl2 = Gtk.Label(label="Confirmar senha:")
        lbl2.get_style_context().add_class("field-title")
        lbl2.set_halign(Gtk.Align.START)
        f.pack_start(lbl2, False, False, 2)

        self.pw_confirm = _make_password_entry("Confirme a senha")
        self.pw_confirm.connect("changed", self._on_pw_changed)
        f.pack_start(self.pw_confirm, False, False, 0)

        self.strength_bar = _StrengthBar()
        f.pack_start(self.strength_bar, False, False, 2)

        return f

    def _show_warning(self):
        self.warning_box.show_all()
        self.form.hide()
        self.setup_btn.show()
        self.next_btn.set_sensitive(False)
        self.next_btn.set_label("")

    def _show_form(self):
        self.warning_box.hide()
        self.form.show_all()
        self.setup_btn.hide()
        self.next_btn.set_label("Próximo")
        self._validate()

    def _on_pw_changed(self, entry):
        self.strength_bar.set_strength(_password_strength(self.pw_entry.get_text()))
        GLib.idle_add(self._validate)

    def _validate(self):
        pw1 = self.pw_entry.get_text()
        pw2 = self.pw_confirm.get_text()
        ok = True
        msg = ""
        if len(pw1) < 6:
            msg = "A senha precisa ter pelo menos 6 caracteres."
            ok = False
        elif pw1 != pw2:
            msg = "As senhas não conferem."
            ok = False
        elif _password_strength(pw1) < 2:
            msg = "A senha é muito fraca. Use letras e números."
            ok = False
        self.error_label.set_text(msg)
        self._valid = ok
        self.next_btn.set_sensitive(ok)
        return False

    def _on_next(self):
        if self._valid:
            win = self.get_toplevel()
            win._oobe_root_password = self.pw_entry.get_text()
            win._oobe_goto("user")


class _UserPage(Gtk.Box):
    """Etapa 2 — criação do usuário comum (com sudo)."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        step = _center_label("2 / 2 — Criar sua conta", "step-label")
        self.pack_start(step, False, False, 24)

        title = _center_label("Crie sua conta de usuário", "title")
        self.pack_start(title, False, False, 8)

        sub = _center_label(
            "Com esta conta você poderá usar o sistema no dia a dia.", "subtitle")
        self.pack_start(sub, False, False, 32)

        f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pack_start(f, False, False, 8)

        lbl_n = Gtk.Label(label="Nome de usuário:")
        lbl_n.get_style_context().add_class("field-title")
        lbl_n.set_halign(Gtk.Align.START)
        f.pack_start(lbl_n, False, False, 0)
        self.name_entry = _make_entry("seu.nome")
        self.name_entry.connect("changed", lambda e: self._validate())
        f.pack_start(self.name_entry, False, False, 0)

        info = Gtk.Label(
            label="Use letras minúsculas, números, ponto ou traço. Exemplo: joao.silva")
        info.get_style_context().add_class("info")
        info.set_halign(Gtk.Align.START)
        f.pack_start(info, False, False, 2)

        lbl_p = Gtk.Label(label="Senha:")
        lbl_p.get_style_context().add_class("field-title")
        lbl_p.set_halign(Gtk.Align.START)
        f.pack_start(lbl_p, False, False, 4)
        self.pw_entry = _make_password_entry("Crie uma senha")
        self.pw_entry.connect("changed", self._on_pw_changed)
        f.pack_start(self.pw_entry, False, False, 0)

        lbl_c = Gtk.Label(label="Confirmar senha:")
        lbl_c.get_style_context().add_class("field-title")
        lbl_c.set_halign(Gtk.Align.START)
        f.pack_start(lbl_c, False, False, 2)
        self.pw_confirm = _make_password_entry("Confirme a senha")
        self.pw_confirm.connect("changed", self._on_pw_changed)
        f.pack_start(self.pw_confirm, False, False, 0)

        self.strength_bar = _StrengthBar()
        f.pack_start(self.strength_bar, False, False, 2)

        # erro fora do form
        self.error_label = _center_label("", "error-msg")
        self.pack_start(self.error_label, False, False, 2)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.back_btn = Gtk.Button(label="Voltar")
        self.back_btn.get_style_context().add_class("btn-secondary")
        self.back_btn.connect("clicked", lambda b: self.get_toplevel()._oobe_goto("root"))
        btn_box.pack_start(self.back_btn, False, False, 0)

        self.create_btn = Gtk.Button(label="Criar conta e entrar")
        self.create_btn.get_style_context().add_class("btn-primary")
        self.create_btn.set_sensitive(False)
        self.create_btn.connect("clicked", lambda b: self._on_create())
        btn_box.pack_start(self.create_btn, False, False, 0)

        self.pack_start(btn_box, False, False, 24)

    def _on_pw_changed(self, entry):
        self.strength_bar.set_strength(_password_strength(self.pw_entry.get_text()))
        GLib.idle_add(self._validate)

    def _validate(self):
        name = self.name_entry.get_text().strip()
        pw1 = self.pw_entry.get_text()
        pw2 = self.pw_confirm.get_text()
        ok = True
        msg = ""
        if not re.match(r"^[a-z][a-z0-9._-]{1,31}$", name):
            msg = "Nome inválido. Use letras minúsculas, números, ponto ou traço."
            ok = False
        elif len(pw1) < 6:
            msg = "A senha precisa ter pelo menos 6 caracteres."
            ok = False
        elif pw1 != pw2:
            msg = "As senhas não conferem."
            ok = False
        elif _password_strength(pw1) < 2:
            msg = "A senha é muito fraca. Use letras e números."
            ok = False
        self.error_label.set_text(msg)
        self.create_btn.set_sensitive(ok)
        return False

    def _on_create(self):
        win = self.get_toplevel()
        win._oobe_user_name = self.name_entry.get_text().strip()
        win._oobe_user_password = self.pw_entry.get_text()
        win._oobe_goto("progress")


class _ProgressPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        self.msg = _center_label("Criando sua conta…", "progress-msg")
        self.pack_start(self.msg, False, False, 0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.pack_start(self.spinner, False, False, 0)

    def start(self):
        self.spinner.start()

    def set_status(self, text, error=False):
        self.msg.set_text(text)
        if error:
            self.msg.get_style_context().add_class("error-msg")
            self.spinner.stop()
            self.spinner.hide()


class OobeWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("Tarsila — Primeiro acesso")
        self.set_default_size(800, 580)
        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self._fullscreened = False
        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self._on_realize)

        self._oobe_root_state = _read_root_state()
        self._oobe_root_password = ""
        self._oobe_user_name = ""
        self._oobe_user_password = ""

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(250)
        vbox.pack_start(self.stack, True, True, 0)

        self.root_page = _RootPage(self._oobe_root_state)
        self.user_page = _UserPage()
        self.progress_page = _ProgressPage()

        for name, page in (("root", self.root_page),
                           ("user", self.user_page),
                           ("progress", self.progress_page)):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.set_valign(Gtk.Align.CENTER)
            box.set_halign(Gtk.Align.CENTER)
            box.set_margin_start(20)
            box.set_margin_end(20)
            box.pack_start(page, False, False, 0)
            self.stack.add_named(box, name)

        self.show_all()
        if self._oobe_root_state in ("none", "locked", "weak"):
            self.stack.set_visible_child_name("root")
        else:
            self.stack.set_visible_child_name("user")

    def _on_realize(self, widget):
        try:
            self.fullscreen()
        except Exception:
            pass

    def _oobe_goto(self, name):
        if name == "progress":
            self.progress_page.start()
        self.stack.set_visible_child_name(name)
        if name == "progress":
            GLib.idle_add(self._run_provision)

    def _run_provision(self):
        self.progress_page.set_status("Criando sua conta…")
        try:
            result = subprocess.run(
                ["sudo", "/usr/local/sbin/tarsila-user-provision",
                 self._oobe_user_name, self._oobe_root_password],
                input=self._oobe_user_password,
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            result = None

        if result is None:
            self.progress_page.set_status(
                "O processo demorou demais.\n\n"
                "Reinicie o sistema e tente novamente.", error=True)
            return

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "Erro desconhecido.").strip()
            self.progress_page.set_status(
                "Não foi possível criar a conta.\n\n" + err[:200], error=True)
            return

        self.progress_page.set_status("Conta criada! Iniciando…")
        # o provision reinicia o lightdm → a sessão (e esta janela) termina


def main():
    _apply_css()
    OobeWindow()
    Gtk.main()


if __name__ == "__main__":
    main()