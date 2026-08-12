#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agenda Tarsila - calendario local GTK3 com Google Agenda opcional (stdlib)."""

import base64
import calendar as pycal
import datetime
import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import ssl
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

APP_NAME = "Agenda Tarsila"
APP_ID = "agenda-tarsila"
APP_VERSION = "5.0.0"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
GOOGLE_ICON = os.path.join(APP_DIR, "icons", "google-20.png")
GOOGLE_ICON_FALLBACK = os.path.join(APP_DIR, "icons", "google.png")

# --------------------------------------------------------------------- GTK
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo, GdkPixbuf
except Exception as exc:                                    # pragma: no cover
    sys.stderr.write("\n[ERRO] Modulo GTK3/gi indisponivel: %s\n" % exc)
    sys.stderr.write("Interpretador: %s\n\n" % sys.executable)
    sys.stderr.write("Corrija com:\n")
    sys.stderr.write("  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0\n\n")
    sys.exit(1)

# --------------------------------------------------------------- endpoints
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# ------------------------------------------------------------------ caminhos
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), APP_ID)
DATA_DIR = os.path.join(GLib.get_user_data_dir(), APP_ID)
for _d in (CONFIG_DIR, DATA_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except Exception:
        pass
TOKEN_FILE = os.path.join(CONFIG_DIR, "token.json")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
USER_CREDENTIALS = os.path.join(CONFIG_DIR, "credentials.json")
CACHE_DB = os.path.join(DATA_DIR, "cache.db")
CREDENTIAL_PATHS = [USER_CREDENTIALS,
                    "/etc/agenda-tarsila/credentials.json",
                    "/opt/agenda-tarsila/credentials.json"]

SCHEMA_VERSION = "5"
LOCAL_CAL_ID = "local:default"
LOCAL_CAL_NAME = "Minha agenda"
HORIZON_BACK = 400          # dias sincronizados para tras
HORIZON_FWD = 800           # dias sincronizados para frente
AUTOSYNC_SECONDS = 180

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
MESES_ABR = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sabado", "domingo"]
DIAS_ABR = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
DIAS_MINI = ["S", "T", "Q", "Q", "S", "S", "D"]

EVENT_COLORS_HEX = {"1": "#7986cb", "2": "#33b679", "3": "#8e24aa", "4": "#e67c73",
                    "5": "#f6bf26", "6": "#f4511e", "7": "#039be5", "8": "#616161",
                    "9": "#3f51b5", "10": "#0b8043", "11": "#d50000"}


# =============================================================================
# UTILIDADES
# =============================================================================
def hex_rgb(value, fallback=(0.10, 0.45, 0.91)):
    s = (value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0)
    except Exception:
        return fallback


EVENT_COLORS = dict((k, hex_rgb(v)) for k, v in EVENT_COLORS_HEX.items())
LOCAL_COLOR = hex_rgb("#2a9d8f")


def is_local_cal(cal_id):
    return cal_id == LOCAL_CAL_ID or (cal_id or "").startswith("local:")


def new_local_event_id():
    return "local-" + secrets.token_hex(8)


def event_source_label(ev):
    if getattr(ev, "synced", False):
        return "Local (sincronizado com Google)"
    if getattr(ev, "source", "google") == "local":
        return "Agenda local"
    return "Google Agenda"


def rgb_to_hex(color):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * 255))) for v in color)


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def readable_on(c):
    return (1, 1, 1) if luminance(c) < 0.62 else (0.12, 0.12, 0.12)


def google_g_image(px=20):
    """Icone Google (Flaticon / Magnific) para o botao de login."""
    path = os.path.join(APP_DIR, "icons", "google-%d.png" % px)
    if not os.path.isfile(path):
        path = GOOGLE_ICON if os.path.isfile(GOOGLE_ICON) else GOOGLE_ICON_FALLBACK
    try:
        if os.path.isfile(path):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, px, px, True)
            return Gtk.Image.new_from_pixbuf(pb)
    except Exception:
        pass
    return Gtk.Image.new_from_icon_name("web-browser-symbolic", Gtk.IconSize.BUTTON)


def make_google_login_button(on_clicked):
    """Botao azul: [G] Faça login na sua conta Google."""
    btn = Gtk.Button.new_with_label("Faça login na sua conta Google")
    btn.set_image(google_g_image(20))
    btn.set_always_show_image(True)
    btn.set_image_position(Gtk.PositionType.LEFT)
    btn.get_style_context().add_class("suggested-action")
    btn.get_style_context().add_class("at-google-login")
    btn.set_tooltip_text("Conectar Google Agenda")
    btn.connect("clicked", lambda *_a: on_clicked())
    return btn


def local_iso(value):
    """datetime naive (hora local) -> RFC3339 com offset."""
    if value.tzinfo is None:
        value = value.astimezone()
    return value.isoformat()


def parse_g_time(node):
    """{'date':..} ou {'dateTime':..} -> (date | datetime naive local, all_day)."""
    if not node:
        return None, False
    if node.get("date"):
        try:
            y, m, d = [int(x) for x in node["date"].split("-")]
            return date(y, m, d), True
        except Exception:
            return None, False
    raw = node.get("dateTime")
    if not raw:
        return None, False
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        value = datetime.datetime.fromisoformat(raw)
    except Exception:
        try:
            value = datetime.datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None, False
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value, False


def event_day_span(raw):
    """(d0, d1) em ordinais de data, inclusivos. None se indecifravel."""
    start, all_day = parse_g_time(raw.get("start"))
    end, _ = parse_g_time(raw.get("end"))
    if start is None:
        return None
    if all_day:
        d0 = start
        d1 = d0
        if end is not None and isinstance(end, date) and end > d0:
            d1 = end - timedelta(days=1)          # 'end.date' e exclusivo
    else:
        d0 = start.date()
        d1 = end.date() if isinstance(end, datetime.datetime) else d0
        if (isinstance(end, datetime.datetime)
                and end.time() == datetime.time(0, 0) and d1 > d0):
            d1 -= timedelta(days=1)
    if d1 < d0:
        d1 = d0
    return d0.toordinal(), d1.toordinal()


def fmt_mes_ano(d):
    return "%s de %d" % (MESES[d.month - 1], d.year)


def fmt_dia_longo(d):
    return "%s, %d de %s de %d" % (DIAS[d.weekday()], d.day, MESES[d.month - 1], d.year)


def fmt_relogio(ts):
    if not ts:
        return "nunca"
    delta = time.time() - float(ts)
    if delta < 90:
        return "agora"
    if delta < 3600:
        return "ha %d min" % int(delta / 60)
    if delta < 86400:
        return "ha %d h" % int(delta / 3600)
    return datetime.datetime.fromtimestamp(float(ts)).strftime("%d/%m %H:%M")


def load_settings():
    data = {"view": "week", "week_start": 6, "hidden": [], "hour_height": 46}
    try:
        with open(SETTINGS_FILE, "r") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            data.update(stored)
    except Exception:
        pass
    return data


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


# =============================================================================
# CAMADA HTTP / OAUTH2 (stdlib)
# =============================================================================
class ApiError(Exception):
    def __init__(self, message, status=None, reason=""):
        super().__init__(message)
        self.message = message
        self.status = status
        self.reason = reason


class SyncExpired(Exception):
    """syncToken invalidado pelo Google (HTTP 410)."""


_SSL = ssl.create_default_context()          # usa o CA store do sistema


def _clean_params(params):
    out = {}
    for key, value in (params or {}).items():
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        out[key] = value
    return out


def http_call(method, url, params=None, body=None, headers=None, timeout=40):
    """Requisicao JSON. Levanta ApiError com mensagem legivel."""
    clean = _clean_params(params)
    if clean:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(clean)
    hdrs = {"Accept": "application/json",
            "User-Agent": "AgendaTarsila/" + APP_VERSION}
    if headers:
        hdrs.update(headers)
    data = None
    if isinstance(body, (dict, list)):
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json; charset=UTF-8"
    elif isinstance(body, bytes):
        data = body
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read() or b""
        except Exception:
            pass
        message = "HTTP %s" % exc.code
        reason = ""
        try:
            payload = json.loads(raw.decode("utf-8", "replace"))
            err = payload.get("error")
            if isinstance(err, dict):
                message = err.get("message") or message
                details = err.get("errors") or []
                if details:
                    reason = details[0].get("reason", "")
            elif isinstance(err, str):
                reason = err
                message = payload.get("error_description") or err
        except Exception:
            pass
        raise ApiError(message, exc.code, reason)
    except socket.timeout:
        raise ApiError("Tempo esgotado ao contatar o Google.")
    except urllib.error.URLError as exc:
        raise ApiError("Falha de rede: %s" % exc.reason)
    except ssl.SSLError as exc:
        raise ApiError("Erro TLS: %s" % exc)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return {}


def http_form(url, fields):
    body = urllib.parse.urlencode(fields).encode("utf-8")
    return http_call("POST", url, body=body,
                     headers={"Content-Type": "application/x-www-form-urlencoded"})


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def api_error_text(exc):
    if isinstance(exc, ApiError):
        extra = ""
        if exc.reason in ("accessNotConfigured", "forbidden"):
            extra = "\nAtive a Google Calendar API no projeto do Cloud Console."
        elif exc.reason == "access_denied":
            extra = ("\nAdicione seu e-mail em 'Usuarios de teste' na tela de "
                     "permissao OAuth.")
        elif exc.reason in ("rateLimitExceeded", "userRateLimitExceeded"):
            extra = "\nLimite de requisicoes atingido; tente novamente em instantes."
        elif exc.reason == "invalid_grant":
            extra = "\nA sessao foi revogada. Saia da conta e conecte novamente."
        return exc.message + extra
    return str(exc)


PAGE_OK = ("<!doctype html><html><head><meta charset='utf-8'><title>Agenda Tarsila</title>"
           "<style>body{font-family:Roboto,\"Noto Sans\",sans-serif;text-align:center;padding:60px;color:#202124}"
           "h1{color:#1a73e8}</style></head><body><h1>Tudo pronto!</h1>"
           "<p>Autenticacao concluida. Volte para o <b>Agenda Tarsila</b>.</p>"
           "<p><small>Voce pode fechar esta aba.</small></p></body></html>")

PAGE_FAIL = ("<!doctype html><html><head><meta charset='utf-8'><title>Agenda Tarsila</title>"
             "<style>body{font-family:Roboto,\"Noto Sans\",sans-serif;text-align:center;padding:60px;color:#202124}"
             "h1{color:#d93025}</style></head><body><h1>Autorizacao cancelada</h1>"
             "<p>Nenhum acesso foi concedido. Feche esta aba e tente novamente.</p>"
             "</body></html>")


class _OAuthHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        result = dict((k, v[0]) for k, v in urllib.parse.parse_qs(query).items())
        if "code" in result or "error" in result:
            self.server.oauth_result = result
        page = PAGE_OK if "code" in result else PAGE_FAIL
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def log_message(self, *args):
        pass


class DesktopFlow(object):
    """OAuth 2.0 Installed App + PKCE, redirecionamento por loopback."""

    def __init__(self, client_id, client_secret, scopes):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes

    def run(self, timeout=300, on_url=None):
        verifier = b64url(secrets.token_bytes(64))
        challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        state = secrets.token_urlsafe(24)

        server = HTTPServer(("127.0.0.1", 0), _OAuthHandler)
        server.oauth_result = None
        server.timeout = 1
        redirect_uri = "http://127.0.0.1:%d/" % server.server_port

        params = {"client_id": self.client_id,
                  "redirect_uri": redirect_uri,
                  "response_type": "code",
                  "scope": " ".join(self.scopes),
                  "state": state,
                  "code_challenge": challenge,
                  "code_challenge_method": "S256",
                  "access_type": "offline",
                  "prompt": "consent"}
        url = AUTH_URI + "?" + urllib.parse.urlencode(params)
        if on_url:
            on_url(url)
        try:
            opened = webbrowser.open(url, new=1, autoraise=True)
        except Exception:
            opened = False
        if not opened:
            sys.stderr.write("Abra manualmente no navegador:\n%s\n" % url)

        deadline = time.time() + timeout
        try:
            while server.oauth_result is None and time.time() < deadline:
                server.handle_request()
        finally:
            try:
                server.server_close()
            except Exception:
                pass

        result = server.oauth_result
        if result is None:
            raise ApiError("Tempo esgotado esperando a autorizacao no navegador.")
        if "error" in result:
            raise ApiError("Autorizacao negada pelo Google (%s)." % result["error"],
                           reason=result["error"])
        if result.get("state") != state:
            raise ApiError("Resposta OAuth invalida (state divergente).")

        payload = http_form(TOKEN_URI, {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": result["code"],
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri})
        if not payload.get("refresh_token"):
            raise ApiError("O Google nao devolveu refresh_token. Remova o acesso do app "
                           "em myaccount.google.com/permissions e tente novamente.")
        return payload


