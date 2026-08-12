#!/usr/bin/env python3
# Recorta input da polybar só nos módulos (X Shape) e grava hitboxes para o clamp.
# Recalculado ao subir a barra, mudar systray (via watcher) ou chamar manualmente.

from __future__ import annotations

import configparser
import ctypes
import os
import re
import signal
import subprocess
import sys
from ctypes import c_int, c_short, c_uint, c_ushort, c_void_p
from pathlib import Path

ShapeSet = 0
ShapeInput = 2

FONT_CHAR_W = {10: 6.0, 11: 6.5, 12: 7.2, 13: 7.8, 14: 8.4}
ICON_W = {11: 16, 12: 17, 13: 18, 14: 19}


class XRectangle(ctypes.Structure):
    _fields_ = [
        ("x", c_short),
        ("y", c_short),
        ("width", c_ushort),
        ("height", c_ushort),
    ]


def run(cmd: list[str], timeout: float = 2.0) -> str:
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XAUTHORITY", str(Path.home() / ".Xauthority"))
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout, env=env, text=True)
        return out.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def strip_tags(text: str) -> str:
    return re.sub(r"%\{[^}]*\}", "", text or "")


def parse_config(gen_ini: Path) -> dict:
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read(gen_ini, encoding="utf-8")
    bar = cp["bar/tarsila"]
    fonts = {}
    for key, val in bar.items():
        if key.startswith("font-"):
            m = re.search(r"size=(\d+)", val)
            if m:
                fonts[key] = int(m.group(1))
    return {
        "height": int(bar.get("height", "34")),
        "padding_left": int(bar.get("padding-left", "1")),
        "padding_right": int(bar.get("padding-right", "2")),
        "module_margin": int(bar.get("module-margin", "2")),
        "modules_left": [m.strip() for m in bar.get("modules-left", "").split() if m.strip()],
        "modules_right": [m.strip() for m in bar.get("modules-right", "").split() if m.strip()],
        "fonts": fonts,
        "cp": cp,
    }


def screen_width() -> int:
    out = run(["xdotool", "getdisplaygeometry"])
    if out:
        parts = out.split()
        if len(parts) >= 1:
            return int(parts[0])
    out = run(["xrandr", "--query"])
    m = re.search(r"connected (?:primary )?\d+x\d+", out)
    if m:
        m2 = re.search(r"(\d+)x", m.group(0))
        if m2:
            return int(m2.group(1))
    return 1366


