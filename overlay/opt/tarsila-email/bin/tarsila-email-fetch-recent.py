#!/usr/bin/env python3
"""Baixa só os N e-mails mais recentes do Gmail para a caixa local (MH).

O Claws tentaria sincronizar tudo (~13k). Na TV Box baixamos só o necessario.
"""
import base64
import email
import imaplib
import os
import re
import sys
from pathlib import Path

LIMITE = int(os.environ.get("TARSILA_EMAIL_LIMITE", "25"))
ACCOUNTRC = Path.home() / ".claws-mail" / "accountrc"
INBOX = Path.home() / "Mail" / "inbox"


def ler_senha(account_id=1):
    m_pwd = re.search(r"^password=(.+)$", ACCOUNTRC.read_text(), re.M)
    if m_pwd:
        enc = m_pwd.group(1)
    else:
        store = Path.home() / ".claws-mail" / "passwordstorerc"
        if not store.is_file():
            return None
        bloco = re.search(
            rf"\[account:{account_id}\]\s*\nrecv\s+(\S+)",
            store.read_text(),
            re.M,
        )
        if not bloco:
            return None
        enc = bloco.group(1)
    raw = base64.b64decode(enc)
    k = b"passkey0"
    return bytes(b ^ k[i % 8] for i, b in enumerate(raw)).decode().replace(" ", "")


def ler_conta():
    if not ACCOUNTRC.is_file():
        return None
    text = ACCOUNTRC.read_text()
    m_addr = re.search(r"^address=(.+)$", text, re.M)
    m_srv = re.search(r"^receive_server=(.+)$", text, re.M)
    if not (m_addr and m_srv):
        return None
    senha = ler_senha()
    if not senha:
        return None
    return m_addr.group(1), senha, m_srv.group(1)


def prox_numero(pasta):
    nums = []
    for f in pasta.iterdir():
        if f.is_file() and f.name.isdigit():
            nums.append(int(f.name))
    return max(nums) if nums else 0


def main():
    conta = ler_conta()
    if not conta:
        print("Sem conta configurada.", file=sys.stderr)
        return 1
    email_addr, senha, servidor = conta
    INBOX.mkdir(parents=True, exist_ok=True)

    M = imaplib.IMAP4_SSL(servidor, 993, timeout=30)
    M.login(email_addr, senha)
    M.select("INBOX", readonly=True)

    typ, data = M.search(None, "ALL")
    ids = data[0].split() if data and data[0] else []
    recentes = ids[-LIMITE:] if len(ids) > LIMITE else ids
    if not recentes:
        M.logout()
        print("Inbox vazia no servidor.")
        return 0

    n = prox_numero(INBOX)
    baixados = 0
    for uid in recentes:
        typ, parts = M.fetch(uid, "(RFC822)")
        if typ != "OK" or not parts or not parts[0]:
            continue
        raw = parts[0][1]
        if not raw:
            continue
        n += 1
        dest = INBOX / str(n)
        dest.write_bytes(raw)
        baixados += 1

    M.logout()
    (INBOX / ".claws_mark").write_text(str(n))
    print(f"OK: {baixados} e-mails recentes (de {len(ids)} no Gmail)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
