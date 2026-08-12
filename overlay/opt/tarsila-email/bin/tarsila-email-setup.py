#!/usr/bin/env python3
"""Assistente Tarsila Email — configuração Gmail (multi-conta).

Primeira tela (UX): marca Gmail + “Faça login” + “Gerenciar sua senha”.
Depois: e-mail + senha de aplicativo (Google já aberto no navegador).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from lib import config  # noqa: E402

MOTOR = RAIZ / "bin" / "configurar-claws"
APP = RAIZ / "bin" / "tarsila-email-gtk.py"
GMAIL_ICON = RAIZ / "ui" / "icons" / "gmail.png"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GMAIL_URL = "https://myaccount.google.com/apppasswords"
FROM_APP = os.environ.get("TARSILA_EMAIL_FROM_APP") == "1"
ICON_PX = 64
CSS_APP = RAIZ / "ui" / "css" / "gmail-gtk.css"

TEXTO_ENTENDER = """\
Entenda como configurar o seu Tarsila Email

O Tarsila Email lê o Gmail neste aparelho sem navegador. Para isso o Google
pede uma “senha de aplicativo” — uma senha só para o Tarsila, diferente da
senha com que você entra no Gmail no dia a dia.

O que você vai precisar
• Uma conta Gmail (@gmail.com ou Google Workspace).
• Verificação em duas etapas ligada nessa conta (o Google exige isso
  para criar senha de app).
• Acesso à internet neste aparelho.

Passo a passo

1. Nesta tela, toque em “Gerenciar sua senha”.
2. O navegador abre a página de senhas de app da sua Conta Google.
   Se pedir login ou confirmação, use a conta que deseja no Tarsila.
3. Se o Google avisar que a verificação em duas etapas não está ativa,
   ative-a e volte à página de senhas de app.
4. Em “Selecionar app”, escolha E-mail (ou Outro) e dê um nome, por
   exemplo “Tarsila”. Toque em Criar / Gerar.
5. O Google mostra uma senha de 16 letras (às vezes com espaços).
   Copie essa senha — você não verá de novo com facilidade.
6. Volte ao Tarsila Email. Na próxima tela, digite:
   • seu endereço de e-mail completo;
   • a senha de 16 caracteres (os espaços podem ficar).
7. Toque em “Entrar”. O Tarsila testa a conexão com o Google. Se estiver
   tudo certo, a conta fica salva só neste aparelho e a caixa de entrada
   abre.

Se der erro ao entrar
• Confira se colou a senha de app, e não a senha normal do Gmail.
• Confira se a verificação em duas etapas continua ativa.
• Use “Abrir de novo a página do Google” e gere outra senha de app.
• Confira a internet do aparelho.

Privacidade em uma frase
A senha de app fica guardada neste aparelho. Ao usar “Sair” no Tarsila Email,
apagamos a conta e os e-mails baixados daqui.

Pronto: com a senha de app, o Tarsila Email passa a sincronizar seu Gmail
como um aplicativo de e-mail comum.
"""

TEXTO_TERMOS = """\
Termos de uso — Tarsila Email

O Tarsila Email é um leitor de Gmail feito para o sistema Tarsila.
Ele se conecta ao Google pelos protocolos IMAP e SMTP, usando a
senha de aplicativo que você criar na sua Conta Google.

• Seus e-mails ficam sincronizados neste aparelho (armazenamento local).
• A senha de app é guardada de forma ofuscada só nesta conta de usuário.
• Não enviamos sua senha a servidores Tarsila; a conversa é com o Google.
• Ao tocar em “Sair” no aplicativo, apagamos contas e dados locais.
• O uso do Gmail continua sujeito aos Termos e Políticas do Google.

