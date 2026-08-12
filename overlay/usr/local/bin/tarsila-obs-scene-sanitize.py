#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove fontes V4L2 quebradas da cena OBS quando nao ha /dev/video*.

Evita erro repetido e instabilidade ao abrir propriedades de camera vazia.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

CONFIG = os.path.expanduser("~/.config/obs-studio/basic/scenes")
FLAG = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                      "tarsila-obs-no-camera-notified")


def has_camera():
    return bool(glob.glob("/dev/video*"))


def sanitize_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    v4l2_uuids = set()
    kept = []
    for src in data.get("sources", []):
        sid = src.get("versioned_id") or src.get("id") or ""
        if sid == "v4l2_input":
            uid = src.get("uuid")
            if uid:
                v4l2_uuids.add(uid)
            continue
        kept.append(src)
    if not v4l2_uuids:
        return False
    for src in kept:
        if (src.get("versioned_id") or src.get("id")) != "scene":
            continue
        items = src.get("settings", {}).get("items") or []
        src.setdefault("settings", {})["items"] = [
            it for it in items if it.get("source_uuid") not in v4l2_uuids
        ]
    data["sources"] = kept
    shutil.copy2(path, path + ".bak-v4l2")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return True


def notify_once():
    if os.path.isfile(FLAG):
        return
    try:
        subprocess.run(
            ["notify-send", "-a", "Tarsila", "-i", "camera-web",
             "Nenhuma câmera conectada",
             "Conecte uma webcam USB para usar câmera no OBS.\n"
             "Por enquanto use Captura de tela (X11) para gravar."],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        open(FLAG, "w").close()
    except Exception:
        pass


def main():
    if has_camera():
        try:
            if os.path.isfile(FLAG):
                os.remove(FLAG)
        except Exception:
            pass
        return 0
    if not os.path.isdir(CONFIG):
        notify_once()
        return 0
    changed = False
    for path in glob.glob(os.path.join(CONFIG, "*.json")):
        if path.endswith(".bak") or ".bak-" in path:
            continue
        try:
            if sanitize_file(path):
                changed = True
        except Exception as exc:
            sys.stderr.write("tarsila-obs-scene-sanitize: %s: %s\n" % (path, exc))
    if changed or not has_camera():
        notify_once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
