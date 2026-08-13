#!/usr/bin/env python3
"""Instalador de pacotes .deb avulsos — abre ao dar duplo clique num .deb.

Fluxo: confirma o pacote -> pede a senha de administrador -> instala
mostrando progresso -> avisa sucesso/erro -> oferece rodar o app agora.

Por baixo, roda como root só o necessário (via "sudo -S", com a senha
digitada aqui) para chamar tarsila-deb-instalar, que instala o pacote e
cria o atalho curado com o mesmo mecanismo da Tarsila Store
(tarsila-atalho-criar): .desktop em /usr/share/tarsila/games (jogos) ou
/usr/share/tarsila/applications (demais apps), ícone em
/usr/share/tarsila/icons/.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import subprocess
import sys
import threading
from pathlib import Path

INSTALLER = "/opt/tarsila-store/bin/tarsila-deb-instalar"


def dpkg_info(caminho, campo, default="—"):
    try:
        r = subprocess.run(["dpkg-deb", "-f", caminho, campo],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or default
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return default


class InstaladorDeb:
    def __init__(self, caminho):
        self.caminho = caminho
        self.pkg = dpkg_info(caminho, "Package", Path(caminho).stem)
        self.versao = dpkg_info(caminho, "Version", "")

    def confirmar(self):
        dlg = Gtk.MessageDialog(
            modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Deseja instalar o arquivo \"{Path(self.caminho).name}\"?")
        detalhe = f"Pacote: {self.pkg}"
        if self.versao != "—":
            detalhe += f"  ·  Versão: {self.versao}"
        dlg.format_secondary_text(detalhe)
        dlg.add_buttons("Não", Gtk.ResponseType.NO, "Sim", Gtk.ResponseType.YES)
        dlg.set_default_response(Gtk.ResponseType.YES)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def pedir_senha(self):
        dlg = Gtk.Dialog(title="Autorização necessária", modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        "Confirmar", Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(10)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.pack_start(Gtk.Label(
            label="Instalar aplicativos exige a senha de administrador."),
            False, False, 0)
        entry = Gtk.Entry()
        entry.set_visibility(False)
        entry.set_placeholder_text("Senha")
        entry.set_activates_default(True)
        content.pack_start(entry, False, False, 0)
        aviso = Gtk.Label(label="")
        content.pack_start(aviso, False, False, 0)
        content.show_all()

        while True:
            entry.grab_focus()
            resp = dlg.run()
            if resp != Gtk.ResponseType.OK:
                dlg.destroy()
                return None
            senha = entry.get_text()
            if not senha:
                aviso.set_markup("<span foreground='red'>Digite a senha.</span>")
                continue
            if self._senha_valida(senha):
                dlg.destroy()
                return senha
            aviso.set_markup(
                "<span foreground='red'>Senha incorreta. Tente de novo.</span>")
            entry.set_text("")

    @staticmethod
    def _senha_valida(senha):
        try:
            r = subprocess.run(["sudo", "-S", "-k", "-p", "", "true"],
                               input=senha + "\n", capture_output=True,
                               text=True, timeout=10)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def instalar_com_progresso(self, senha):
        janela = Gtk.Window(title="Instalando")
        janela.set_default_size(420, 150)
        janela.set_position(Gtk.WindowPosition.CENTER)
        janela.set_deletable(False)
        janela.set_resizable(False)
        janela.connect("destroy", lambda *_: Gtk.main_quit())
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        janela.add(box)

        titulo = Gtk.Label(xalign=0)
        titulo.set_markup(f"<b>Instalando {self.pkg}…</b>")
        box.pack_start(titulo, False, False, 0)

        spinner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        spinner = Gtk.Spinner()
        spinner.start()
        spinner_box.pack_start(spinner, False, False, 0)
        status_lbl = Gtk.Label(label="Preparando…", xalign=0)
        spinner_box.pack_start(status_lbl, True, True, 0)
        box.pack_start(spinner_box, False, False, 0)

        barra = Gtk.ProgressBar()
        barra.set_show_text(True)
        box.pack_start(barra, False, False, 0)

        janela.show_all()

        resultado = {"ok": False, "saida": ""}

        def atualizar(pct, desc):
            if pct is not None:
                barra.set_fraction(max(0.0, min(1.0, pct / 100)))
                barra.set_text(f"{pct:.0f}%")
            else:
                barra.pulse()
            if desc:
                status_lbl.set_text(desc)
            return False

        def worker():
            saida = []
            try:
                proc = subprocess.Popen(
                    ["sudo", "-S", "-k", "-p", "", INSTALLER, self.caminho],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1)
                proc.stdin.write(senha + "\n")
                proc.stdin.flush()
                proc.stdin.close()
                for linha in proc.stdout:
                    saida.append(linha)
                    if linha.startswith("pmstatus:"):
                        partes = linha.strip().split(":", 3)
                        pct = None
                        if len(partes) >= 3:
                            try:
                                pct = float(partes[2])
                            except ValueError:
                                pct = None
                        desc = partes[3] if len(partes) > 3 else ""
                        GLib.idle_add(atualizar, pct, desc)
                proc.wait()
                resultado["ok"] = proc.returncode == 0
            except Exception as exc:
                saida.append(str(exc))
            resultado["saida"] = "".join(saida)[-800:]
            GLib.idle_add(janela.destroy)

        threading.Thread(target=worker, daemon=True).start()
        Gtk.main()
        return resultado

    def avisar_resultado(self, resultado):
        if resultado["ok"]:
            dlg = Gtk.MessageDialog(
                modal=True, message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK, text="Instalado com sucesso")
            dlg.format_secondary_text(
                "Seu aplicativo foi instalado com sucesso.")
        else:
            dlg = Gtk.MessageDialog(
                modal=True, message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK, text="Não foi possível instalar")
            dlg.format_secondary_text(
                resultado["saida"].strip() or "Erro desconhecido.")
        dlg.run()
        dlg.destroy()

    def perguntar_se_roda_agora(self):
        dlg = Gtk.MessageDialog(
            modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Deseja rodar o aplicativo agora?")
        dlg.add_buttons("Não", Gtk.ResponseType.NO, "Sim", Gtk.ResponseType.YES)
        dlg.set_default_response(Gtk.ResponseType.YES)
        resp = dlg.run()
        dlg.destroy()
        return resp == Gtk.ResponseType.YES

    def rodar_agora(self):
        if subprocess.run(["gtk-launch", self.pkg],
                          capture_output=True).returncode == 0:
            return
        for base in (Path("/usr/share/tarsila/applications"),
                    Path("/usr/share/tarsila/games")):
            desktop = base / f"{self.pkg}.desktop"
            if desktop.exists():
                subprocess.Popen(["gtk-launch", desktop.stem])
                return


def main():
    if len(sys.argv) < 2:
        print("uso: tarsila-deb-gui.py <arquivo.deb>", file=sys.stderr)
        sys.exit(1)
    caminho = str(Path(sys.argv[1]).resolve())
    app = InstaladorDeb(caminho)

    if not app.confirmar():
        return
    senha = app.pedir_senha()
    if senha is None:
        return
    resultado = app.instalar_com_progresso(senha)
    app.avisar_resultado(resultado)
    if resultado["ok"] and app.perguntar_se_roda_agora():
        app.rodar_agora()


if __name__ == "__main__":
    main()