# =============================================================================
# DESENHO
# =============================================================================
def text(cr, x, y, value, size=11.0, bold=False, color=(0, 0, 0), width=None,
         height=None, align="left", wrap=False, alpha=1.0):
    layout = PangoCairo.create_layout(cr)
    fd = Pango.FontDescription()
    fd.set_family("Roboto")
    fd.set_absolute_size(size * Pango.SCALE)
    if bold:
        fd.set_weight(Pango.Weight.BOLD)
    layout.set_font_description(fd)
    layout.set_text(value or "", -1)
    if width:
        layout.set_width(int(max(1, width) * Pango.SCALE))
        if wrap:
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        else:
            layout.set_ellipsize(Pango.EllipsizeMode.END)
    if align == "center":
        layout.set_alignment(Pango.Alignment.CENTER)
    elif align == "right":
        layout.set_alignment(Pango.Alignment.RIGHT)
    _tw, th = layout.get_pixel_size()
    ty = y if height is None else y + (height - th) / 2.0
    cr.set_source_rgba(color[0], color[1], color[2], alpha)
    cr.move_to(x, ty)
    PangoCairo.show_layout(cr, layout)
    return th


def rrect(cr, x, y, w, h, r=4.0):
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()


def paint_event_rect(cr, x, y, w, h, ev, radius=4.0):
    """Desenha bloco de evento com estilo por origem (local / google / sync)."""
    src = getattr(ev, "source", "google")
    synced = getattr(ev, "synced", False)
    rrect(cr, x, y, w, h, radius)
    cr.set_source_rgba(ev.color[0], ev.color[1], ev.color[2], 0.90)
    cr.fill()
    if src == "local" and not synced:
        cr.set_line_width(1.2)
        cr.set_dash([4.0, 3.0], 0)
        cr.set_source_rgba(ev.color[0] * 0.55, ev.color[1] * 0.55, ev.color[2] * 0.55, 0.95)
        rrect(cr, x + 0.6, y + 0.6, w - 1.2, h - 1.2, max(2.0, radius - 1))
        cr.stroke()
        cr.set_dash([], 0)
    elif synced:
        cr.set_line_width(1.0)
        cr.set_source_rgba(1, 1, 1, 0.35)
        cr.move_to(x + w - 10, y + 4)
        cr.line_to(x + w - 4, y + 10)
        cr.line_to(x + w - 14, y + 10)
        cr.close_path()
        cr.stroke()


class Palette(object):
    """Cores derivadas do tema GTK (funciona em tema claro e escuro)."""

    def __init__(self, widget):
        ctx = widget.get_style_context()
        self.base = self._color(ctx, "theme_base_color", (1, 1, 1))
        self.fg = self._color(ctx, "theme_fg_color", (0.15, 0.15, 0.15))
        self.accent = self._color(ctx, "theme_selected_bg_color", (0.10, 0.45, 0.91))
        self.alt = mix(self.base, self.fg, 0.05)
        self.grid = mix(self.base, self.fg, 0.17)
        self.grid_soft = mix(self.base, self.fg, 0.09)
        self.muted = mix(self.base, self.fg, 0.50)
        self.now = (0.85, 0.16, 0.14)

    @staticmethod
    def _color(ctx, name, fallback):
        try:
            ok, rgba = ctx.lookup_color(name)
            if ok:
                return (rgba.red, rgba.green, rgba.blue)
        except Exception:
            pass
        return fallback


# =============================================================================
# MODELO
# =============================================================================
class Ev(object):
    def __init__(self, raw, cal_id, cal_name, color, editable=True,
                 source="google", synced=False):
        self.raw = raw or {}
        self.id = self.raw.get("id", "")
        self.cal_id = cal_id
        self.cal_name = cal_name
        self.editable = editable
        self.source = source
        self.synced = synced
        self.summary = (self.raw.get("summary") or "(sem titulo)").strip()
        self.description = self.raw.get("description") or ""
        self.location = self.raw.get("location") or ""
        self.link = self.raw.get("htmlLink") or ""
        self.color = EVENT_COLORS.get(str(self.raw.get("colorId") or ""), color)
        self.start, self.all_day = parse_g_time(self.raw.get("start"))
        self.end, _ = parse_g_time(self.raw.get("end"))
        if self.start is None:
            self.start = date.today()
            self.all_day = True
        if self.end is None:
            self.end = self.start
        span = event_day_span(self.raw) or (self.start.toordinal()
                                           if isinstance(self.start, date)
                                           and not isinstance(self.start, datetime.datetime)
                                           else self.start.date().toordinal(),) * 2
        self.first_day = date.fromordinal(span[0])
        self.last_day = date.fromordinal(span[1])

    @property
    def multiday(self):
        return self.all_day or self.last_day != self.first_day

    def spans(self, day):
        return self.first_day <= day <= self.last_day

    def minutes_on(self, day):
        base = datetime.datetime.combine(day, datetime.time.min)
        m0 = (self.start - base).total_seconds() / 60.0
        m1 = (self.end - base).total_seconds() / 60.0
        m0 = max(0.0, min(1440.0, m0))
        m1 = max(0.0, min(1440.0, m1))
        if m1 - m0 < 18:
            m1 = min(1440.0, m0 + 18)
        return m0, m1

    def hour_label(self):
        if self.all_day:
            return "dia inteiro"
        return "%s - %s" % (self.start.strftime("%H:%M"), self.end.strftime("%H:%M"))

    def sort_key(self):
        if self.all_day:
            return (0, 0, 0, self.summary.lower())
        return (1, self.start.hour, self.start.minute, self.summary.lower())


def pack_columns(events, day):
    """Distribui eventos sobrepostos em colunas -> [(ev, col, ncols, m0, m1)]."""
    items = []
    for ev in events:
        m0, m1 = ev.minutes_on(day)
        items.append([ev, m0, m1])
    items.sort(key=lambda i: (i[1], i[2]))
    out = []
    cluster = []
    cluster_end = -1.0

    def flush():
        cols = []
        entries = []
        for it in cluster:
            slot = -1
            for idx, end in enumerate(cols):
                if end <= it[1] + 0.01:
                    cols[idx] = it[2]
                    slot = idx
                    break
            if slot < 0:
                cols.append(it[2])
                slot = len(cols) - 1
            entries.append([it[0], slot, 0, it[1], it[2]])
        total = max(1, len(cols))
        for entry in entries:
            entry[2] = total
        out.extend(entries)

    for it in items:
        if cluster and it[1] >= cluster_end - 0.01:
            flush()
            cluster = []
            cluster_end = -1.0
        cluster.append(it)
        cluster_end = it[2] if cluster_end < 0 else max(cluster_end, it[2])
    if cluster:
        flush()
    return out


def pack_lanes(segments):
    """segments: [(i0, i1, ev)] -> ([(ev, i0, i1, lane)], n_lanes)."""
    lanes = []
    result = []
    for i0, i1, ev in sorted(segments, key=lambda s: (s[0], -(s[1] - s[0]))):
        placed = False
        for idx, lane in enumerate(lanes):
            if all(i1 < s or i0 > e for s, e in lane):
                lane.append((i0, i1))
                result.append((ev, i0, i1, idx))
                placed = True
                break
        if not placed:
            lanes.append([(i0, i1)])
            result.append((ev, i0, i1, len(lanes) - 1))
    return result, len(lanes)


