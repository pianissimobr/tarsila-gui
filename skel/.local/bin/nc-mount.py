#!/usr/bin/env python3
"""Monta o Nextcloud via GVFS e liga ~/Nextcloud ao ponto de montagem (opção B).

Atalho do Thunar "NextCloud" → file:///home/alan/Nextcloud (symlink → gvfs).
Pode ser chamado no login (autostart) ou pelo plugin/nc-setup.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urlparse

HOME = Path.home()
CFG = HOME / ".config/nextcloud-bridge/config.json"
NC_DIR = HOME / "Nextcloud"
BOOKMARKS = HOME / ".config/gtk-3.0/bookmarks"
PREFIX = "/remote.php/webdav"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


def _load_cfg():
    try:
        return json.loads(CFG.read_text())
    except Exception:
        return {}


def _ensure_bookmark():
    """Garante um único atalho NextCloud → ~/Nextcloud (sem dav:// duplicado)."""
    BOOKMARKS.parent.mkdir(parents=True, exist_ok=True)
    wanted = "file:///home/alan/Nextcloud NextCloud"
    lines = []
    if BOOKMARKS.exists():
        for line in BOOKMARKS.read_text().splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("dav://") or s.startswith("davs://"):
                continue
            if "Nextcloud" in s or "NextCloud" in s:
                continue
            lines.append(s)
    lines.append(wanted)
    BOOKMARKS.write_text("\n".join(lines) + "\n")


def _dav_url(url: str, user: str) -> str:
    host = url.rstrip("/")
    dav = host.replace("https://", "davs://").replace("http://", "dav://")
    dav = dav.replace("davs://", "davs://" + quote(user) + "@", 1)
    dav = dav.replace("dav://", "dav://" + quote(user) + "@", 1)
    return dav + PREFIX + "/"


def _already_mounted() -> bool:
    try:
        out = subprocess.run(
            ["gio", "mount", "-l"], capture_output=True, text=True, timeout=10
        ).stdout
        return PREFIX in out
    except Exception:
        return False


def _mount(url: str, user: str, pw: str) -> None:
    if _already_mounted():
        return
    dav = _dav_url(url, user)
    try:
        subprocess.run(
            ["gio", "mount", dav],
            input=(pw + "\n").encode(),
            timeout=30,
            check=False,
        )
    except Exception:
        pass


def _gvfs_candidates(url: str) -> list[Path]:
    gvfs = RUNTIME / "gvfs"
    if not gvfs.is_dir():
        return []
    host = urlparse(url).hostname or ""
    port = urlparse(url).port
    all_dav = sorted(gvfs.glob("dav:*")) + sorted(gvfs.glob("davs:*"))
    if not host:
        return all_dav
    matched = []
    for p in all_dav:
        name = p.name
        if f"host={host}" not in name:
            continue
        if port is not None and f"port={port}" not in name:
            # http default 80 / https 443 às vezes omite port=
            if port not in (80, 443):
                continue
        matched.append(p)
    return matched or [p for p in all_dav if host in p.name]


def link_home(url: str, retries: int = 25, delay: float = 1.0) -> bool:
    """Aponta ~/Nextcloud para o diretório gvfs do WebDAV."""
    target = None
    for _ in range(max(1, retries)):
        cands = _gvfs_candidates(url)
        if cands:
            target = cands[0]
            break
        time.sleep(delay)
    if target is None:
        return False

    if NC_DIR.exists() or NC_DIR.is_symlink():
        if NC_DIR.is_symlink():
            if NC_DIR.resolve() == target.resolve():
                _ensure_bookmark()
                return True
            NC_DIR.unlink()
        elif NC_DIR.is_dir():
            bak = HOME / f"Nextcloud.local.bak.{time.strftime('%Y%m%d%H%M%S')}"
            NC_DIR.rename(bak)
        else:
            NC_DIR.unlink()

    NC_DIR.symlink_to(target)
    _ensure_bookmark()
    return True


def mount_and_link() -> bool:
    c = _load_cfg()
    url, user, pw = c.get("url"), c.get("user"), c.get("app_password")
    if not all([url, user, pw]):
        return False
    _mount(url, user, pw)
    return link_home(url)


if __name__ == "__main__":
    raise SystemExit(0 if mount_and_link() else 0)