Ao continuar, você confirma que entendeu esses pontos e que a conta
Google usada é sua (ou que você tem autorização para usá-la).
"""


def motor(*args, senha=None, email=None):
    amb = dict(os.environ)
    if senha:
        amb["CLAWS_SENHA"] = senha
    if email:
        amb["CLAWS_EMAIL"] = email
    p = subprocess.run(
        [str(MOTOR), *args], env=amb, capture_output=True, text=True, timeout=90
    )
    return p.returncode, (p.stderr or p.stdout or "").strip()


def _gmail_image(px: int = ICON_PX) -> Gtk.Widget:
    """Ícone Gmail oficial (PNG), centralizado."""
    from gi.repository import GdkPixbuf

    wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    wrap.set_halign(Gtk.Align.CENTER)
    wrap.set_valign(Gtk.Align.CENTER)
    img = Gtk.Image()
    path = GMAIL_ICON if GMAIL_ICON.is_file() else None
    if path is None:
        img.set_from_icon_name("internet-mail", Gtk.IconSize.DIALOG)
    else:
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), px, px, True)
            img.set_from_pixbuf(pb)
        except Exception:
            img.set_from_file(str(path))
    wrap.pack_start(img, False, False, 0)
    return wrap


class Setup(Gtk.Window):
    def __init__(self, prefill_email=""):
        super().__init__(title="Tarsila Email")
        self.set_resizable(False)
        self.set_default_size(360, 420)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name("internet-mail")
        self.get_style_context().add_class("tarsila-setup-window")
        self._prefill = prefill_email or ""

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(180)
        self.add(self.stack)

        self.stack.add_named(self._build_welcome(), "welcome")
        self.stack.add_named(self._build_credentials(), "credentials")
        self.stack.set_visible_child_name("welcome")
        self.show_all()

    # --- páginas ---------------------------------------------------------

    def _build_welcome(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_border_width(22)

        page.pack_start(_gmail_image(ICON_PX), False, False, 0)

        spacer = Gtk.Box()
        spacer.set_size_request(-1, 12)
        page.pack_start(spacer, False, False, 0)

        title = Gtk.Label(label="Faça login")
        title.set_halign(Gtk.Align.CENTER)
        title.get_style_context().add_class("tarsila-setup-title")
        page.pack_start(title, False, False, 0)

        sub = Gtk.Label(label="Use sua conta do Google")
        sub.set_halign(Gtk.Align.CENTER)
        sub.set_margin_top(6)
        sub.set_margin_bottom(20)
        sub.get_style_context().add_class("dim-label")
        page.pack_start(sub, False, False, 0)

        btn = Gtk.Button()
        btn.set_size_request(-1, 42)
        btn.get_style_context().add_class("suggested-action")
        btn.get_style_context().add_class("tarsila-setup-btn")
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        inner.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic", Gtk.IconSize.BUTTON)
        inner.pack_start(icon, False, False, 0)
        lab = Gtk.Label(label="Gerenciar sua senha")
        lab.set_markup("<b>Gerenciar sua senha</b>")
        inner.pack_start(lab, False, False, 0)
        btn.add(inner)
        btn.connect("clicked", self._on_gerenciar_senha)
        page.pack_start(btn, False, False, 0)

        links = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        links.set_margin_top(18)
        links.set_halign(Gtk.Align.CENTER)

        l1 = Gtk.LinkButton(uri="", label="Entenda como configurar o seu Tarsila Email")
        l1.set_halign(Gtk.Align.CENTER)
        l1.get_style_context().add_class("tarsila-setup-link")
        l1.connect("activate-link", lambda *_: True)
        l1.connect("clicked", lambda *_: self._dialogo_texto(
            "Como configurar", TEXTO_ENTENDER))
        links.pack_start(l1, False, False, 0)

        l2 = Gtk.LinkButton(uri="", label="Termos de uso")
        l2.set_halign(Gtk.Align.CENTER)
        l2.get_style_context().add_class("tarsila-setup-link")
        l2.connect("activate-link", lambda *_: True)
        l2.connect("clicked", lambda *_: self._dialogo_texto(
            "Termos de uso", TEXTO_TERMOS))
        links.pack_start(l2, False, False, 0)

        page.pack_start(links, False, False, 0)
        return page

    def _build_credentials(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(22)

        back = Gtk.Button()
        back.set_relief(Gtk.ReliefStyle.NONE)
        back.set_halign(Gtk.Align.START)
        back_box = Gtk.Box(spacing=4)
        back_box.pack_start(
            Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON),
            False, False, 0,
        )
        back_box.pack_start(Gtk.Label(label="Voltar"), False, False, 0)
        back.add(back_box)
        back.connect("clicked", lambda *_: self.stack.set_visible_child_name("welcome"))
        page.pack_start(back, False, False, 0)

        tit = Gtk.Label(label="Senha de aplicativo")
        tit.set_halign(Gtk.Align.START)
        tit.get_style_context().add_class("tarsila-setup-title")
        page.pack_start(tit, False, False, 0)

        info = Gtk.Label(
            label="Cole aqui o e-mail do Gmail e a senha de 16 caracteres "
                  "gerada no Google."
        )
        info.set_line_wrap(True)
        info.set_xalign(0)
        info.set_max_width_chars(36)
        page.pack_start(info, False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=10)
        grid.set_margin_top(8)

        grid.attach(Gtk.Label(label="E-mail", xalign=0), 0, 0, 1, 1)
        self.email = Gtk.Entry()
        self.email.set_placeholder_text("voce@gmail.com")
        self.email.set_hexpand(True)
        if self._prefill:
            self.email.set_text(self._prefill)
        grid.attach(self.email, 0, 1, 1, 1)

        grid.attach(Gtk.Label(label="Senha de app", xalign=0), 0, 2, 1, 1)
        self.senha = Gtk.Entry()
        self.senha.set_visibility(False)
        self.senha.set_placeholder_text("xxxx xxxx xxxx xxxx")
        self.senha.set_hexpand(True)
        grid.attach(self.senha, 0, 3, 1, 1)
        page.pack_start(grid, False, False, 0)

        self.aviso = Gtk.Label()
        self.aviso.set_line_wrap(True)
        self.aviso.set_xalign(0)
        page.pack_start(self.aviso, False, False, 0)

        btn_save = Gtk.Button(label="Entrar")
        btn_save.set_size_request(-1, 40)
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self.salvar)
        page.pack_start(btn_save, False, False, 0)

        reopen = Gtk.LinkButton(uri="", label="Abrir de novo a página do Google")
        reopen.set_halign(Gtk.Align.CENTER)
        reopen.connect("activate-link", lambda *_: True)
        reopen.connect("clicked", lambda *_: self._abrir_google(silencioso=True))
        page.pack_start(reopen, False, False, 0)
        return page

    # --- ações -----------------------------------------------------------

    def _dialogo_texto(self, titulo: str, texto: str):
        dlg = Gtk.Dialog(
            title=titulo, transient_for=self, modal=True,
            flags=0,
        )
        dlg.add_button("Fechar", Gtk.ResponseType.CLOSE)
        dlg.set_default_size(380, 340)
        box = dlg.get_content_area()
        box.set_border_width(14)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(250)
        lab = Gtk.Label(label=texto)
        lab.set_line_wrap(True)
        lab.set_xalign(0)
        lab.set_yalign(0)
        lab.set_selectable(True)
        lab.set_max_width_chars(46)
        lab.get_style_context().add_class("tarsila-setup-help")
        scroll.add(lab)
        box.pack_start(scroll, True, True, 0)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def _abrir_google(self, silencioso=False):
        if not silencioso:
            dlg = Gtk.MessageDialog(
                transient_for=self, modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text="Verificação em duas etapas",
            )
            dlg.format_secondary_text(
                "No Google, a verificação em duas etapas precisa estar "
                "ativa para criar uma senha de aplicativo.\n\n"
                "Abrir a página do Google agora?"
            )
            if dlg.run() != Gtk.ResponseType.OK:
                dlg.destroy()
                return False
            dlg.destroy()
        if MOTOR.is_file():
            subprocess.Popen(
                [str(MOTOR), "--abrir", GMAIL_URL],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", GMAIL_URL],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        return True

    def _on_gerenciar_senha(self, _):
        if not self._abrir_google(silencioso=False):
            return
        self.stack.set_visible_child_name("credentials")
        self.senha.grab_focus()

    def erro(self, t: str):
        self.aviso.set_markup(
            f'<span foreground="#c01c28">{GLib.markup_escape_text(t)}</span>'
        )

    def salvar(self, _=None):
        e = self.email.get_text().strip()
        s = self.senha.get_text()
        if not EMAIL_RE.match(e):
            self.erro("E-mail inválido")
            return
        if not s:
            self.erro("Digite a senha de aplicativo")
            return
        self.aviso.set_text("Testando conexão…")
        self.set_sensitive(False)

        def work():
            rc, _ = motor("--testar-imap", "imap.gmail.com", "993", senha=s, email=e)
            GLib.idle_add(self.fim, rc, e, s)

        threading.Thread(target=work, daemon=True).start()

    def fim(self, rc, e, s):
        self.set_sensitive(True)
        if rc != 0:
            self.erro("Não conectou. Confira a senha de aplicativo e a verificação em duas etapas.")
            return False
        config.save_account(e, s)
        if not FROM_APP:
            subprocess.Popen(
                [sys.executable, str(APP)],
                env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        Gtk.main_quit()
        return False


def _apply_css():
    """Roboto em todo o setup + tipografia/links mais compactos."""
    providers = []
    if CSS_APP.is_file():
        p = Gtk.CssProvider()
        p.load_from_path(str(CSS_APP))
        providers.append(p)
    # Título 22px; corpo/subtítulo/botão/links em escala (~14 / 14 / 14 / 12).
    extra = Gtk.CssProvider()
    extra.load_from_data(b"""
    * {
      font-family: Roboto, "Noto Sans", sans-serif;
    }
    .tarsila-setup-window {
      font-family: Roboto, "Noto Sans", sans-serif;
      font-size: 14px;
    }
    .tarsila-setup-title {
      font-family: Roboto, "Noto Sans", sans-serif;
      font-size: 22px;
      font-weight: bold;
    }
    .tarsila-setup-btn,
    .tarsila-setup-btn label {
      font-family: Roboto, "Noto Sans", sans-serif;
      font-size: 14px;
    }
    .tarsila-setup-link,
    .tarsila-setup-link label,
    linkbutton.tarsila-setup-link,
    linkbutton.tarsila-setup-link label {
      font-family: Roboto, "Noto Sans", sans-serif;
      font-size: 12px;
    }
    .tarsila-setup-help {
      font-family: Roboto, "Noto Sans", sans-serif;
      font-size: 13px;
    }
    .dim-label {
      color: #5f6368;
      font-size: 14px;
    }
    """)
    providers.append(extra)
    screen = Gdk.Screen.get_default()
    for p in providers:
        Gtk.StyleContext.add_provider_for_screen(
            screen, p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


if __name__ == "__main__":
    try:
        _apply_css()
    except Exception:
        pass

    prefill = sys.argv[1] if len(sys.argv) > 1 else ""
    w = Setup(prefill)
    w.connect("destroy", Gtk.main_quit)
    Gtk.main()
