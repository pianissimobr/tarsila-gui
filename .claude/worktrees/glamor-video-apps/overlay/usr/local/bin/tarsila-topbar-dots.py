#!/usr/bin/env python3
# Substitui os 3 plugins genmon (tarsila-dot1/2/3.sh) por um unico processo.
# Orientado a evento via Wnck (sem polling): reage direto a maximizar/
# desmaximizar/fechar/trocar janela ativa. Mantem o mesmo estado por
# arquivo (tarsila-state) so para preservar compatibilidade com os
# scripts tarsila-goto1/2/3.sh existentes, que continuam sendo os
# unicos donos da logica "o que cada bolinha faz".
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Wnck", "3.0")
from gi.repository import Gtk, GLib, Gdk, Wnck
import os
import signal
import subprocess

DOTS = "/usr/local/share/tarsila"
RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STATE_FILE = os.path.join(RUNTIME, "tarsila-state")
WINCOUNT_CACHE = os.path.join(RUNTIME, "tarsila-wincount")

ICON_SIZE = 20


def read_state():
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return f.read().strip()
        except OSError:
            pass
    return ""


def app_window_count(screen):
    return sum(
        1
        for w in screen.get_windows()
        if w.get_window_type() == Wnck.WindowType.NORMAL
        and not w.is_skip_tasklist()
    )


class Dot:
    def __init__(self, goto_script):
        self.goto_script = goto_script
        self.image = Gtk.Image()
        self.event_box = Gtk.EventBox()
        self.event_box.add(self.image)
        self.event_box.connect("button-press-event", self.on_click)
        self.event_box.set_visible_window(False)

    def on_click(self, *_args):
        subprocess.Popen([self.goto_script])

    def set_on(self, on):
        path = os.path.join(DOTS, "dot-on.svg" if on else "dot-off.svg")
        self.image.set_from_file(path)
        self.image.set_pixel_size(ICON_SIZE)


class TopbarDots(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.stick()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_border_width(4)
        self.add(box)

        self.dot1 = Dot("/usr/local/bin/tarsila-goto1.sh")
        self.dot2 = Dot("/usr/local/bin/tarsila-goto2.sh")
        self.dot3 = Dot("/usr/local/bin/tarsila-goto3.sh")
        for d in (self.dot1, self.dot2, self.dot3):
            box.pack_start(d.event_box, False, False, 0)

        self.connect("realize", self.on_realize)

        self.screen = Wnck.Screen.get_default()
        self.screen.connect("active-window-changed", self.on_wnck_event)
        self.screen.connect("window-opened", self.on_wnck_event)
        self.screen.connect("window-closed", self.on_wnck_event)
        self._tracked_windows = set()
        self.screen.force_update()
        self._hook_existing_windows()

        self.refresh()
        # rede de seguranca bem espacada (60s) so pra corrigir qualquer
        # drift eventual; o normal e o refresh disparar via sinal do wnck.
        GLib.timeout_add_seconds(60, self.refresh)

    def _hook_existing_windows(self):
        for w in self.screen.get_windows():
            self._hook_window(w)

    def _hook_window(self, w):
        if w in self._tracked_windows:
            return
        self._tracked_windows.add(w)
        w.connect("state-changed", self.on_wnck_event)

    def on_wnck_event(self, *_args):
        # janelas novas tambem precisam ser "hookadas" pro state-changed
        for w in self.screen.get_windows():
            self._hook_window(w)
        self.refresh()

    def on_realize(self, *_args):
        screen = Gdk.Screen.get_default()
        sw = screen.get_width()
        self.move((sw - self.get_allocated_width()) // 2, 0)
        # forca a janela acima de qualquer coisa, inclusive apps
        # maximizados - refeito a cada realize/map por seguranca.
        self.get_window().set_keep_above(True)

    def refresh(self):
        active = self.screen.get_active_window()
        max_v = 1 if (active and active.is_maximized()) else 0
        n = app_window_count(self.screen)
        state = read_state()

        if n == 0:
            self.dot1.set_on(True)
            self.dot2.set_on(False)
            self.dot3.set_on(False)
        elif max_v == 1:
            self.dot1.set_on(False)
            self.dot2.set_on(False)
            self.dot3.set_on(True)
        else:
            dot1_on = state == "1"
            self.dot1.set_on(dot1_on)
            self.dot2.set_on(not dot1_on)
            self.dot3.set_on(False)

        self.resize(1, 1)
        if self.get_window():
            self.get_window().set_keep_above(True)
        return True  # mantem o timer de 60s (rede de seguranca)


def main():
    win = TopbarDots()
    win.show_all()

    def on_sigusr1(_signum, _frame):
        GLib.idle_add(win.refresh)

    signal.signal(signal.SIGUSR1, on_sigusr1)
    Gtk.main()


if __name__ == "__main__":
    main()