# =============================================================================
# CACHE LOCAL (SQLite) - fonte de verdade da interface
# =============================================================================
class Store(object):
    def __init__(self, path=CACHE_DB):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
                CREATE TABLE IF NOT EXISTS calendars (
                    id TEXT PRIMARY KEY, summary TEXT, color TEXT,
                    editable INT, prim INT, pos INT, source TEXT DEFAULT 'google');
                CREATE TABLE IF NOT EXISTS sync (
                    cal_id TEXT PRIMARY KEY, token TEXT,
                    h0 INT, h1 INT, at REAL);
                CREATE TABLE IF NOT EXISTS events (
                    cal_id TEXT, id TEXT, d0 INT, d1 INT, payload TEXT,
                    PRIMARY KEY (cal_id, id));
                CREATE TABLE IF NOT EXISTS sync_links (
                    local_id TEXT PRIMARY KEY,
                    google_cal_id TEXT, google_event_id TEXT, synced_at REAL);
                CREATE INDEX IF NOT EXISTS idx_ev_range ON events (d1, d0);
            """)
            self.db.commit()
        self._migrate_schema()
        self.ensure_local_calendar()

    def _migrate_schema(self):
        cur = self.get_meta("schema")
        if cur == SCHEMA_VERSION:
            return
        with self.lock:
            cols = [r[1] for r in self.db.execute("PRAGMA table_info(calendars)")]
            if "source" not in cols:
                self.db.execute(
                    "ALTER TABLE calendars ADD COLUMN source TEXT DEFAULT 'google'")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS sync_links (
                    local_id TEXT PRIMARY KEY,
                    google_cal_id TEXT, google_event_id TEXT, synced_at REAL);
            """)
            self.db.execute(
                "UPDATE calendars SET source='google' WHERE source IS NULL")
            self.db.commit()
        self.set_meta("schema", SCHEMA_VERSION)

    def ensure_local_calendar(self):
        with self.lock:
            row = self.db.execute(
                "SELECT id FROM calendars WHERE id=?", (LOCAL_CAL_ID,)).fetchone()
            if row:
                return
            self.db.execute(
                "INSERT INTO calendars(id,summary,color,editable,prim,pos,source) "
                "VALUES(?,?,?,?,?,?,?)",
                (LOCAL_CAL_ID, LOCAL_CAL_NAME, rgb_to_hex(LOCAL_COLOR),
                 1, 0, -1, "local"))
            self.db.commit()

    # ------------------------------------------------------------------- meta
    def get_meta(self, key):
        with self.lock:
            row = self.db.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return row["v"] if row else None

    def set_meta(self, key, value):
        with self.lock:
            self.db.execute("INSERT INTO meta(k,v) VALUES(?,?) "
                            "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                            (key, str(value)))
            self.db.commit()

    def wipe(self):
        with self.lock:
            self.db.executescript("DELETE FROM events; DELETE FROM sync; "
                                  "DELETE FROM sync_links; "
                                  "DELETE FROM calendars; DELETE FROM meta;")
            self.db.commit()
        self.set_meta("schema", SCHEMA_VERSION)
        self.ensure_local_calendar()

    def wipe_google(self):
        """Remove cache Google; preserva agenda local."""
        with self.lock:
            self.db.execute("DELETE FROM events WHERE cal_id NOT LIKE 'local:%'")
            self.db.execute("DELETE FROM sync")
            self.db.execute("DELETE FROM sync_links")
            self.db.execute("DELETE FROM calendars WHERE id NOT LIKE 'local:%'")
            self.db.commit()
        for key in ("google_account", "last_sync"):
            with self.lock:
                self.db.execute("DELETE FROM meta WHERE k=?", (key,))
                self.db.commit()

    def ensure_account(self, email):
        """Trocar conta Google invalida so o cache Google."""
        if not email:
            return
        if self.get_meta("google_account") != email:
            self.wipe_google()
            self.set_meta("google_account", email)

    # -------------------------------------------------------------- calendarios
    def save_calendars(self, cals):
        """Atualiza agendas Google; preserva a agenda local."""
        with self.lock:
            self.db.execute("DELETE FROM calendars WHERE source='google' "
                            "OR (source IS NULL AND id NOT LIKE 'local:%')")
            rows = [(c["id"], c["summary"], rgb_to_hex(c["rgb"]),
                     int(c["editable"]), int(c["primary"]), i, "google")
                    for i, c in enumerate(cals)]
            if rows:
                self.db.executemany(
                    "INSERT INTO calendars(id,summary,color,editable,prim,pos,source) "
                    "VALUES(?,?,?,?,?,?,?)", rows)
            self.db.commit()
        self.ensure_local_calendar()

    def load_calendars(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM calendars ORDER BY "
                "CASE WHEN source='local' THEN 0 ELSE 1 END, pos").fetchall()
        return [{"id": r["id"], "summary": r["summary"], "rgb": hex_rgb(r["color"]),
                 "editable": bool(r["editable"]), "primary": bool(r["prim"]),
                 "source": (r["source"] if "source" in r.keys() else "google") or "google"}
                for r in rows]

    def drop_calendar(self, cal_id):
        if is_local_cal(cal_id):
            return
        with self.lock:
            self.db.execute("DELETE FROM events WHERE cal_id=?", (cal_id,))
            self.db.execute("DELETE FROM sync WHERE cal_id=?", (cal_id,))
            self.db.execute("DELETE FROM calendars WHERE id=?", (cal_id,))
            self.db.commit()

    # --------------------------------------------------------------- estado sync
    def sync_state(self, cal_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM sync WHERE cal_id=?", (cal_id,)).fetchone()
        if not row:
            return None
        return {"token": row["token"] or "", "h0": row["h0"],
                "h1": row["h1"], "at": row["at"]}

    def set_sync_state(self, cal_id, token, h0, h1):
        with self.lock:
            self.db.execute(
                "INSERT INTO sync(cal_id,token,h0,h1,at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(cal_id) DO UPDATE SET token=excluded.token, "
                "h0=excluded.h0, h1=excluded.h1, at=excluded.at",
                (cal_id, token or "", int(h0), int(h1), time.time()))
            self.db.commit()

    def reset_calendar(self, cal_id):
        """Descarta token e eventos (410 Gone ou resync forcado)."""
        with self.lock:
            self.db.execute("DELETE FROM events WHERE cal_id=?", (cal_id,))
            self.db.execute("DELETE FROM sync WHERE cal_id=?", (cal_id,))
            self.db.commit()

    # ------------------------------------------------------------------ eventos
    @staticmethod
    def _split(cal_id, items):
        upserts, deletes = [], []
        for raw in items:
            ev_id = raw.get("id")
            if not ev_id:
                continue
            if raw.get("status") == "cancelled":
                deletes.append((cal_id, ev_id))
                continue
            span = event_day_span(raw)
            if span is None:
                deletes.append((cal_id, ev_id))
                continue
            upserts.append((cal_id, ev_id, span[0], span[1],
                            json.dumps(raw, separators=(",", ":"))))
        return upserts, deletes

    _UPSERT = ("INSERT INTO events(cal_id,id,d0,d1,payload) VALUES(?,?,?,?,?) "
               "ON CONFLICT(cal_id,id) DO UPDATE SET d0=excluded.d0, "
               "d1=excluded.d1, payload=excluded.payload")

    def apply_changes(self, cal_id, items):
        """Aplica o delta incremental: cancelados apagam, o resto faz upsert."""
        upserts, deletes = self._split(cal_id, items)
        with self.lock:
            if deletes:
                self.db.executemany("DELETE FROM events WHERE cal_id=? AND id=?", deletes)
            if upserts:
                self.db.executemany(self._UPSERT, upserts)
            self.db.commit()
        return len(upserts), len(deletes)

    def replace_calendar(self, cal_id, items):
        """Full sync: troca o conteudo da agenda numa unica transacao."""
        upserts, _ = self._split(cal_id, items)
        with self.lock:
            try:
                self.db.execute("DELETE FROM events WHERE cal_id=?", (cal_id,))
                if upserts:
                    self.db.executemany(self._UPSERT, upserts)
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return len(upserts), 0

    def raw_between(self, day0, day1, cal_ids=None):
        sql = "SELECT cal_id, payload FROM events WHERE d1>=? AND d0<=?"
        args = [day0.toordinal(), day1.toordinal()]
        if cal_ids is not None:
            if not cal_ids:
                return []
            sql += " AND cal_id IN (%s)" % ",".join("?" * len(cal_ids))
            args.extend(cal_ids)
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
        out = []
        for row in rows:
            try:
                out.append((row["cal_id"], json.loads(row["payload"])))
            except Exception:
                pass
        return out

    def upsert_local_event(self, raw):
        cal_id = LOCAL_CAL_ID
        ev_id = raw.get("id") or new_local_event_id()
        raw = dict(raw)
        raw["id"] = ev_id
        span = event_day_span(raw)
        if span is None:
            raise ValueError("Evento local com data invalida.")
        with self.lock:
            self.db.execute(self._UPSERT,
                            (cal_id, ev_id, span[0], span[1],
                             json.dumps(raw, separators=(",", ":"))))
            self.db.commit()
        return ev_id, raw

    def delete_local_event(self, ev_id):
        with self.lock:
            self.db.execute("DELETE FROM events WHERE cal_id=? AND id=?",
                            (LOCAL_CAL_ID, ev_id))
            self.db.execute("DELETE FROM sync_links WHERE local_id=?", (ev_id,))
            self.db.commit()

    def get_sync_link(self, local_id):
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM sync_links WHERE local_id=?", (local_id,)).fetchone()
        if not row:
            return None
        return {"google_cal_id": row["google_cal_id"],
                "google_event_id": row["google_event_id"],
                "synced_at": row["synced_at"]}

    def set_sync_link(self, local_id, google_cal_id, google_event_id):
        with self.lock:
            self.db.execute(
                "INSERT INTO sync_links(local_id,google_cal_id,google_event_id,synced_at) "
                "VALUES(?,?,?,?) ON CONFLICT(local_id) DO UPDATE SET "
                "google_cal_id=excluded.google_cal_id, "
                "google_event_id=excluded.google_event_id, "
                "synced_at=excluded.synced_at",
                (local_id, google_cal_id, google_event_id, time.time()))
            self.db.commit()

    def list_unsynced_local(self, day0=None, day1=None):
        sql = ("SELECT e.id, e.payload FROM events e LEFT JOIN sync_links s "
               "ON e.id=s.local_id WHERE e.cal_id=? AND s.local_id IS NULL")
        args = [LOCAL_CAL_ID]
        if day0 and day1:
            sql += " AND e.d1>=? AND e.d0<=?"
            args.extend([day0.toordinal(), day1.toordinal()])
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
        out = []
        for row in rows:
            try:
                out.append((row["id"], json.loads(row["payload"])))
            except Exception:
                pass
        return out

    def synced_local_ids(self):
        with self.lock:
            rows = self.db.execute("SELECT local_id FROM sync_links").fetchall()
        return set(r["local_id"] for r in rows)

    def count(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]


# =============================================================================
# PLUGIN GOOGLE (REST puro)
# =============================================================================
class GooglePlugin(object):
    def __init__(self):
        self.authenticated = False
        self.email = ""
        self.client_id = ""
        self.client_secret = ""
        self.refresh_token = ""
        self.access_token = ""
        self.expiry = 0.0
        self._lock = threading.Lock()
        self.credentials_file = self.find_credentials()

    # ------------------------------------------------------------- credenciais
    @staticmethod
    def find_credentials():
        for path in CREDENTIAL_PATHS:
            if os.path.isfile(path):
                return path
        return None

    def credentials_kind(self, path=None):
        path = path or self.credentials_file
        if not path or not os.path.isfile(path):
            return "ausente"
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
        except Exception:
            return "invalido"
        if isinstance(data, dict) and "installed" in data:
            return "installed"
        if isinstance(data, dict) and "web" in data:
            return "web"
        return "invalido"

    def install_credentials(self, path):
        with open(path, "r") as fh:
            data = json.load(fh)
        if "installed" not in data:
            if "web" in data:
                raise ValueError(
                    "Este credentials.json e de um cliente OAuth do tipo "
                    "'Aplicativo Web'.\nCrie um ID do cliente OAuth do tipo "
                    "'App para desktop' no Google Cloud Console e baixe o JSON "
                    "novamente.")
            raise ValueError("Arquivo JSON invalido: nao parece um client_secret "
                             "do Google.")
        shutil.copy(path, USER_CREDENTIALS)
        try:
            os.chmod(USER_CREDENTIALS, 0o600)
        except Exception:
            pass
        self.credentials_file = USER_CREDENTIALS

    def _load_client(self):
        kind = self.credentials_kind()
        if kind == "web":
            raise ApiError("O credentials.json e de um cliente 'Aplicativo Web'.\n"
                           "E necessario um cliente do tipo 'App para desktop'.")
        if kind != "installed":
            raise ApiError("Nenhum credentials.json valido encontrado.")
        with open(self.credentials_file, "r") as fh:
            node = json.load(fh)["installed"]
        self.client_id = node.get("client_id", "")
        self.client_secret = node.get("client_secret", "")
        if not self.client_id:
            raise ApiError("credentials.json sem client_id.")

    # ------------------------------------------------------------------ token
    def _save_token(self):
        data = {"client_id": self.client_id, "client_secret": self.client_secret,
                "refresh_token": self.refresh_token, "access_token": self.access_token,
                "expiry": self.expiry, "scopes": SCOPES, "email": self.email}
        tmp = TOKEN_FILE + ".tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump(data, fh)
            os.chmod(tmp, 0o600)
            os.replace(tmp, TOKEN_FILE)
        except Exception as exc:
            sys.stderr.write("Nao foi possivel salvar o token: %s\n" % exc)

    def _apply_token_payload(self, payload):
        self.access_token = payload.get("access_token", "")
        self.expiry = time.time() + float(payload.get("expires_in", 3600)) - 60
        if payload.get("refresh_token"):
            self.refresh_token = payload["refresh_token"]

    def _refresh(self):
        payload = http_form(TOKEN_URI, {"client_id": self.client_id,
                                        "client_secret": self.client_secret,
                                        "refresh_token": self.refresh_token,
                                        "grant_type": "refresh_token"})
        self._apply_token_payload(payload)
        self._save_token()

    def _bearer(self):
        with self._lock:
            if not self.access_token or time.time() >= self.expiry:
                if not self.refresh_token:
                    raise ApiError("Sessao expirada. Faca login novamente.")
                self._refresh()
            return self.access_token

    # -------------------------------------------------------------------- API
    def _call(self, method, path, params=None, body=None, retry=True):
        headers = {"Authorization": "Bearer " + self._bearer()}
        try:
            return http_call(method, API_BASE + path, params=params, body=body,
                             headers=headers)
        except ApiError as exc:
            if exc.status == 401 and retry and self.refresh_token:
                with self._lock:
                    self._refresh()
                return self._call(method, path, params, body, retry=False)
            raise

    def _fetch_email(self):
        try:
            info = self._call("GET", "/users/me/calendarList/primary")
            self.email = info.get("id", "")
        except Exception:
            self.email = ""

    # ------------------------------------------------------------------ login
    def silent_login(self):
        if not os.path.isfile(TOKEN_FILE):
            return False
        try:
            with open(TOKEN_FILE, "r") as fh:
                data = json.load(fh)
            self.client_id = data.get("client_id", "")
            self.client_secret = data.get("client_secret", "")
            self.refresh_token = data.get("refresh_token", "")
            self.access_token = data.get("access_token", "")
            self.expiry = float(data.get("expiry") or 0)
            self.email = data.get("email", "")
            if not (self.client_id and self.refresh_token):
                return False
            self._bearer()
            self.authenticated = True
            if not self.email:
                self._fetch_email()
                self._save_token()
            return True
        except Exception as exc:
            sys.stderr.write("Login silencioso falhou: %s\n" % exc)
            self.authenticated = False
            return False

    def interactive_login(self):
        self._load_client()
        flow = DesktopFlow(self.client_id, self.client_secret, SCOPES)
        payload = flow.run(timeout=300)
        self._apply_token_payload(payload)
        self.authenticated = True
        self._fetch_email()
        self._save_token()

    def logout(self):
        token = self.refresh_token or self.access_token
        if token:
            try:
                http_form(REVOKE_URI, {"token": token})
            except Exception:
                pass
        self.authenticated = False
        self.email = ""
        self.access_token = ""
        self.refresh_token = ""
        self.expiry = 0.0
        try:
            if os.path.isfile(TOKEN_FILE):
                os.remove(TOKEN_FILE)
        except Exception:
            pass

    # --------------------------------------------------------------- recursos
    def list_calendars(self):
        items = []
        page = None
        while True:
            resp = self._call("GET", "/users/me/calendarList",
                              params={"maxResults": 250, "pageToken": page})
            items.extend(resp.get("items", []))
            page = resp.get("nextPageToken")
            if not page:
                return items

    def sync_events(self, cal_id, token=None, window=None):
        """Full sync (window) ou incremental (token). -> (items, next_token).

        syncToken e incompativel com timeMin/timeMax/orderBy, por isso a
        ordenacao e feita localmente e showDeleted fica sempre ligado (e assim
        que descobrimos exclusoes).
        """
        path = "/calendars/%s/events" % urllib.parse.quote(cal_id, safe="")
        items, page = [], None
        while True:
            params = {"maxResults": 2500, "singleEvents": True,
                      "showDeleted": True, "pageToken": page}
            if token:
                params["syncToken"] = token
            elif window:
                params["timeMin"] = local_iso(window[0])
                params["timeMax"] = local_iso(window[1])
            try:
                resp = self._call("GET", path, params=params)
            except ApiError as exc:
                if exc.status == 410:
                    raise SyncExpired(cal_id)
                raise
            items.extend(resp.get("items", []))
            page = resp.get("nextPageToken")
            if not page:
                return items, resp.get("nextSyncToken")

    def insert_event(self, cal_id, body):
        path = "/calendars/%s/events" % urllib.parse.quote(cal_id, safe="")
        return self._call("POST", path, body=body)

    def patch_event(self, cal_id, ev_id, body):
        path = "/calendars/%s/events/%s" % (urllib.parse.quote(cal_id, safe=""),
                                            urllib.parse.quote(ev_id, safe=""))
        return self._call("PATCH", path, body=body)

    def delete_event(self, cal_id, ev_id):
        path = "/calendars/%s/events/%s" % (urllib.parse.quote(cal_id, safe=""),
                                            urllib.parse.quote(ev_id, safe=""))
        self._call("DELETE", path)


# =============================================================================
# CONTROLLER
# =============================================================================
class Controller(object):
    def __init__(self, plugin):
        self.plugin = plugin
        self.store = Store()
        self.store.ensure_local_calendar()
        self.settings = load_settings()
        self.view = self.settings.get("view", "week")
        if self.view not in ("day", "week", "month"):
            self.view = "week"
        self.week_start = int(self.settings.get("week_start", 6))
        self.anchor = date.today()
        self.selected = date.today()
        self.hidden = set(self.settings.get("hidden", []))
        self.calendars = self.store.load_calendars()
        self.events = []
        self.syncing = False
        self.pushing = False
        self.error = None
        self.last_sync = self.store.get_meta("last_sync")
        self._listeners = []
        self._sync_lock = threading.Lock()
        self._synced_ids = self.store.synced_local_ids()

    # ---------------------------------------------------------------- listeners
    def connect(self, callback):
        self._listeners.append(callback)

    def notify(self):
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                traceback.print_exc()

    # -------------------------------------------------------------- calendario
    def week_start_of(self, day):
        return day - timedelta(days=(day.weekday() - self.week_start) % 7)

    def visible_days(self):
        if self.view == "day":
            return [self.anchor]
        start = self.week_start_of(self.anchor)
        return [start + timedelta(days=i) for i in range(7)]

    def month_grid(self):
        start = self.week_start_of(self.anchor.replace(day=1))
        return [start + timedelta(days=i) for i in range(42)]

    def weekday_order(self):
        return [(self.week_start + i) % 7 for i in range(7)]

    def window_days(self):
        days = self.month_grid() if self.view == "month" else self.visible_days()
        return days[0], days[-1]

    def title_text(self):
        if self.view == "day":
            return fmt_dia_longo(self.anchor)
        if self.view == "week":
            days = self.visible_days()
            a, b = days[0], days[-1]
            if a.month == b.month:
                return "%d - %d de %s de %d" % (a.day, b.day, MESES[a.month - 1], a.year)
            if a.year == b.year:
                return "%d de %s - %d de %s de %d" % (a.day, MESES_ABR[a.month - 1],
                                                      b.day, MESES_ABR[b.month - 1], a.year)
            return "%s %d - %s %d" % (MESES_ABR[a.month - 1], a.year,
                                      MESES_ABR[b.month - 1], b.year)
        return fmt_mes_ano(self.anchor)

    # ------------------------------------------------------ leitura (do cache)
    @property
    def enabled_ids(self):
        return [c["id"] for c in self.calendars if c["id"] not in self.hidden]

    def load_window(self):
        """Instantaneo: reconstroi self.events a partir do SQLite."""
        d0, d1 = self.window_days()
        meta = dict((c["id"], c) for c in self.calendars)
        ids = self.enabled_ids
        synced = self.store.synced_local_ids()
        events = []
        for cal_id, raw in self.store.raw_between(d0, d1, ids):
            cal = meta.get(cal_id)
            if cal is None:
                continue
            src = cal.get("source", "google")
            if is_local_cal(cal_id):
                src = "local"
            ev_id = raw.get("id", "")
            events.append(Ev(raw, cal_id, cal["summary"], cal["rgb"], cal["editable"],
                             source=src, synced=ev_id in synced))
        self.events = events
        self._synced_ids = synced
        self.notify()

    def events_visible(self):
        return [e for e in self.events if e.cal_id not in self.hidden]

    def events_of(self, day):
        return sorted([e for e in self.events_visible() if e.spans(day)],
                      key=lambda e: e.sort_key())

    def writable_calendars(self):
        return [c for c in self.calendars if c["editable"]]

    def google_calendars(self):
        return [c for c in self.calendars
                if c.get("source", "google") == "google" and not is_local_cal(c["id"])]

    def primary_google_calendar(self):
        for cal in self.google_calendars():
            if cal.get("primary"):
                return cal["id"]
        g = self.google_calendars()
        return g[0]["id"] if g else None

    def unsynced_local_count(self):
        d0, d1 = self.window_days()
        return len(self.store.list_unsynced_local(d0, d1))

    # -------------------------------------------------------------- horizonte
    @staticmethod
    def desired_horizon():
        today = date.today()
        return ((today - timedelta(days=HORIZON_BACK)).toordinal(),
                (today + timedelta(days=HORIZON_FWD)).toordinal())

    def horizon_covers_window(self):
        if not self.calendars:
            return False
        d0, d1 = self.window_days()
        for cal in self.calendars:
            if cal["id"] in self.hidden or is_local_cal(cal["id"]):
                continue
            state = self.store.sync_state(cal["id"])
            if not state:
                return False
            if not (state["h0"] <= d0.toordinal() and state["h1"] >= d1.toordinal()):
                return False
        return True

    def refresh_view(self):
        """Sempre pinta do cache; so vai a rede se o horizonte nao cobre."""
        self.load_window()
        if not self.horizon_covers_window():
            self.sync()

    # -------------------------------------------------------------- navegacao
    def set_view(self, view):
        if view == self.view:
            return
        self.view = view
        self.settings["view"] = view
        save_settings(self.settings)
        self.refresh_view()

    def set_week_start(self, value):
        self.week_start = int(value)
        self.settings["week_start"] = self.week_start
        save_settings(self.settings)
        self.refresh_view()

    def go_today(self):
        self.anchor = date.today()
        self.selected = self.anchor
        self.refresh_view()

    def go_to(self, day, view=None):
        self.anchor = day
        self.selected = day
        if view and view != self.view:
            self.view = view
            self.settings["view"] = view
            save_settings(self.settings)
        self.refresh_view()

    def step(self, delta):
        if self.view == "day":
            self.anchor += timedelta(days=delta)
        elif self.view == "week":
            self.anchor += timedelta(days=7 * delta)
        else:
            month = self.anchor.month - 1 + delta
            year = self.anchor.year + month // 12
            month = month % 12 + 1
            day = min(self.anchor.day, pycal.monthrange(year, month)[1])
            self.anchor = date(year, month, day)
        self.selected = self.anchor
        self.refresh_view()

    def toggle_calendar(self, cal_id, active):
        if active:
            self.hidden.discard(cal_id)
        else:
            self.hidden.add(cal_id)
        self.settings["hidden"] = sorted(self.hidden)
        save_settings(self.settings)
        self.refresh_view()

    # ------------------------------------------------------------------- sync
    def sync(self, only=None, full=False):
        """Sincroniza em background. only=[cal_id]; full=True descarta tokens."""
        if not self.plugin.authenticated:
            return
        if not self._sync_lock.acquire(blocking=False):
            return                              # ja ha um sync em andamento
        self.syncing = True
        self.error = None
        self.notify()
        threading.Thread(target=self._sync_worker, args=(only, full),
                         daemon=True).start()

    def _sync_worker(self, only, full):
        errors = []
        changed = 0
        try:
            cals = self._sync_calendar_list(errors)
            h0, h1 = self.desired_horizon()
            window = (datetime.datetime.fromordinal(h0),
                      datetime.datetime.fromordinal(h1) + timedelta(days=1))
            targets = [c for c in cals
                       if c["id"] not in self.hidden
                       and (only is None or c["id"] in only)]
            for cal in targets:
                changed += self._sync_one(cal, window, h0, h1, full, errors)
        except Exception as exc:
            errors.append(api_error_text(exc))
            traceback.print_exc()
        finally:
            self._sync_lock.release()
        GLib.idle_add(self._sync_done, errors, changed)

    def _sync_calendar_list(self, errors):
        try:
            items = self.plugin.list_calendars()
        except Exception as exc:
            errors.append(api_error_text(exc))
            return list(self.calendars)
        cals = []
        for it in items:
            if it.get("deleted"):
                continue
            cals.append({"id": it.get("id"),
                         "summary": (it.get("summaryOverride") or it.get("summary")
                                     or it.get("id")),
                         "rgb": hex_rgb(it.get("backgroundColor")),
                         "editable": it.get("accessRole") in ("owner", "writer"),
                         "primary": bool(it.get("primary"))})
        cals.sort(key=lambda c: (not c["primary"], (c["summary"] or "").lower()))
        live = set(c["id"] for c in cals)
        for old in self.store.load_calendars():
            if old["id"] not in live:
                self.store.drop_calendar(old["id"])
        self.store.save_calendars(cals)
        GLib.idle_add(self._set_calendars, cals)
        return cals

    def _sync_one(self, cal, window, h0, h1, full, errors):
        cal_id = cal["id"]
        if full:
            self.store.reset_calendar(cal_id)
        state = self.store.sync_state(cal_id)
        token = state["token"] if state else ""
        # horizonte insuficiente -> refaz a base
        if state and not (state["h0"] <= h0 and state["h1"] >= h1):
            self.store.reset_calendar(cal_id)
            token = ""
        changed = 0
        for attempt in (1, 2):
            try:
                items, next_token = self.plugin.sync_events(
                    cal_id, token=token or None, window=None if token else window)
                if token:
                    up, dele = self.store.apply_changes(cal_id, items)
                else:
                    up, dele = self.store.replace_calendar(cal_id, items)
                changed += up + dele
                # grava o horizonte mesmo sem token: a navegacao continua offline
                self.store.set_sync_state(cal_id, next_token or "", h0, h1)
                return changed
            except SyncExpired:
                self.store.reset_calendar(cal_id)
                token = ""
                if attempt == 2:
                    errors.append("Sincronizacao reiniciada em %s." % cal["summary"])
            except Exception as exc:
                errors.append("%s: %s" % (cal["summary"], api_error_text(exc)))
                return changed
        return changed

    def _set_calendars(self, cals):
        self.calendars = cals
        self.notify()
        return False

    def _sync_done(self, errors, changed):
        self.syncing = False
        self.error = "\n".join(errors) if errors else None
        if not errors:
            self.last_sync = str(time.time())
            self.store.set_meta("last_sync", self.last_sync)
        self.load_window()
        return False

    def hard_reset(self):
        self.store.wipe_google()
        self.store.ensure_local_calendar()
        self.calendars = self.store.load_calendars()
        self.events = []
        self.last_sync = None
        self.notify()

    # ---------------------------------------------------------------- escrita
    def save_event(self, cal_id, body, ev=None, on_error=None):
        if is_local_cal(cal_id):
            self._save_local_event(body, ev, on_error)
            return
        if not self.plugin.authenticated:
            if on_error:
                on_error("Conecte o Google Agenda para salvar nesta agenda.")
            return

        def work():
            touched = [cal_id]
            try:
                if ev is None:
                    self.plugin.insert_event(cal_id, body)
                elif ev.cal_id == cal_id:
                    self.plugin.patch_event(cal_id, ev.id, body)
                else:
                    self.plugin.insert_event(cal_id, body)
                    self.plugin.delete_event(ev.cal_id, ev.id)
                    touched.append(ev.cal_id)
                GLib.idle_add(self.sync, touched)
            except Exception as exc:
                msg = api_error_text(exc)
                if on_error:
                    GLib.idle_add(on_error, msg)
        threading.Thread(target=work, daemon=True).start()

    def _save_local_event(self, body, ev=None, on_error=None):
        try:
            raw = dict(body)
            if ev is not None:
                raw["id"] = ev.id
            else:
                raw["id"] = new_local_event_id()
            self.store.upsert_local_event(raw)
            GLib.idle_add(self.load_window)
        except Exception as exc:
            if on_error:
                on_error(str(exc))

    def delete_event(self, ev, on_error=None):
        if is_local_cal(ev.cal_id):
            try:
                self.store.delete_local_event(ev.id)
                GLib.idle_add(self.load_window)
            except Exception as exc:
                if on_error:
                    on_error(str(exc))
            return
        if not self.plugin.authenticated:
            if on_error:
                on_error("Conecte o Google Agenda para excluir desta agenda.")
            return

        def work():
            try:
                self.plugin.delete_event(ev.cal_id, ev.id)
                GLib.idle_add(self.sync, [ev.cal_id])
            except Exception as exc:
                msg = api_error_text(exc)
                if on_error:
                    GLib.idle_add(on_error, msg)
        threading.Thread(target=work, daemon=True).start()

    def push_local_to_google(self, target_cal_id=None, on_done=None):
        """Fase D/E: envia eventos locais nao sincronizados para o Google."""
        if not self.plugin.authenticated:
            if on_done:
                on_done(False, "Conecte o Google Agenda primeiro.")
            return
        if not self._sync_lock.acquire(blocking=False):
            return
        self.pushing = True
        self.notify()

        def work():
            errors = []
            sent = 0
            cal_id = target_cal_id or self.primary_google_calendar()
            try:
                if not cal_id:
                    raise ApiError("Nenhuma agenda Google editavel encontrada.")
                items = self.store.list_unsynced_local()
                for local_id, raw in items:
                    try:
                        resp = self.plugin.insert_event(cal_id, raw)
                        gid = resp.get("id")
                        if gid:
                            self.store.set_sync_link(local_id, cal_id, gid)
                            sent += 1
                    except Exception as exc:
                        title = raw.get("summary", local_id)
                        errors.append("%s: %s" % (title, api_error_text(exc)))
                if sent:
                    GLib.idle_add(self.sync, [cal_id])
            except Exception as exc:
                errors.append(api_error_text(exc))
            finally:
                self._sync_lock.release()
            GLib.idle_add(self._push_done, sent, errors, on_done)

        threading.Thread(target=work, daemon=True).start()

    def _push_done(self, sent, errors, on_done):
        self.pushing = False
        self.load_window()
        if errors:
            self.error = "\n".join(errors)
        if on_done:
            if errors and not sent:
                on_done(False, "\n".join(errors))
            else:
                msg = "%d evento(s) enviado(s) ao Google." % sent
                if errors:
                    msg += "\n" + "\n".join(errors)
                on_done(True, msg)
        return False


# =============================================================================
# DIALOGOS
# =============================================================================
def error_dialog(parent, primary, secondary=None):
    dlg = Gtk.MessageDialog(transient_for=parent, modal=parent is not None,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.OK, text=primary)
    if secondary:
        dlg.format_secondary_text(secondary)
    dlg.run()
    dlg.destroy()


class DateButton(Gtk.Button):
    def __init__(self, value, on_change=None):
        super().__init__()
        self.value = value
        self.on_change = on_change
        self._sync()
        self.connect("clicked", self._open)

    def _sync(self):
        self.set_label(self.value.strftime("%d/%m/%Y"))

    def set_value(self, value):
        self.value = value
        self._sync()

    def _open(self, *_a):
        pop = Gtk.Popover.new(self)
        cal = Gtk.Calendar()
        cal.select_month(self.value.month - 1, self.value.year)
        cal.select_day(self.value.day)
        cal.connect("day-selected", self._picked)
        cal.connect("day-selected-double-click", lambda *_x: pop.popdown())
        pop.add(cal)
        pop.show_all()
        pop.popup()

    def _picked(self, cal):
        year, month, day = cal.get_date()
        self.value = date(year, month + 1, day)
        self._sync()
        if self.on_change:
            self.on_change(self.value)


class TimeCombo(Gtk.ComboBoxText):
    def __init__(self, value):
        super().__init__(has_entry=True)
        for hour in range(24):
            for minute in (0, 30):
                self.append_text("%02d:%02d" % (hour, minute))
        self.get_child().set_width_chars(6)
        self.set_value(value)

    def set_value(self, value):
        self.get_child().set_text(value.strftime("%H:%M"))

    def get_value(self):
        raw = (self.get_active_text() or "").strip().replace("h", ":").replace(".", ":")
        if not raw:
            return None
        parts = raw.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        except ValueError:
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return datetime.time(hour, minute)


class EventEditor(Gtk.Dialog):
    def __init__(self, parent, ctrl, ev=None, day=None, start_minute=None, all_day=False):
        super().__init__(title="Editar evento" if ev else "Novo evento",
                         transient_for=parent, modal=True)
        self.ctrl = ctrl
        self.ev = ev
        self.parent_win = parent
        self.set_default_size(480, -1)
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        save = self.add_button("Salvar", Gtk.ResponseType.OK)
        save.get_style_context().add_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(row_spacing=8, column_spacing=10, margin=14)
        self.get_content_area().pack_start(grid, True, True, 0)

        row = 0
        self.title_entry = Gtk.Entry(hexpand=True)
        self.title_entry.set_placeholder_text("Adicionar titulo")
        self.title_entry.set_activates_default(True)
        grid.attach(Gtk.Label(label="Titulo", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.title_entry, 1, row, 3, 1)
        row += 1

        self.cal_combo = Gtk.ComboBoxText()
        self.cal_ids = []
        for cal in ctrl.writable_calendars():
            self.cal_combo.append_text(cal["summary"])
            self.cal_ids.append(cal["id"])
        grid.attach(Gtk.Label(label="Agenda", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.cal_combo, 1, row, 3, 1)
        row += 1

        self.allday_switch = Gtk.Switch(halign=Gtk.Align.START)
        grid.attach(Gtk.Label(label="Dia inteiro", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.allday_switch, 1, row, 3, 1)
        row += 1

        if ev:
            if ev.all_day:
                sd, ed = ev.first_day, ev.last_day
                st, et = datetime.time(9, 0), datetime.time(10, 0)
            else:
                sd, ed = ev.start.date(), ev.end.date()
                st, et = ev.start.time(), ev.end.time()
        else:
            sd = ed = day or ctrl.selected
            if start_minute is None:
                now = datetime.datetime.now()
                st = now.replace(minute=0 if now.minute < 30 else 30,
                                 second=0, microsecond=0).time()
            else:
                st = datetime.time(int(start_minute // 60), int(start_minute % 60))
            end_dt = datetime.datetime.combine(sd, st) + timedelta(hours=1)
            ed, et = end_dt.date(), end_dt.time()

        self.start_date = DateButton(sd, self._start_changed)
        self.start_time = TimeCombo(st)
        self.end_date = DateButton(ed)
        self.end_time = TimeCombo(et)
        grid.attach(Gtk.Label(label="Inicio", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.start_date, 1, row, 1, 1)
        grid.attach(self.start_time, 2, row, 1, 1)
        row += 1
        grid.attach(Gtk.Label(label="Fim", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.end_date, 1, row, 1, 1)
        grid.attach(self.end_time, 2, row, 1, 1)
        row += 1

        self.place_entry = Gtk.Entry(hexpand=True)
        self.place_entry.set_placeholder_text("Local (opcional)")
        grid.attach(Gtk.Label(label="Local", halign=Gtk.Align.END), 0, row, 1, 1)
        grid.attach(self.place_entry, 1, row, 3, 1)
        row += 1

        self.desc_view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD)
        scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroll.set_size_request(-1, 92)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.desc_view)
        grid.attach(Gtk.Label(label="Descricao", halign=Gtk.Align.END,
                              valign=Gtk.Align.START), 0, row, 1, 1)
        grid.attach(scroll, 1, row, 3, 1)

        if ev:
            self.title_entry.set_text("" if ev.summary == "(sem titulo)" else ev.summary)
            self.place_entry.set_text(ev.location)
            self.desc_view.get_buffer().set_text(ev.description)
            self.allday_switch.set_active(ev.all_day)
            if ev.cal_id in self.cal_ids:
                self.cal_combo.set_active(self.cal_ids.index(ev.cal_id))
            elif self.cal_ids:
                self.cal_combo.set_active(0)
        else:
            self.allday_switch.set_active(all_day)
            if self.cal_ids:
                idx = 0
                if LOCAL_CAL_ID in self.cal_ids:
                    idx = self.cal_ids.index(LOCAL_CAL_ID)
                self.cal_combo.set_active(idx)

        self.allday_switch.connect("notify::active", self._allday_toggled)
        self._allday_toggled()
        self.show_all()
        self.title_entry.grab_focus()

    def _start_changed(self, value):
        if self.end_date.value < value:
            self.end_date.set_value(value)

    def _allday_toggled(self, *_a):
        active = self.allday_switch.get_active()
        self.start_time.set_sensitive(not active)
        self.end_time.set_sensitive(not active)

    def build_body(self):
        buf = self.desc_view.get_buffer()
        body = {"summary": self.title_entry.get_text().strip() or "(sem titulo)",
                "description": buf.get_text(buf.get_start_iter(),
                                            buf.get_end_iter(), False).strip(),
                "location": self.place_entry.get_text().strip()}
        if self.allday_switch.get_active():
            sd = self.start_date.value
            ed = max(self.end_date.value, sd)
            body["start"] = {"date": sd.isoformat()}
            body["end"] = {"date": (ed + timedelta(days=1)).isoformat()}
        else:
            st, et = self.start_time.get_value(), self.end_time.get_value()
            if st is None or et is None:
                raise ValueError("Horario invalido. Use o formato HH:MM.")
            start = datetime.datetime.combine(self.start_date.value, st)
            end = datetime.datetime.combine(self.end_date.value, et)
            if end <= start:
                end = start + timedelta(hours=1)
            body["start"] = {"dateTime": local_iso(start)}
            body["end"] = {"dateTime": local_iso(end)}
        return body

    def selected_calendar(self):
        idx = self.cal_combo.get_active()
        return self.cal_ids[idx] if 0 <= idx < len(self.cal_ids) else None

    def run_and_save(self):
        while True:
            if self.run() != Gtk.ResponseType.OK:
                return False
            cal_id = self.selected_calendar()
            if not cal_id:
                error_dialog(self, "Nenhuma agenda com permissao de escrita.")
                continue
            try:
                body = self.build_body()
            except ValueError as exc:
                error_dialog(self, str(exc))
                continue
            win = self.parent_win
            self.ctrl.save_event(
                cal_id, body, self.ev,
                on_error=lambda m: error_dialog(win, "Erro ao salvar", m))
            return True


class EventDetails(Gtk.Dialog):
    def __init__(self, parent, ctrl, ev):
        super().__init__(title="Detalhes do evento", transient_for=parent, modal=True)
        self.ctrl = ctrl
        self.ev = ev
        self.parent_win = parent
        self.set_default_size(440, -1)
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=16)
        self.get_content_area().pack_start(wrap, True, True, 0)

        head = Gtk.Box(spacing=10)
        dot = Gtk.DrawingArea()
        dot.set_size_request(14, 14)
        dot.set_valign(Gtk.Align.CENTER)
        dot.connect("draw", self._draw_dot)
        head.pack_start(dot, False, False, 0)
        title = Gtk.Label(xalign=0.0)
        title.set_markup("<b><big>%s</big></b>" % GLib.markup_escape_text(ev.summary))
        title.set_line_wrap(True)
        head.pack_start(title, True, True, 0)
        wrap.pack_start(head, False, False, 0)

        if ev.all_day:
            if ev.first_day == ev.last_day:
                when = "%s - dia inteiro" % fmt_dia_longo(ev.first_day)
            else:
                when = "%s ate %s" % (fmt_dia_longo(ev.first_day),
                                      fmt_dia_longo(ev.last_day))
        else:
            when = "%s\n%s" % (fmt_dia_longo(ev.start.date()), ev.hour_label())
        wrap.pack_start(self._line("Quando", when), False, False, 0)
        wrap.pack_start(self._line("Agenda", ev.cal_name), False, False, 0)
        wrap.pack_start(self._line("Origem", event_source_label(ev)), False, False, 0)
        if ev.location:
            wrap.pack_start(self._line("Local", ev.location), False, False, 0)
        if ev.description:
            view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, editable=False)
            view.get_buffer().set_text(ev.description)
            scroll = Gtk.ScrolledWindow()
            scroll.set_size_request(-1, 110)
            scroll.set_shadow_type(Gtk.ShadowType.IN)
            scroll.add(view)
            wrap.pack_start(scroll, True, True, 0)
        if ev.link and ev.source != "local":
            link = Gtk.LinkButton.new_with_label(ev.link, "Abrir no Google Agenda")
            link.set_halign(Gtk.Align.START)
            wrap.pack_start(link, False, False, 0)

        self.add_button("Fechar", Gtk.ResponseType.CLOSE)
        if ev.editable:
            self.add_button("Excluir", 101)
            self.add_button("Editar", 102).get_style_context().add_class("suggested-action")
        self.show_all()

    def _draw_dot(self, _w, cr):
        cr.set_source_rgb(*self.ev.color)
        cr.arc(7, 7, 6, 0, 6.2832)
        cr.fill()

    @staticmethod
    def _line(label, value):
        box = Gtk.Box(spacing=8)
        lbl = Gtk.Label(xalign=1.0, yalign=0.0)
        lbl.set_markup("<small><b>%s</b></small>" % label)
        lbl.set_size_request(72, -1)
        box.pack_start(lbl, False, False, 0)
        val = Gtk.Label(label=value, xalign=0.0)
        val.set_line_wrap(True)
        val.set_selectable(True)
        box.pack_start(val, True, True, 0)
        return box

    def run_actions(self):
        response = self.run()
        self.hide()
        if response == 102:
            editor = EventEditor(self.parent_win, self.ctrl, ev=self.ev)
            editor.run_and_save()
            editor.destroy()
        elif response == 101:
            confirm = Gtk.MessageDialog(transient_for=self.parent_win, modal=True,
                                        message_type=Gtk.MessageType.QUESTION,
                                        buttons=Gtk.ButtonsType.OK_CANCEL,
                                        text="Excluir \u201c%s\u201d?" % self.ev.summary)
            ok = confirm.run()
            confirm.destroy()
            if ok == Gtk.ResponseType.OK:
                self.ctrl.delete_event(
                    self.ev,
                    on_error=lambda m: error_dialog(self.parent_win, "Erro ao excluir", m))


# =============================================================================
# MINI CALENDARIO
# =============================================================================
class MiniCalendar(Gtk.Box):
    CELL_H = 24

    def __init__(self, ctrl):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.ctrl = ctrl
        self.shown = ctrl.anchor.replace(day=1)

        header = Gtk.Box(spacing=2)
        self.label = Gtk.Label(xalign=0.0)
        header.pack_start(self.label, True, True, 4)
        for icon, delta in (("pan-start-symbolic", -1), ("pan-end-symbolic", 1)):
            btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", self._month, delta)
            header.pack_start(btn, False, False, 0)
        self.pack_start(header, False, False, 0)

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(-1, self.CELL_H * 7)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        self.area.connect("draw", self._draw)
        self.area.connect("button-press-event", self._click)
        self.area.connect("scroll-event", self._scroll)
        self.pack_start(self.area, False, False, 0)
        self.refresh()

    def refresh(self):
        self.shown = self.ctrl.anchor.replace(day=1)
        self._title()
        self.area.queue_draw()

    def _title(self):
        self.label.set_markup("<b>%s</b>" % fmt_mes_ano(self.shown).capitalize())

    def _month(self, _btn, delta):
        month = self.shown.month - 1 + delta
        self.shown = date(self.shown.year + month // 12, month % 12 + 1, 1)
        self._title()
        self.area.queue_draw()

    def _scroll(self, _w, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self._month(None, -1)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self._month(None, 1)
        return True

    def _cells(self):
        start = self.ctrl.week_start_of(self.shown)
        return [start + timedelta(days=i) for i in range(42)]

    def _draw(self, widget, cr):
        pal = Palette(widget)
        width = widget.get_allocated_width()
        cw, ch = width / 7.0, self.CELL_H
        today = date.today()
        for idx, weekday in enumerate(self.ctrl.weekday_order()):
            text(cr, idx * cw, 2, DIAS_MINI[weekday], size=10.0, color=pal.muted,
                 width=cw, height=ch - 6, align="center")
        for i, day in enumerate(self._cells()):
            x, y = (i % 7) * cw, ch + (i // 7) * ch
            is_today = day == today
            selected = day == self.ctrl.anchor
            color = pal.fg if day.month == self.shown.month else pal.muted
            if is_today:
                cr.set_source_rgb(*pal.accent)
                cr.arc(x + cw / 2.0, y + ch / 2.0, min(cw, ch) / 2.0 - 2, 0, 6.2832)
                cr.fill()
                color = readable_on(pal.accent)
            elif selected:
                cr.set_source_rgba(pal.accent[0], pal.accent[1], pal.accent[2], 0.20)
                cr.arc(x + cw / 2.0, y + ch / 2.0, min(cw, ch) / 2.0 - 2, 0, 6.2832)
                cr.fill()
            text(cr, x, y, str(day.day), size=10.5, color=color, width=cw,
                 height=ch, align="center", bold=is_today or selected)
        return False

    def _click(self, _w, event):
        width = self.area.get_allocated_width()
        col = int(event.x / (width / 7.0))
        row = int((event.y - self.CELL_H) / self.CELL_H)
        if 0 <= row <= 5 and 0 <= col <= 6:
            self.ctrl.go_to(self._cells()[row * 7 + col])
        return True


# =============================================================================
# SIDEBAR
# =============================================================================
class Sidebar(Gtk.Box):
    def __init__(self, ctrl, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.ctrl = ctrl
        self.window = window
        self.set_size_request(238, -1)
        self.get_style_context().add_class("at-sidebar")
        for setter in ("set_margin_top", "set_margin_bottom",
                       "set_margin_start", "set_margin_end"):
            getattr(self, setter)(10)

        create = Gtk.Button()
        create.get_style_context().add_class("suggested-action")
        cbox = Gtk.Box(spacing=6)
        cbox.pack_start(Gtk.Image.new_from_icon_name("list-add-symbolic",
                                                     Gtk.IconSize.BUTTON), False, False, 0)
        cbox.pack_start(Gtk.Label(label="Criar evento"), False, False, 0)
        create.add(cbox)
        create.connect("clicked", lambda *_a: window.new_event())
        self.pack_start(create, False, False, 0)

        self.mini = MiniCalendar(ctrl)
        self.pack_start(self.mini, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 2)

        self.pack_start(Gtk.Separator(), False, False, 2)

        self.connect_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.push_btn = Gtk.Button.new_with_label("Enviar locais ao Google")
        self.push_btn.connect("clicked", lambda *_a: window.push_local_events())
        self.connect_box.pack_start(self.push_btn, False, False, 0)
        self.pack_start(self.connect_box, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 2)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scroll.add(self.list)
        self.pack_start(scroll, True, True, 0)

        legend = Gtk.Label(xalign=0.0)
        legend.set_line_wrap(True)
        legend.set_markup(
            "<small><b>Legenda</b>\n"
            "<span foreground='%s'>\u25cf</span> local   "
            "<span foreground='%s'>\u25cf</span> Google   "
            "<span foreground='%s'>\u25cf</span> local sincronizado</small>"
            % (rgb_to_hex(LOCAL_COLOR), "#4285f4", rgb_to_hex(mix(LOCAL_COLOR, (1, 1, 1), 0.3))))
        self.pack_start(legend, False, False, 0)

        self.status = Gtk.Label(xalign=0.0)
        self.status.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.pack_start(self.status, False, False, 0)

        self._signature = None
        self._building = False
        self.refresh()

    def refresh(self):
        self.mini.refresh()
        auth = self.ctrl.plugin.authenticated
        self.push_btn.set_visible(auth)
        self.connect_box.set_visible(auth)
        n_unsync = self.ctrl.unsynced_local_count()
        if auth:
            self.push_btn.set_sensitive(n_unsync > 0 and not self.ctrl.pushing)
            if n_unsync:
                self.push_btn.set_label("Enviar %d local(is) ao Google" % n_unsync)
            else:
                self.push_btn.set_label("Enviar locais ao Google")
        if auth:
            self.status.set_markup(
                "<small>Google: %s\nsincronizado %s</small>"
                % (GLib.markup_escape_text(self.ctrl.plugin.email or "conectado"),
                   fmt_relogio(self.ctrl.last_sync)))
        else:
            self.status.set_markup("<small>Modo local — sem Google conectado</small>")

        local_cals = [c for c in self.ctrl.calendars if is_local_cal(c["id"])]
        google_cals = [c for c in self.ctrl.calendars if not is_local_cal(c["id"])]
        signature = ("L", local_cals, "G", google_cals, auth,
                     sorted(self.ctrl.hidden), n_unsync)
        if signature == self._signature:
            return
        self._signature = signature
        self._building = True
        for child in self.list.get_children():
            self.list.remove(child)

        def add_section(title):
            lbl = Gtk.Label(xalign=0.0)
            lbl.set_markup("<b><small>%s</small></b>" % title)
            self.list.pack_start(lbl, False, False, 4)

        def add_cal(cal):
            check = Gtk.CheckButton()
            check.set_active(cal["id"] not in self.ctrl.hidden)
            label = Gtk.Label(xalign=0.0)
            label.set_markup('<span foreground="%s">\u25cf</span> %s'
                             % (rgb_to_hex(cal["rgb"]),
                                GLib.markup_escape_text(cal["summary"])))
            label.set_ellipsize(Pango.EllipsizeMode.END)
            check.add(label)
            check.connect("toggled", self._toggled, cal["id"])
            self.list.pack_start(check, False, False, 0)

        add_section("AGENDA LOCAL")
        for cal in local_cals:
            add_cal(cal)
        if auth:
            add_section("GOOGLE")
            if google_cals:
                for cal in google_cals:
                    add_cal(cal)
            else:
                wait = Gtk.Label(xalign=0.0)
                wait.set_markup("<small>Sincronizando agendas...</small>")
                self.list.pack_start(wait, False, False, 4)
        self.list.show_all()
        self._building = False

    def _toggled(self, check, cal_id):
        if not self._building:
            self.ctrl.toggle_calendar(cal_id, check.get_active())


# =============================================================================
# VISUALIZACAO DIA / SEMANA
# =============================================================================
class TimeGridView(Gtk.Box):
    GUTTER = 58.0

    def __init__(self, ctrl, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.ctrl = ctrl
        self.window = window
        self.hour_h = float(ctrl.settings.get("hour_height", 46))
        self._lanes = []
        self._nlanes = 0
        self._head_hits = []
        self._grid_hits = []
        self._head_h = 74
        self._scrolled = False

        self.head = Gtk.DrawingArea()
        self.head.set_size_request(-1, self._head_h)
        self.head.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.head.connect("draw", self._draw_head)
        self.head.connect("button-press-event", self._click_head)
        self.pack_start(self.head, False, False, 0)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.grid = Gtk.DrawingArea()
        self.grid.set_size_request(-1, int(24 * self.hour_h))
        self.grid.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.grid.connect("draw", self._draw_grid)
        self.grid.connect("button-press-event", self._click_grid)
        self.scroll.add(self.grid)
        self.pack_start(self.scroll, True, True, 0)

        GLib.timeout_add_seconds(60, self._tick)

    def _tick(self):
        self.grid.queue_draw()
        return True

    def refresh(self):
        days = self.ctrl.visible_days()
        segments = []
        for ev in self.ctrl.events_visible():
            if not ev.multiday:
                continue
            first = last = None
            for idx, day in enumerate(days):
                if ev.spans(day):
                    if first is None:
                        first = idx
                    last = idx
            if first is not None:
                segments.append((first, last, ev))
        self._lanes, self._nlanes = pack_lanes(segments)
        head_h = int(52 + max(1, self._nlanes) * 20 + 6)
        if head_h != self._head_h:
            self._head_h = head_h
            self.head.set_size_request(-1, head_h)
        self.grid.set_size_request(-1, int(24 * self.hour_h))
        self.head.queue_draw()
        self.grid.queue_draw()
        if not self._scrolled:
            self._scrolled = True
            GLib.idle_add(self._scroll_to_now)

    def _scroll_to_now(self):
        adj = self.scroll.get_vadjustment()
        target = max(0, (datetime.datetime.now().hour - 2) * self.hour_h)
        adj.set_value(min(target, max(0, adj.get_upper() - adj.get_page_size())))
        return False

    def _cols(self, width):
        days = self.ctrl.visible_days()
        return days, max(40.0, (width - self.GUTTER) / len(days))

    def _draw_head(self, widget, cr):
        pal = Palette(widget)
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        days, colw = self._cols(width)
        today = date.today()
        self._head_hits = []

        cr.set_source_rgb(*pal.base)
        cr.paint()
        for idx, day in enumerate(days):
            x = self.GUTTER + idx * colw
            if day.weekday() >= 5:
                cr.set_source_rgb(*pal.alt)
                cr.rectangle(x, 0, colw, height)
                cr.fill()
            text(cr, x, 6, DIAS_ABR[day.weekday()], size=10.0,
                 color=pal.accent if day == today else pal.muted,
                 width=colw, align="center", bold=day == today)
            cx, cy = x + colw / 2.0, 36.0
            color = pal.fg
            if day == today:
                cr.set_source_rgb(*pal.accent)
                cr.arc(cx, cy, 15, 0, 6.2832)
                cr.fill()
                color = readable_on(pal.accent)
            text(cr, x, cy - 11, str(day.day), size=15.0, bold=True, color=color,
                 width=colw, align="center")
            self._head_hits.append((x, 0, colw, 52, "day", day))

        for ev, first, last, lane in self._lanes:
            x = self.GUTTER + first * colw + 2
            w = (last - first + 1) * colw - 4
            y = 54.0 + lane * 20
            rrect(cr, x, y, w, 17, 4)
            paint_event_rect(cr, x, y, w, 17, ev, 4)
            text(cr, x + 6, y, ev.summary, size=10.0, color=readable_on(ev.color),
                 width=w - 10, height=17)
            self._head_hits.append((x, y, w, 17, "event", ev))

        cr.set_source_rgb(*pal.grid)
        cr.set_line_width(1.0)
        cr.move_to(0, height - 0.5)
        cr.line_to(width, height - 0.5)
        cr.stroke()
        return False

    def _click_head(self, _w, event):
        for x, y, w, h, kind, payload in reversed(self._head_hits):
            if x <= event.x <= x + w and y <= event.y <= y + h:
                if kind == "event":
                    self.window.open_event(payload)
                elif event.type == Gdk.EventType._2BUTTON_PRESS:
                    self.window.new_event(day=payload, all_day=True)
                else:
                    self.ctrl.go_to(payload, "day")
                return True
        return True

    def _draw_grid(self, widget, cr):
        pal = Palette(widget)
        width = widget.get_allocated_width()
        days, colw = self._cols(width)
        total_h = 24 * self.hour_h
        today = date.today()
        self._grid_hits = []

        cr.set_source_rgb(*pal.base)
        cr.paint()
        for idx, day in enumerate(days):
            if day.weekday() >= 5:
                cr.set_source_rgb(*pal.alt)
                cr.rectangle(self.GUTTER + idx * colw, 0, colw, total_h)
                cr.fill()

        cr.set_line_width(1.0)
        for hour in range(25):
            y = hour * self.hour_h
            cr.set_source_rgb(*pal.grid_soft)
            cr.move_to(self.GUTTER, y + 0.5)
            cr.line_to(width, y + 0.5)
            cr.stroke()
            if 0 < hour < 24:
                text(cr, 0, y - 7, "%02d:00" % hour, size=9.5, color=pal.muted,
                     width=self.GUTTER - 8, align="right")
        for idx in range(len(days) + 1):
            x = self.GUTTER + idx * colw
            cr.set_source_rgb(*pal.grid_soft)
            cr.move_to(x + 0.5, 0)
            cr.line_to(x + 0.5, total_h)
            cr.stroke()

        for idx, day in enumerate(days):
            x0 = self.GUTTER + idx * colw
            timed = [e for e in self.ctrl.events_visible()
                     if not e.multiday and e.spans(day)]
            for ev, col, ncols, m0, m1 in pack_columns(timed, day):
                slot_w = (colw - 6) / float(ncols)
                x = x0 + 3 + col * slot_w
                w = slot_w - 2
                y = m0 / 60.0 * self.hour_h
                h = max(18.0, (m1 - m0) / 60.0 * self.hour_h - 2)
                rrect(cr, x, y, w, h, 4)
                paint_event_rect(cr, x, y, w, h, ev, 4)
                fg = readable_on(ev.color)
                text(cr, x + 7, y + 2, ev.summary, size=10.0, bold=True, color=fg,
                     width=w - 10)
                if h > 32:
                    text(cr, x + 7, y + 16, ev.start.strftime("%H:%M"), size=9.0,
                         color=fg, width=w - 10, alpha=0.9)
                self._grid_hits.append((x, y, w, h, ev))

            if day == today:
                now = datetime.datetime.now()
                y = (now.hour * 60 + now.minute) / 60.0 * self.hour_h
                cr.set_source_rgb(*pal.now)
                cr.set_line_width(2.0)
                cr.move_to(x0, y)
                cr.line_to(x0 + colw, y)
                cr.stroke()
                cr.arc(x0 + 4, y, 4, 0, 6.2832)
                cr.fill()
        return False

    def _click_grid(self, _w, event):
        for x, y, w, h, ev in reversed(self._grid_hits):
            if x <= event.x <= x + w and y <= event.y <= y + h:
                self.window.open_event(ev)
                return True
        if event.x < self.GUTTER:
            return True
        days, colw = self._cols(self.grid.get_allocated_width())
        idx = int((event.x - self.GUTTER) / colw)
        if not 0 <= idx < len(days):
            return True
        minute = max(0, min(1439, int(event.y / self.hour_h * 60)))
        minute -= minute % 15
        self.ctrl.selected = days[idx]
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.window.new_event(day=days[idx], start_minute=minute)
        return True


# =============================================================================
# VISUALIZACAO MES
# =============================================================================
class MonthView(Gtk.DrawingArea):
    HEAD_H = 26.0
    CHIP_H = 18.0

    def __init__(self, ctrl, window):
        super().__init__()
        self.ctrl = ctrl
        self.window = window
        self._hits = []
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._click)

    def refresh(self):
        self.queue_draw()

    def _geometry(self):
        return (float(self.get_allocated_width()) / 7.0,
                (float(self.get_allocated_height()) - self.HEAD_H) / 6.0)

    def _draw(self, widget, cr):
        pal = Palette(widget)
        cw, ch = self._geometry()
        cells = self.ctrl.month_grid()
        today = date.today()
        month = self.ctrl.anchor.month
        visible = self.ctrl.events_visible()
        self._hits = []

        cr.set_source_rgb(*pal.base)
        cr.paint()
        for idx, weekday in enumerate(self.ctrl.weekday_order()):
            text(cr, idx * cw, 0, DIAS_ABR[weekday], size=10.0, color=pal.muted,
                 width=cw, height=self.HEAD_H, align="center")

        cr.set_line_width(1.0)
        for i, day in enumerate(cells):
            x, y = (i % 7) * cw, self.HEAD_H + (i // 7) * ch
            in_month = day.month == month
            if not in_month:
                cr.set_source_rgb(*pal.alt)
                cr.rectangle(x, y, cw, ch)
                cr.fill()
            cr.set_source_rgb(*pal.grid_soft)
            cr.rectangle(x + 0.5, y + 0.5, cw, ch)
            cr.stroke()

            num_color = pal.fg if in_month else pal.muted
            if day == today:
                cr.set_source_rgb(*pal.accent)
                cr.arc(x + cw / 2.0, y + 13, 11, 0, 6.2832)
                cr.fill()
                num_color = readable_on(pal.accent)
            text(cr, x, y + 3, str(day.day), size=11.0, bold=day == today,
                 color=num_color, width=cw, align="center")

            events = sorted([e for e in visible if e.spans(day)],
                            key=lambda e: e.sort_key())
            top = y + 26
            room = int(max(0, (ch - 28) / self.CHIP_H))
            for pos, ev in enumerate(events):
                if pos >= room:
                    rest = len(events) - pos
                    text(cr, x + 6, top + pos * self.CHIP_H,
                         "+%d evento%s" % (rest, "s" if rest > 1 else ""),
                         size=9.5, color=pal.muted, width=cw - 12)
                    self._hits.append((x + 4, top + pos * self.CHIP_H, cw - 8,
                                       self.CHIP_H, "more", day))
                    break
                cy = top + pos * self.CHIP_H
                if ev.multiday:
                    paint_event_rect(cr, x + 3, cy, cw - 6, self.CHIP_H - 3, ev, 3)
                    text(cr, x + 8, cy, ev.summary, size=9.5,
                         color=readable_on(ev.color), width=cw - 16,
                         height=self.CHIP_H - 3)
                else:
                    cr.set_source_rgb(*ev.color)
                    if ev.source == "local" and not ev.synced:
                        cr.set_dash([2.0, 2.0], 0)
                    cr.arc(x + 9, cy + 7, 3.5, 0, 6.2832)
                    cr.fill()
                    cr.set_dash([], 0)
                    text(cr, x + 16, cy,
                         "%s  %s" % (ev.start.strftime("%H:%M"), ev.summary),
                         size=9.5, color=pal.fg, width=cw - 22, height=self.CHIP_H - 3)
                self._hits.append((x + 3, cy, cw - 6, self.CHIP_H - 3, "event", ev))
        return False

    def _click(self, _w, event):
        for x, y, w, h, kind, payload in self._hits:
            if x <= event.x <= x + w and y <= event.y <= y + h:
                if kind == "event":
                    self.window.open_event(payload)
                else:
                    self.ctrl.go_to(payload, "day")
                return True
        cw, ch = self._geometry()
        if event.y < self.HEAD_H:
            return True
        col, row = int(event.x / cw), int((event.y - self.HEAD_H) / ch)
        if 0 <= col < 7 and 0 <= row < 6:
            day = self.ctrl.month_grid()[row * 7 + col]
            self.ctrl.selected = day
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.window.new_event(day=day, all_day=True)
            else:
                self.queue_draw()
        return True


# =============================================================================
# CONECTAR GOOGLE (dialog opcional)
# =============================================================================
class ConnectGoogleDialog(Gtk.Dialog):
    def __init__(self, parent_win):
        super().__init__(title="Conectar Google Agenda", transient_for=parent_win,
                         modal=True)
        self.parent_win = parent_win
        self.set_default_size(520, -1)
        self.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        self.login_btn = self.add_button("Conectar", Gtk.ResponseType.OK)
        self.login_btn.get_style_context().add_class("suggested-action")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        self.get_content_area().pack_start(box, True, True, 0)

        icon = Gtk.Image.new_from_icon_name(APP_ID, Gtk.IconSize.DIALOG)
        icon.set_pixel_size(72)
        box.pack_start(icon, False, False, 0)

        title = Gtk.Label()
        title.set_markup("<span size='large' weight='bold'>Google Agenda</span>")
        box.pack_start(title, False, False, 0)

        sub = Gtk.Label()
        sub.set_line_wrap(True)
        sub.set_markup("<small>Veja compromissos da nuvem e envie eventos locais "
                       "para o Google quando quiser.</small>")
        box.pack_start(sub, False, False, 0)

        self.status = Gtk.Label()
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(56)
        self.status.set_justify(Gtk.Justification.CENTER)
        box.pack_start(self.status, False, False, 6)

        self.spinner = Gtk.Spinner()
        box.pack_start(self.spinner, False, False, 0)

        self.pick_btn = Gtk.Button.new_with_label("Selecionar credentials.json...")
        self.pick_btn.connect("clicked",
                              lambda *_a: self.parent_win.pick_credentials(self))
        box.pack_start(self.pick_btn, False, False, 0)

        expander = Gtk.Expander(label="Configuracao avancada (credentials.json)")
        help_text = Gtk.Label(xalign=0.0)
        help_text.set_markup(
            "<small>"
            "1. Acesse <b>console.cloud.google.com</b>\n"
            "2. Ative a <b>Google Calendar API</b>\n"
            "3. OAuth externo, modo Teste, seu e-mail em Usuarios de teste\n"
            "4. Credencial OAuth tipo <b>App para desktop</b>\n"
            "5. Baixe o JSON e selecione acima"
            "</small>")
        help_text.set_line_wrap(True)
        help_text.set_margin_top(6)
        expander.add(help_text)
        box.pack_start(expander, False, False, 0)
        self.refresh()

    def refresh(self):
        kind = self.parent_win.plugin.credentials_kind()
        if kind == "installed":
            self.status.set_markup(
                "<small>Credenciais em\n<tt>%s</tt></small>"
                % GLib.markup_escape_text(self.parent_win.plugin.credentials_file))
            self.login_btn.set_sensitive(True)
        elif kind == "web":
            self.status.set_markup(
                "<b>credentials.json incompativel</b>\n"
                "<small>Use cliente OAuth <b>App para desktop</b>.</small>")
            self.login_btn.set_sensitive(False)
        elif kind == "invalido":
            self.status.set_markup("<b>Arquivo invalido.</b>")
            self.login_btn.set_sensitive(False)
        else:
            self.status.set_markup(
                "<small>Nenhum credentials.json. Selecione o arquivo ou "
                "instale em /etc/agenda-tarsila/.</small>")
            self.login_btn.set_sensitive(False)

    def set_busy(self, busy, message=None):
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
        ready = self.parent_win.plugin.credentials_kind() == "installed"
        self.login_btn.set_sensitive(not busy and ready)
        self.pick_btn.set_sensitive(not busy)
        if message:
            self.status.set_markup("<small>%s</small>"
                                   % GLib.markup_escape_text(message))


# =============================================================================
# JANELA PRINCIPAL
# =============================================================================
class MainWindow(Gtk.Window):
    def __init__(self, plugin):
        super().__init__(title=APP_NAME)
        self.plugin = plugin
        self.ctrl = Controller(plugin)
        self.ctrl.connect(self.on_state_changed)
        self._autosync = None
        self.set_default_size(1180, 760)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_name(APP_ID)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key)

        # A HeaderBar NAO e mais a barra de titulo da janela.
        #
        # Como titlebar, ela era desenhada pelo proprio programa (decoracao do
        # lado do cliente): botoes a esquerda, titulo centralizado, cor
        # propria -- diferente de todos os outros aplicativos do Tarsila, que
        # usam a barra do Openbox. A Agenda destoava.
        #
        # Ela continua existindo, com os mesmos botoes (menu lateral, Hoje,
        # navegacao), mas agora como barra de ferramentas DENTRO da janela. O
        # Openbox desenha o titulo por cima, igual ao resto.
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)   # quem fecha e o Openbox
        self.set_title(APP_NAME)

        self.sidebar_btn = Gtk.ToggleButton()
        self.sidebar_btn.add(Gtk.Image.new_from_icon_name("open-menu-symbolic",
                                                          Gtk.IconSize.BUTTON))
        self.sidebar_btn.set_active(True)
        self.sidebar_btn.connect("toggled", self.on_sidebar_toggled)
        self.header.pack_start(self.sidebar_btn)

        self.today_btn = Gtk.Button.new_with_label("Hoje")
        self.today_btn.connect("clicked", lambda *_a: self.ctrl.go_today())
        self.header.pack_start(self.today_btn)

        self.nav_box = Gtk.Box()
        self.nav_box.get_style_context().add_class("linked")
        for icon, delta in (("pan-start-symbolic", -1), ("pan-end-symbolic", 1)):
            btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            btn.connect("clicked", lambda _b, d=delta: self.ctrl.step(d))
            self.nav_box.pack_start(btn, False, False, 0)
        self.header.pack_start(self.nav_box)

        self.title_label = Gtk.Label()
        self.header.pack_start(self.title_label)

        self.source_chip = Gtk.Label()
        self.source_chip.get_style_context().add_class("dim-label")
        self.header.pack_start(self.source_chip)

        self.spinner = Gtk.Spinner()
        self.header.pack_end(self.spinner)

        self.view_combo = Gtk.ComboBoxText()
        for label in ("Dia", "Semana", "Mes"):
            self.view_combo.append_text(label)
        self.view_combo.set_active({"day": 0, "week": 1, "month": 2}[self.ctrl.view])
        self.view_combo.connect("changed", self.on_view_combo)
        self.header.pack_end(self.view_combo)

        self.refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic",
                                                         Gtk.IconSize.BUTTON)
        self.refresh_btn.set_tooltip_text("Baixar novidades do Google")
        self.refresh_btn.connect("clicked", lambda *_a: self.ctrl.sync())
        self.header.pack_end(self.refresh_btn)

        # [G Faça login…] imediatamente à esquerda da engrenagem (ferramenta)
        self.tool_trail = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.google_login_btn = make_google_login_button(self.open_connect_google)
        self.google_login_btn.set_no_show_all(True)
        self.tool_trail.pack_start(self.google_login_btn, False, False, 0)

        self.menu_btn = Gtk.MenuButton()
        self.menu_btn.add(Gtk.Image.new_from_icon_name("preferences-system-symbolic",
                                                       Gtk.IconSize.BUTTON))
        self.menu_btn.set_popover(self.build_menu())
        self.tool_trail.pack_start(self.menu_btn, False, False, 0)
        self.header.pack_end(self.tool_trail)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.sidebar_revealer = Gtk.Revealer()
        self.sidebar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.sidebar = Sidebar(self.ctrl, self)
        self.sidebar_revealer.add(self.sidebar)
        self.sidebar_revealer.set_reveal_child(True)
        body.pack_start(self.sidebar_revealer, False, False, 0)
        body.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL),
                        False, False, 0)

        self.content = Gtk.Stack()
        self.timegrid = TimeGridView(self.ctrl, self)
        self.monthview = MonthView(self.ctrl, self)
        self.content.add_named(self.timegrid, "time")
        self.content.add_named(self.monthview, "month")
        body.pack_start(self.content, True, True, 0)

        self.infobar = Gtk.InfoBar()
        self.infobar.set_message_type(Gtk.MessageType.WARNING)
        self.infobar.set_show_close_button(True)
        self.infobar.connect("response", lambda bar, _r: bar.hide())
        self.info_label = Gtk.Label(xalign=0.0)
        self.info_label.set_line_wrap(True)
        self.infobar.get_content_area().add(self.info_label)
        self.infobar.set_no_show_all(True)

        app_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        app_page.pack_start(self.infobar, False, False, 0)
        app_page.pack_start(body, True, True, 0)

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        raiz.pack_start(self.header, False, False, 0)
        raiz.pack_start(app_page, True, True, 0)
        self.add(raiz)

    # -------------------------------------------------------------------- menu
    def build_menu(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=10)

        lbl = Gtk.Label(xalign=0.0)
        lbl.set_markup("<b><small>A SEMANA COMECA EM</small></b>")
        box.pack_start(lbl, False, False, 0)
        sunday = Gtk.RadioButton.new_with_label_from_widget(None, "Domingo")
        monday = Gtk.RadioButton.new_with_label_from_widget(sunday, "Segunda-feira")
        (sunday if self.ctrl.week_start == 6 else monday).set_active(True)
        sunday.connect("toggled", lambda b: b.get_active() and self.ctrl.set_week_start(6))
        monday.connect("toggled", lambda b: b.get_active() and self.ctrl.set_week_start(0))
        box.pack_start(sunday, False, False, 0)
        box.pack_start(monday, False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 4)
        menu_items = [
            ("Enviar eventos locais ao Google", self.push_local_events),
        ]
        if self.plugin.authenticated:
            menu_items.extend([
                ("Baixar do Google agora", lambda: self.ctrl.sync()),
                ("Ressincronizar tudo (Google)", lambda: self.ctrl.sync(full=True)),
                ("Abrir Google Agenda no navegador",
                 lambda: webbrowser.open("https://calendar.google.com")),
                ("Desconectar Google", self.logout),
            ])
        else:
            menu_items.append(("Conectar Google Agenda", self.open_connect_google))
        menu_items.append(("Sobre", self.show_about))
        for label, action in menu_items:
            btn = Gtk.Button.new_with_label(label)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", lambda _b, fn=action: fn())
            box.pack_start(btn, False, False, 0)

        pop.add(box)
        box.show_all()
        return pop

    def show_about(self):
        dlg = Gtk.AboutDialog(transient_for=self, modal=True)
        dlg.set_program_name(APP_NAME)
        dlg.set_version(APP_VERSION)
        dlg.set_comments("Calendario local GTK3 com Google Agenda opcional.\n"
                         "Sem dependencias externas; sync incremental.\n\n"
                         "Google icons created by Magnific - Flaticon\n"
                         "https://www.flaticon.com/free-icons/google")
        dlg.set_logo_icon_name(APP_ID)
        dlg.run()
        dlg.destroy()

    # ------------------------------------------------------------------ estado
    def post_show(self):
        self.enter_app()

        def work():
            ok = self.plugin.silent_login()
            GLib.idle_add(finish, ok)

        def finish(ok):
            if ok:
                self.ctrl.store.ensure_account(self.plugin.email)
                self.ctrl.calendars = self.ctrl.store.load_calendars()
                self.ctrl.sync()
            self.on_state_changed()
            return False

        threading.Thread(target=work, daemon=True).start()

    def enter_app(self):
        self.ctrl.store.ensure_local_calendar()
        self.ctrl.calendars = self.ctrl.store.load_calendars()
        self.ctrl.last_sync = self.ctrl.store.get_meta("last_sync")
        self.ctrl.load_window()
        self.sidebar.refresh()
        self.on_state_changed()
        if self._autosync is None:
            self._autosync = GLib.timeout_add_seconds(AUTOSYNC_SECONDS, self._tick_sync)

    def _tick_sync(self):
        if self.plugin.authenticated and self.is_active():
            self.ctrl.sync()
        return True

    def on_state_changed(self):
        self.title_label.set_markup(
            "<b>%s</b>" % GLib.markup_escape_text(self.ctrl.title_text().capitalize()))
        if self.plugin.authenticated:
            chip = "Local + Google · %s" % (self.plugin.email or "conectado")
        else:
            chip = "Local"
        self.source_chip.set_markup("<small><i>%s</i></small>"
                                    % GLib.markup_escape_text(chip))
        if self.plugin.authenticated:
            self.google_login_btn.hide()
        else:
            # set_no_show_all(True) foi posto no botao para ele NAO aparecer
            # no show_all() da janela (senao piscaria antes de sabermos se a
            # conta ja esta conectada). Mas esse mesmo sinalizador faz o
            # show_all() do PROPRIO botao nao surtir efeito -- o GTK sai
            # cedo da funcao. Resultado: o botao "Faca login na sua conta
            # Google" nunca aparecia, e nao havia erro nenhum para indicar
            # isso. Verificado no GTK 3: com no_show_all ligado, show_all()
            # deixa visible=False; so show() muda. Desligamos o sinalizador
            # aqui, quando ja e hora de mostrar de verdade.
            self.google_login_btn.set_no_show_all(False)
            self.google_login_btn.show_all()
        self.refresh_btn.set_sensitive(self.plugin.authenticated)
        if self.ctrl.syncing or self.ctrl.pushing:
            self.spinner.start()
            self.spinner.show()
        else:
            self.spinner.stop()
            self.spinner.hide()
        if self.ctrl.error:
            self.info_label.set_text(self.ctrl.error)
            self.infobar.show_all()
        else:
            self.infobar.hide()
        if self.ctrl.view == "month":
            self.content.set_visible_child_name("month")
            self.monthview.refresh()
        else:
            self.content.set_visible_child_name("time")
            self.timegrid.refresh()
        self.sidebar.refresh()
        index = {"day": 0, "week": 1, "month": 2}[self.ctrl.view]
        if self.view_combo.get_active() != index:
            self.view_combo.handler_block_by_func(self.on_view_combo)
            self.view_combo.set_active(index)
            self.view_combo.handler_unblock_by_func(self.on_view_combo)

    # ------------------------------------------------------------------- acoes
    def on_sidebar_toggled(self, button):
        self.sidebar_revealer.set_reveal_child(button.get_active())

    def on_view_combo(self, combo):
        self.ctrl.set_view({0: "day", 1: "week", 2: "month"}[combo.get_active()])

    def new_event(self, day=None, start_minute=None, all_day=False):
        if not self.ctrl.writable_calendars():
            error_dialog(self, "Nenhuma agenda editavel",
                         "Nao ha agenda disponivel para criar eventos.")
            return
        editor = EventEditor(self, self.ctrl, day=day or self.ctrl.selected,
                             start_minute=start_minute, all_day=all_day)
        editor.run_and_save()
        editor.destroy()

    def open_connect_google(self):
        dlg = ConnectGoogleDialog(self)
        dlg.show_all()
        resp = dlg.run()
        dlg.destroy()
        if resp != Gtk.ResponseType.OK:
            return
        wait = Gtk.MessageDialog(transient_for=self, modal=True,
                                 message_type=Gtk.MessageType.INFO,
                                 buttons=Gtk.ButtonsType.CANCEL,
                                 text="Conectando ao Google Agenda...")
        wait.format_secondary_text("Complete a autorizacao no navegador.")
        wait.show_all()

        def work():
            err = None
            try:
                self.plugin.interactive_login()
            except Exception as exc:
                err = api_error_text(exc)
            GLib.idle_add(finish, err)

        def finish(err):
            wait.destroy()
            if err:
                error_dialog(self, "Nao foi possivel conectar", err)
            else:
                self.ctrl.store.ensure_account(self.plugin.email)
                self.ctrl.calendars = self.ctrl.store.load_calendars()
                self.ctrl.sync()
                self.on_state_changed()
            return False

        threading.Thread(target=work, daemon=True).start()

    def push_local_events(self):
        if not self.plugin.authenticated:
            self.open_connect_google()
            return
        n = self.ctrl.unsynced_local_count()
        if n == 0:
            info = Gtk.MessageDialog(transient_for=self, modal=True,
                                     message_type=Gtk.MessageType.INFO,
                                     buttons=Gtk.ButtonsType.OK,
                                     text="Nenhum evento local pendente.")
            info.format_secondary_text(
                "Todos os eventos locais visiveis ja foram enviados ao Google.")
            info.run()
            info.destroy()
            return

        def done(ok, msg):
            typ = Gtk.MessageType.INFO if ok else Gtk.MessageType.WARNING
            dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                    message_type=typ, buttons=Gtk.ButtonsType.OK,
                                    text="Sincronizacao local → Google")
            dlg.format_secondary_text(msg)
            dlg.run()
            dlg.destroy()
            self.on_state_changed()

        self.ctrl.push_local_to_google(on_done=done)

    def open_event(self, ev):
        dlg = EventDetails(self, self.ctrl, ev)
        dlg.run_actions()
        dlg.destroy()

    def pick_credentials(self, dialog=None):
        chooser = Gtk.FileChooserDialog(title="Selecione o credentials.json",
                                        transient_for=self,
                                        action=Gtk.FileChooserAction.OPEN)
        chooser.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                            "Abrir", Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name("JSON")
        flt.add_pattern("*.json")
        chooser.add_filter(flt)
        downloads = os.path.expanduser("~/Downloads")
        chooser.set_current_folder(downloads if os.path.isdir(downloads)
                                   else os.path.expanduser("~"))
        response = chooser.run()
        path = chooser.get_filename()
        chooser.destroy()
        if response != Gtk.ResponseType.OK or not path:
            return
        try:
            self.plugin.install_credentials(path)
        except Exception as exc:
            error_dialog(self, "Arquivo invalido", str(exc))
            if dialog:
                dialog.refresh()
            return
        if dialog:
            dialog.refresh()

    def logout(self):
        self.plugin.logout()
        self.ctrl.hard_reset()
        self.on_state_changed()

    # ----------------------------------------------------------------- teclado
    def on_key(self, _w, event):
        if isinstance(self.get_focus(), (Gtk.Entry, Gtk.TextView)):
            return False
        name = (Gdk.keyval_name(event.keyval) or "").lower()
        if name in ("d", "1"):
            self.ctrl.set_view("day")
        elif name in ("w", "s", "2"):
            self.ctrl.set_view("week")
        elif name in ("m", "3"):
            self.ctrl.set_view("month")
        elif name == "t":
            self.ctrl.go_today()
        elif name in ("left", "k", "page_up"):
            self.ctrl.step(-1)
        elif name in ("right", "j", "page_down"):
            self.ctrl.step(1)
        elif name in ("n", "c"):
            self.new_event()
        elif name in ("r", "f5"):
            self.ctrl.sync()
        else:
            return False
        return True


# =============================================================================
# CSS / DIAGNOSTICO / MAIN
# =============================================================================
CSS = b"""
* {
  font-family: Roboto, "Noto Sans", sans-serif;
}
window, dialog, messagedialog, label, button, entry, textview,
combobox, menuitem, treeview, notebook, headerbar, popover {
  font-family: Roboto, "Noto Sans", sans-serif;
}
.at-sidebar { background-color: @theme_bg_color; }
headerbar label { margin-left: 6px; margin-right: 6px; }
headerbar button.at-google-login {
  min-width: 260px;
  padding-left: 10px;
  padding-right: 14px;
  padding-top: 4px;
  padding-bottom: 4px;
}
headerbar button.at-google-login label {
  font-weight: bold;
  opacity: 1;
}
headerbar button.at-google-login image {
  margin-right: 6px;
  opacity: 1;
}
"""


def load_css():
    try:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    except Exception:
        pass


def diagnostico():
    print("%s %s" % (APP_NAME, APP_VERSION))
    print("interpretador : %s" % sys.executable)
    print("python        : %s" % sys.version.split()[0])
    print("dependencias  : nenhuma (biblioteca padrao)")
    print("GTK (gi)      : OK")
    print("CA store      : %s" % (ssl.get_default_verify_paths().openssl_cafile
                                  or "padrao do sistema"))
    plugin = GooglePlugin()
    print("credentials   : %s [%s]" % (plugin.credentials_file or "(nenhum)",
                                       plugin.credentials_kind()))
    print("token         : %s" % ("presente" if os.path.isfile(TOKEN_FILE)
                                  else "ausente"))
    try:
        store = Store()
        print("cache         : %s" % CACHE_DB)
        print("eventos       : %d" % store.count())
        print("conta Google  : %s" % (store.get_meta("google_account") or "-"))
        print("ultimo sync   : %s" % fmt_relogio(store.get_meta("last_sync")))
        cals = store.load_calendars()
        if cals:
            print("agendas       :")
            for cal in cals:
                st = store.sync_state(cal["id"])
                print("  %-40s syncToken=%s" % (cal["summary"][:40],
                                                "sim" if st and st["token"] else "nao"))
    except Exception as exc:
        print("cache         : erro (%s)" % exc)


def main():
    args = sys.argv[1:]
    if "--diagnostico" in args or "--diagnose" in args:
        diagnostico()
        return
    if "--version" in args or "-v" in args:
        print("%s %s" % (APP_NAME, APP_VERSION))
        return
    if "--reset-cache" in args:
        Store().wipe()
        print("Cache local apagado.")
        return
    GLib.set_prgname(APP_ID)
    GLib.set_application_name(APP_NAME)
    Gtk.Window.set_default_icon_name(APP_ID)
    load_css()
    window = MainWindow(GooglePlugin())
    window.show_all()
    window.post_show()
    Gtk.main()


if __name__ == "__main__":
    main()
