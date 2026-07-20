#!/usr/bin/env python3
"""Botao de energia da tela de login (Tarsila).

Icone de poweroff BRANCO sobre fundo preto (mesma cor do fundo do
greeter -> parece flutuar, sem "caixa"), no canto superior direito.
Ao clicar, pergunta no centro da tela: Desligar / Reiniciar / Voltar.

Iniciado pelo tarsila-greeter-power.sh (greeter-setup-script do
lightdm); encerrado no login pelo tarsila-greeter-power-stop.sh.
"""
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

GLib.set_prgname("tarsila-greeter-power")

CSS = b"""
window, .fundo { background-color: #000000; }
button {
  background-image: none;
  background-color: #000000;
  color: #ffffff;
  border: none;
  box-shadow: none;
  padding: 4px;
}
button:hover { color: #ff5544; }
dialog, dialog .fundo { background-color: @theme_bg_color; }
"""


def aplicar_css():
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def perguntar(parent):
    dlg = Gtk.Dialog(title="Energia", transient_for=parent, modal=True)
    dlg.set_decorated(False)
    caixa = dlg.get_content_area()
    caixa.set_spacing(12)
    caixa.set_margin_top(18)
    caixa.set_margin_bottom(10)
    caixa.set_margin_start(24)
    caixa.set_margin_end(24)
    rotulo = Gtk.Label()
    rotulo.set_markup("<b>O que você deseja fazer?</b>")
    caixa.pack_start(rotulo, False, False, 0)
    dlg.add_buttons("Desligar", 10, "Reiniciar", 11, "Voltar", 1)
    dlg.show_all()
    # sem window manager: posiciona na mao, logo ABAIXO do icone no
    # canto superior direito (estilo menu suspenso), nao no centro
    tela = Gdk.Screen.get_default()
    w, _h = dlg.get_size()
    dlg.get_window().move(tela.get_width() - w - 8, 36)

    # Fecha sozinho ao clicar FORA da caixa, como um menu de verdade:
    # grab do ponteiro (owner_events=True -> cliques nos botoes seguem
    # normais; cliques fora chegam aqui com coordenadas de tela).
    dlg.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

    def clique_fora(_d, ev):
        wx, wy = dlg.get_window().get_position()
        dw, dh = dlg.get_size()
        fora = not (wx <= ev.x_root <= wx + dw and wy <= ev.y_root <= wy + dh)
        if fora:
            dlg.response(Gtk.ResponseType.DELETE_EVENT)
            return True
        return False

    dlg.connect("button-press-event", clique_fora)
    seat = Gdk.Display.get_default().get_default_seat()
    seat.grab(dlg.get_window(), Gdk.SeatCapabilities.ALL_POINTING,
              True, None, None, None, None)
    resp = dlg.run()
    seat.ungrab()
    dlg.destroy()
    return resp


def ao_clicar(botao, win):
    resp = perguntar(win)
    if resp == 10:
        subprocess.Popen(["systemctl", "poweroff"])
    elif resp == 11:
        subprocess.Popen(["systemctl", "reboot"])
    # Voltar/Esc: nada - o icone continua la


def main():
    aplicar_css()
    # discreto, do tamanho dos icones do top bar do sistema (o greeter
    # nao tem top bar; este icone finge ser um item dela no canto)
    win = Gtk.Window(title="tarsila-greeter-power")
    win.set_decorated(False)
    win.set_skip_taskbar_hint(True)
    win.set_keep_above(True)
    win.set_default_size(26, 26)

    botao = Gtk.Button()
    img = Gtk.Image.new_from_icon_name("system-shutdown-symbolic",
                                       Gtk.IconSize.MENU)
    img.set_pixel_size(18)
    botao.set_image(img)
    botao.set_relief(Gtk.ReliefStyle.NONE)
    botao.set_tooltip_text("Desligar ou reiniciar")
    botao.connect("clicked", ao_clicar, win)
    win.add(botao)

    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    tela = Gdk.Screen.get_default()
    win.get_window().move(tela.get_width() - 38, 3)
    Gtk.main()


if __name__ == "__main__":
    main()
