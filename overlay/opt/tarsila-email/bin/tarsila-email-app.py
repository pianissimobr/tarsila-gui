#!/usr/bin/env python3
"""Tarsila Email — shell GTK3 + WebKit2."""
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("TARSILA_EMAIL_PORT", "8475"))
URL = f"http://127.0.0.1:{PORT}/"
BACKEND = RAIZ / "bin" / "tarsila-email-backend.py"
IDLE = RAIZ / "bin" / "tarsila-email-idle.py"
LOG_DIR = Path.home() / ".local" / "share" / "tarsila-email"
WIN_W, WIN_H = 960, 620

_backend = _idle = None
_we_backend = _we_idle = False


def _api_ok():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status", timeout=1.5) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _start(name, script, flag_attr, proc_attr):
    global _backend, _idle
    if _api_ok() and name == "backend":
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"{name}.log", "a", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(
        [sys.executable, "-u", str(script)],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    if name == "backend":
        _backend = proc
        globals()["_we_backend"] = True
        for _ in range(40):
            if _api_ok():
                return
            time.sleep(0.25)
        raise RuntimeError("Backend não respondeu")
    else:
        _idle = proc
        globals()["_we_idle"] = True


def _stop(proc, we_started):
    if not we_started or proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


class EmailWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Tarsila Email", default_width=WIN_W, default_height=WIN_H)
        self.set_icon_name("internet-mail")
        GLib.set_application_name("Tarsila Email")
        Gdk.set_program_class("tarsila-email")

        settings = WebKit2.Settings()
        settings.set_enable_javascript(True)
        settings.set_enable_html5_local_storage(True)
        self.webview = WebKit2.WebView.new_with_settings(settings)
        self.webview.connect("decide-policy", self._on_policy)
        self.add(self.webview)
        self.connect("delete-event", self._on_close)
        self.webview.load_uri(URL)

    def _on_policy(self, _w, decision, dtype):
        if dtype != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return
        uri = decision.get_navigation_action().get_request().get_uri()
        if uri.startswith(f"http://127.0.0.1:{PORT}") or uri.startswith("about:"):
            return
        decision.ignore()

    def _on_close(self, *_):
        _stop(_backend, _we_backend)
        Gtk.main_quit()
        return False


def main():
    if not BACKEND.is_file():
        sys.stderr.write(f"Backend ausente: {BACKEND}\n")
        sys.exit(1)
    _start("backend", BACKEND, "_we_backend", "_backend")
    if IDLE.is_file():
        try:
            log = open(LOG_DIR / "idle.log", "a", encoding="utf-8")  # noqa: SIM115
            global _idle, _we_idle
            _idle = subprocess.Popen(
                [sys.executable, "-u", str(IDLE)],
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            _we_idle = True
        except Exception:
            pass
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    win = EmailWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
