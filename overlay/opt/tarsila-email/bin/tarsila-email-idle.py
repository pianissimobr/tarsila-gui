#!/usr/bin/env python3
"""Tarsila Email — IMAP IDLE + notificações desktop."""
import os
import select
import subprocess
import sys
import time
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from lib import config, imap_sync  # noqa: E402

IDLE_TIMEOUT = 540  # Gmail renova IDLE ~10 min
POLL_FALLBACK = 300


def notify(title: str, body: str) -> None:
    body = (body or "")[:200]
    for cmd in (
        ["notify-send", "-a", "Tarsila Email", "-i", "internet-mail", title, body],
        ["notify-send", title, body],
    ):
        try:
            subprocess.run(cmd, timeout=5, check=False)
            return
        except Exception:
            continue


def idle_loop() -> None:
    if not config.configured():
        time.sleep(30)
        return
    M = imap_sync.connect()
    conn = __import__("lib.db", fromlist=["db"]).db.connect()
    folders = imap_sync.discover_folders(M, conn)
    inbox = folders.get("inbox", "INBOX")
    box = f'"{inbox}"' if inbox.startswith("[") else inbox
    M.select(box)
    tag = M._new_tag()
    M.send(f"{tag} IDLE\r\n".encode())
    last_notify = 0
    try:
        while True:
            r, _, _ = select.select([M.socket()], [], [], IDLE_TIMEOUT)
            if not r:
                M.send(b"DONE\r\n")
                M._get_response(tag)
                tag = M._new_tag()
                M.send(f"{tag} IDLE\r\n".encode())
                continue
            while M.socket().recv(4096):
                pass
            now = time.time()
            if now - last_notify < 5:
                continue
            last_notify = now
            msg = imap_sync.fetch_one_new("inbox")
            if msg:
                notify(
                    msg.get("sender", "Novo e-mail"),
                    msg.get("subject", ""),
                )
    finally:
        try:
            M.send(b"DONE\r\n")
            M.logout()
        except Exception:
            pass


def main():
    config.migrate_from_claws()
    while True:
        try:
            if config.configured():
                idle_loop()
            else:
                time.sleep(60)
        except KeyboardInterrupt:
            break
        except Exception:
            traceback.print_exc()
            time.sleep(POLL_FALLBACK)


if __name__ == "__main__":
    main()