def module_script_output(name: str, polybar_dir: Path) -> str:
    script = polybar_dir / f"{name}.sh"
    if name in ("netw",):
        script = polybar_dir / "net.sh"
    if not script.is_file():
        return ""
    # title.sh/buttons.sh sao scripts "tail" (emit(); xprop -spy | while
    # ...): nunca terminam sozinhos. Rodar so pra medir a largura do texto
    # e matar por timeout deixava o "xprop -spy | while" orfao rodando pra
    # sempre -- achado 2026-08-02: centenas de processos acumulados por
    # hora de uso, derrubando a carga da box. start_new_session=True poe o
    # subprocesso (e os filhos do pipe que ele cria) num process group
    # proprio, pra dar pra matar o grupo inteiro no timeout, nao so o
    # processo direto.
    proc = subprocess.Popen(
        ["bash", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=0.8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            out, _ = proc.communicate(timeout=0.5)
        except Exception:
            out = ""
    except OSError:
        return ""
    try:
        return (out or "").splitlines()[0].strip()
    except IndexError:
        return ""


def text_width(text: str, font_size: int) -> int:
    visible = strip_tags(text)
    if not visible:
        return 0
    base = FONT_CHAR_W.get(font_size, 7.0)
    w = int(len(visible) * base + 10)
    return max(w, 12)


def icon_width(font_size: int) -> int:
    return ICON_W.get(font_size, 16) + 10


def systray_width(bar_h: int, cp: configparser.ConfigParser) -> int:
    tray_size_pct = 66
    tray_spacing = 6
    if cp.has_section("module/systray"):
        sec = cp["module/systray"]
        m = re.search(r"tray-size\s*=\s*(\d+)", sec.get("tray-size", "66%"))
        if m:
            tray_size_pct = int(m.group(1))
        m = re.search(r"tray-spacing\s*=\s*(\d+)", sec.get("tray-spacing", "6px"))
        if m:
            tray_spacing = int(m.group(1))
    icon = max(16, int(bar_h * tray_size_pct / 100))
    n = count_tray_icons(bar_h, icon)
    if n <= 0:
        return 0
    return n * icon + max(0, n - 1) * tray_spacing + 8


def count_tray_icons(bar_h: int, icon_size: int) -> int:
    sw = screen_width()
    x_min = int(sw * 0.45)
    # StatusNotifier (se existir)
    out = run(
        [
            "dbus-send",
            "--session",
            "--print-reply",
            "--dest=org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.kde.StatusNotifierWatcher",
            "string:RegisteredStatusNotifierItems",
        ],
        timeout=1.5,
    )
    if out and "array [" in out:
        items = re.findall(r'string "([^"]+)"', out)
        if items:
            return len(items)

    # Legacy / XEmbed: janelas pequenas na faixa da barra (ex. VLC, OBS)
    skip_re = re.compile(
        r"(polybar|Polybar|plank|Plank|openbox|Openbox|tarsila-tela-estados|"
        r"xfce4-panel|xfdesktop|Desktop|devtools)",
        re.I,
    )
    n = 0
    ids = run(["xdotool", "search", "--onlyvisible", "--name", ".*"]).split()
    for wid in ids:
        geom = run(["xdotool", "getwindowgeometry", "--shell", wid])
        if not geom:
            continue
        vals = dict(line.split("=", 1) for line in geom.splitlines() if "=" in line)
        try:
            x, y, w, h = int(vals.get("X", 9999)), int(vals.get("Y", 9999)), int(vals.get("WIDTH", 0)), int(vals.get("HEIGHT", 0))
        except ValueError:
            continue
        if y > bar_h or h > bar_h + 4 or w > bar_h + 8:
            continue
        if x < x_min:
            continue
        cls = run(["xprop", "-id", wid, "WM_CLASS"])
        if skip_re.search(cls):
            continue
        if w >= 8 and h >= 8:
            n += 1
    return n


def module_width(name: str, cfg: dict, polybar_dir: Path) -> int:
    cp = cfg["cp"]
    bar_h = cfg["height"]
    fonts = cfg["fonts"]
    base_font = fonts.get("font-0", 12)
    icon_font = fonts.get("font-2", 11)

    if name == "systray":
        return systray_width(bar_h, cp)

    if name == "limpar":
        return icon_width(fonts.get("font-3", base_font))

    if name in ("netw", "sound", "power"):
        return icon_width(icon_font)

    if name == "date":
        out = module_script_output("date", polybar_dir)
        visible = strip_tags(out)
        if not visible:
            visible = run(["bash", "-lc", "LC_TIME=$(. /etc/default/locale 2>/dev/null; echo ${LC_TIME:-pt_BR.UTF-8}); date '+%H:%M  %d de %B'"])
        return text_width(visible, fonts.get("font-5", 10))

    if name in ("buttons", "title"):
        out = module_script_output(name, polybar_dir)
        w = text_width(out, base_font)
        if name == "buttons" and w > 0:
            return w + 4
        return w

    if cp.has_section(f"module/{name}"):
        sec = cp[f"module/{name}"]
        content = sec.get("content", "")
        if content:
            return text_width(content, base_font)

    return 0


def compute_hitboxes(
    cfg: dict, polybar_dir: Path, bar_w: int
) -> list[tuple[int, int, int, int]]:
    """Retângulos relativos à janela da polybar (para X Shape)."""
    bar_h = cfg["height"]
    margin = cfg["module_margin"]
    pl = cfg["padding_left"]
    pr = cfg["padding_right"]
    boxes: list[tuple[int, int, int, int]] = []

    x = pl
    for mod in cfg["modules_left"]:
        w = module_width(mod, cfg, polybar_dir)
        if w > 0:
            boxes.append((x, 0, w, bar_h))
            x += w + margin
        elif mod:
            x += margin

    x_right = bar_w - pr
    for mod in reversed(cfg["modules_right"]):
        w = module_width(mod, cfg, polybar_dir)
        if w > 0:
            x_right -= w
            boxes.append((x_right, 0, w, bar_h))
            x_right -= margin
        elif mod:
            x_right -= margin

    return boxes


def polybar_window_geom() -> tuple[int | None, int, int]:
    """(window_id, absolute_x, width) da polybar principal."""
    out = run(["xdotool", "search", "--class", "polybar"])
    best = None
    best_area = 0
    best_x = 0
    best_w = screen_width()
    for wid in out.split():
        geom = run(["xdotool", "getwindowgeometry", "--shell", wid])
        if not geom:
            continue
        vals = dict(line.split("=", 1) for line in geom.splitlines() if "=" in line)
        try:
            x = int(vals.get("X", 0))
            w = int(vals.get("WIDTH", 0))
            h = int(vals.get("HEIGHT", 0))
        except ValueError:
            continue
        area = w * h
        if h <= 80 and area > best_area:
            best_area = area
            best = int(wid)
            best_x = x
            best_w = w
    # xwininfo costuma ser mais fiel para Absolute X
    if best is not None:
        info = run(["xwininfo", "-id", str(best)])
        m = re.search(r"Absolute upper-left X:\s*(-?\d+)", info)
        if m:
            best_x = int(m.group(1))
        m = re.search(r"Width:\s*(\d+)", info)
        if m:
            best_w = int(m.group(1))
    return best, best_x, best_w


def apply_input_shape(wid: int, boxes: list[tuple[int, int, int, int]]) -> None:
    libx11 = ctypes.CDLL("libX11.so.6")
    libxext = ctypes.CDLL("libXext.so.6")
    libx11.XOpenDisplay.restype = c_void_p
    libx11.XCloseDisplay.argtypes = [c_void_p]
    libxext.XShapeCombineRectangles.argtypes = [
        c_void_p,
        c_uint,
        c_int,
        c_int,
        c_int,
        ctypes.POINTER(XRectangle),
        c_int,
        c_int,
        c_int,
    ]

    dpy = libx11.XOpenDisplay(None)
    if not dpy:
        return
    try:
        if not boxes:
            libxext.XShapeCombineRectangles(dpy, wid, ShapeInput, 0, 0, None, 0, ShapeSet, 0)
            return
        rects = (XRectangle * len(boxes))()
        for i, (x, y, w, h) in enumerate(boxes):
            rects[i] = XRectangle(x, y, w, h)
        libxext.XShapeCombineRectangles(
            dpy, wid, ShapeInput, 0, 0, rects, len(boxes), ShapeSet, 0
        )
        libx11.XSync(dpy, False)
    finally:
        libx11.XCloseDisplay(dpy)


def write_hitboxes(path: Path, boxes: list[tuple[int, int, int, int]], bar_h: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(f"# bar_height={bar_h}\n")
        for x, y, w, h in boxes:
            f.write(f"{x} {y} {w} {h}\n")
    tmp.replace(path)


def is_maximized() -> bool:
    state = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "tarsila-topbar-state.txt"
    try:
        return "MAX=1" in state.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def main() -> int:
    home = Path.home()
    gen_ini = home / ".config/polybar/config.gen.ini"
    polybar_dir = home / ".config/polybar"
    hitboxes = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "tarsila-polybar-hitboxes.txt"

    if not gen_ini.is_file():
        print("config.gen.ini not found", file=sys.stderr)
        return 1

    cfg = parse_config(gen_ini)
    wid, bar_x, bar_w = polybar_window_geom()
    if bar_w <= 0:
        bar_w = screen_width()

    bar_h = cfg["height"]
    # Maximizado: recorte = largura inteira da barra (altura preservada).
    # Flutuante: só módulos (clique passa nos vazios).
    if is_maximized():
        boxes_rel = [(0, 0, bar_w, bar_h)]
    else:
        boxes_rel = compute_hitboxes(cfg, polybar_dir, bar_w)

    # Clamp usa coordenadas de tela; Shape usa relativas à janela
    boxes_abs = [(x + bar_x, y, w, h) for x, y, w, h in boxes_rel]
    write_hitboxes(hitboxes, boxes_abs, bar_h)

    if wid:
        apply_input_shape(wid, boxes_rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
