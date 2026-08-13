"""Cliente IMAP — sync, mutações e IDLE."""
import base64
import email
import email.header
import imaplib
import re
import time
from email.message import Message

from . import config, db

FOLDER_MAP = {
    "INBOX": ("inbox", "Caixa de entrada"),
    "[Gmail]/Sent Mail": ("sent", "Enviados"),
    "[Gmail]/E-mails enviados": ("sent", "Enviados"),
    "[Gmail]/Drafts": ("drafts", "Rascunhos"),
    "[Gmail]/Rascunhos": ("drafts", "Rascunhos"),
    "[Gmail]/Trash": ("trash", "Lixo"),
    "[Gmail]/Lixeira": ("trash", "Lixo"),
    "[Gmail]/Starred": ("starred", "Com estrela"),
    "[Gmail]/Com estrela": ("starred", "Com estrela"),
    "[Gmail]/Spam": ("spam", "Spam"),
    "[Gmail]/Lixo eletrônico": ("spam", "Spam"),
    "[Gmail]/Lixo eletronico": ("spam", "Spam"),
}

SYNC_LIMIT = 10


def _decode_header(val: str | None) -> str:
    if not val:
        return ""
    parts = email.header.decode_header(val)
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(chunk)
    return " ".join(out)


def _snippet(text: str, n: int = 120) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[:n] + ("…" if len(t) > n else "")


def _msg_id(folder_id: str, uid: int) -> str:
    return f"{folder_id}:{uid}"


def connect() -> imaplib.IMAP4_SSL:
    cfg = config.load()
    M = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"], timeout=30)
    M.login(cfg["email"], config.password(cfg))
    return M


# Atributos SPECIAL-USE (RFC 6154). O servidor marca a FUNÇÃO da pasta, e
# isso não depende do idioma da conta -- é o jeito certo de reconhecer
# "spam", "lixeira" etc. O nome só entra como reserva.
ESPECIAIS = {
    "\\junk": ("spam", "Spam"),
    "\\trash": ("trash", "Lixo"),
    "\\sent": ("sent", "Enviados"),
    "\\drafts": ("drafts", "Rascunhos"),
    "\\flagged": ("starred", "Com estrela"),
}


def _de_utf7_imap(nome: str) -> str:
    """Converte o nome de pasta do UTF-7 MODIFICADO do IMAP (RFC 3501).

    O IMAP não manda acento em UTF-8: ele codifica em UTF-7 modificado, onde
    "&" abre um trecho em base64 (com "," no lugar de "/") e "-" fecha.
    Ou seja, "[Gmail]/Lixo eletrônico" chega como
    "[Gmail]/Lixo eletr&APQ-nico".

    Sem esta conversão, o nome nunca batia com o do FOLDER_MAP -- e como a
    ÚNICA pasta acentuada do mapa é justamente a de spam, o efeito era a
    caixa de spam simplesmente não aparecer, sem erro nenhum.
    """
    if "&" not in nome:
        return nome
    saida = []
    i = 0
    while i < len(nome):
        c = nome[i]
        if c != "&":
            saida.append(c)
            i += 1
            continue
        fim = nome.find("-", i + 1)
        if fim < 0:
            saida.append(c)
            i += 1
            continue
        trecho = nome[i + 1:fim]
        if trecho == "":
            saida.append("&")           # "&-" é um "&" literal
        else:
            try:
                b64 = trecho.replace(",", "/")
                b64 += "=" * (-len(b64) % 4)
                saida.append(base64.b64decode(b64).decode("utf-16-be"))
            except Exception:
                saida.append(nome[i:fim + 1])
        i = fim + 1
    return "".join(saida)


def _nome_da_linha(linha: str) -> str | None:
    """Nome da pasta numa linha de LIST, com ou sem aspas.

    Nem todo servidor devolve o nome entre aspas; pegar só o que está
    aspeado deixaria essas pastas de fora.
    """
    m = re.search(r'"([^"]*)"\s*$', linha)
    if m:
        return m.group(1)
    partes = linha.rsplit(None, 1)
    return partes[-1].strip('"') if len(partes) == 2 else None


def discover_folders(M: imaplib.IMAP4_SSL, conn) -> dict:
    found = {}
    typ, data = M.list()
    if typ != "OK" or not data:
        return found
    for item in data:
        if not item:
            continue
        linha = item.decode(errors="replace")
        cru = _nome_da_linha(linha)
        if not cru:
            continue
        imap_name = _de_utf7_imap(cru)

        alvo = None
        # 1) Pela função declarada pelo servidor -- vale em qualquer idioma.
        atributos = re.match(r"\(([^)]*)\)", linha)
        if atributos:
            for attr in atributos.group(1).split():
                if attr.lower() in ESPECIAIS:
                    alvo = ESPECIAIS[attr.lower()]
                    break
        # 2) Reserva: pelo nome, como antes.
        if alvo is None:
            alvo = FOLDER_MAP.get(imap_name)
        if alvo is None and imap_name.upper() == "INBOX":
            alvo = ("inbox", "Caixa de entrada")
        # 3) Última reserva: pelo fim do nome, sem diferenciar maiúsculas nem
        # acento. Cobre servidor que não declara SPECIAL-USE e usa nome
        # próprio ("INBOX.Junk", "Lixo Eletrônico").
        if alvo is None:
            folha = imap_name.rsplit("/", 1)[-1].rsplit(".", 1)[-1].strip().lower()
            for chaves, destino in (
                (("spam", "junk", "lixo eletronico", "lixo eletrônico"),
                 ("spam", "Spam")),
                (("trash", "lixeira", "deleted items"), ("trash", "Lixo")),
            ):
                if folha in chaves:
                    alvo = destino
                    break

        if alvo:
            fid, label = alvo
            if fid in found:          # já achado por um critério melhor
                continue
            # Guarda o nome CRU: é ele que o servidor entende no SELECT.
            db.upsert_folder(conn, fid, label, cru)
            found[fid] = cru
    if "inbox" not in found:
        db.upsert_folder(conn, "inbox", "Caixa de entrada", "INBOX")
        found["inbox"] = "INBOX"
    conn.commit()
    return found


def _parse_flags(flag_data) -> tuple[bool, bool]:
    read = starred = False
    if not flag_data:
        return read, starred
    s = flag_data.decode() if isinstance(flag_data, bytes) else str(flag_data)
    return "\\Seen" in s, "\\Flagged" in s


def _select(M, imap_name: str, readonly: bool = True) -> None:
    box = f'"{imap_name}"' if imap_name.startswith("[") else imap_name
    M.select(box, readonly=readonly)


def sync_folder(M: imaplib.IMAP4_SSL, conn, folder_id: str, imap_name: str,
                limit: int = SYNC_LIMIT) -> int:
    _select(M, imap_name, readonly=True)
    # Incremental: em vez de SEARCH ALL (que baixa TODOS os UIDs da pasta a
    # cada sync), busca so o que veio depois do ultimo UID sincronizado.
    # Em caixas grandes isso transforma um SEARCH de milhares de UIDs numa
    # resposta de poucos bytes.
    last_uid = db.last_sync_uid(conn, folder_id)
    if last_uid:
        typ, data = M.search(None, f"UID {last_uid + 1}:*")
    else:
        typ, data = M.search(None, "ALL")
    if typ != "OK" or not data or not data[0]:
        return 0
    uids = data[0].split()
    recent = uids[-limit:] if len(uids) > limit else uids
    if not recent:
        return 0
    count = 0
    now = time.time()
    # Batch: um unico FETCH para todos os UIDs, em vez de um round-trip IMAP
    # por mensagem. A latencia de rede da TV Box e o custo dominante — N
    # viagens viram 1.
    uid_list = b",".join(recent)
    typ, parts = M.fetch(uid_list,
                         "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
    if typ != "OK":
        return 0
    for meta in parts:
        if not isinstance(meta, tuple):
            continue
        flag_part = meta[0].decode(errors="replace") if meta[0] else ""
        header_raw = meta[1] or b""
        m_uid = re.search(r"UID (\d+)", flag_part)
        if not m_uid:
            continue
        uid = int(m_uid.group(1))
        is_read, is_starred = _parse_flags(flag_part)
        msg = email.message_from_bytes(header_raw)
        subject = _decode_header(msg.get("Subject"))
        db.upsert_message(conn, {
            "id": _msg_id(folder_id, uid),
            "folder_id": folder_id,
            "uid": uid,
            "subject": subject or "(sem assunto)",
            "sender": _decode_header(msg.get("From")),
            "recipient": _decode_header(msg.get("To")),
            "date_str": msg.get("Date") or "",
            "snippet": subject,
            "body_html": "",
            "body_plain": "",
            "is_read": int(is_read),
            "is_starred": int(is_starred),
            "has_attachments": 0,
            "synced_at": now,
        })
        count += 1
    if uids:
        db.set_sync(conn, folder_id, int(uids[-1]))
    conn.commit()
    return count


def sync_all(limit_per_folder: int = SYNC_LIMIT) -> dict:
    conn = db.connect()
    M = connect()
    try:
        folders = discover_folders(M, conn)
        totals = {fid: sync_folder(M, conn, fid, name, limit_per_folder)
                  for fid, name in folders.items()}
        db.prune_cache(conn)
        conn.commit()
        return totals
    finally:
        try:
            M.logout()
        except Exception:
            pass


def fetch_body(msg_id: str) -> dict:
    conn = db.connect()
    row = db.get_message(conn, msg_id)
    if not row:
        raise ValueError("Mensagem não encontrada")
    if row.get("body_plain") or row.get("body_html"):
        return row
    cur = conn.execute("SELECT imap_name FROM folders WHERE id = ?",
                       (row["folder_id"],))
    f = cur.fetchone()
    if not f:
        raise ValueError("Pasta não encontrada")
    M = connect()
    try:
        _select(M, f["imap_name"], readonly=True)
        typ, parts = M.fetch(str(row["uid"]).encode(), "(BODY.PEEK[])")
        if typ != "OK" or not parts or not parts[0]:
            raise ValueError("Fetch falhou")
        raw = parts[0][1] if isinstance(parts[0], tuple) else None
        if not raw:
            raise ValueError("Corpo vazio")
        em = email.message_from_bytes(raw)
        plain, html = _extract_bodies(em)
        has_att = _has_attachments(em)
        conn.execute(
            """UPDATE messages SET body_plain=?, body_html=?,
               has_attachments=?, snippet=?, synced_at=? WHERE id=?""",
            (plain, html, int(has_att), _snippet(plain or html), time.time(), msg_id),
        )
        conn.commit()
        return db.get_message(conn, msg_id)
    finally:
        try:
            M.logout()
        except Exception:
            pass


def _extract_bodies(em: Message) -> tuple[str, str]:
    plain = html = ""
    if em.is_multipart():
        for part in em.walk():
            ct = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if ct == "text/plain" and not plain:
                plain = text
            elif ct == "text/html" and not html:
                html = text
    else:
        payload = em.get_payload(decode=True)
        if payload:
            charset = em.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if em.get_content_type() == "text/html":
                html = text
            else:
                plain = text
    return plain, html


def _has_attachments(em: Message) -> bool:
    if not em.is_multipart():
        return False
    for part in em.walk():
        if part.get_content_disposition() == "attachment":
            return True
    return False


def _folder_imap(conn, folder_id: str) -> str:
    cur = conn.execute("SELECT imap_name FROM folders WHERE id = ?", (folder_id,))
    r = cur.fetchone()
    if not r:
        raise ValueError("Pasta inválida")
    return r["imap_name"]


def _store_flag(M, uid: int, active: bool, flag: str) -> None:
    cmd = "+FLAGS" if active else "-FLAGS"
    M.store(str(uid), cmd, flag)


def mark_read(msg_id: str, read: bool = True) -> None:
    conn = db.connect()
    row = db.get_message(conn, msg_id)
    if not row:
        return
    M = connect()
    try:
        _select(M, _folder_imap(conn, row["folder_id"]), readonly=False)
        _store_flag(M, row["uid"], read, "\\Seen")
        db.update_flags(conn, msg_id, is_read=int(read))
        conn.commit()
    finally:
        try:
            M.logout()
        except Exception:
            pass


def toggle_star(msg_id: str) -> bool:
    conn = db.connect()
    row = db.get_message(conn, msg_id)
    if not row:
        return False
    new_star = not row["is_starred"]
    M = connect()
    try:
        _select(M, _folder_imap(conn, row["folder_id"]), readonly=False)
        _store_flag(M, row["uid"], new_star, "\\Flagged")
        db.update_flags(conn, msg_id, is_starred=int(new_star))
        conn.commit()
        return bool(new_star)
    finally:
        try:
            M.logout()
        except Exception:
            pass


def move_to_trash(msg_id: str) -> None:
    conn = db.connect()
    row = db.get_message(conn, msg_id)
    if not row:
        return
    trash_imap = _trash_folder(conn)
    M = connect()
    try:
        src = _folder_imap(conn, row["folder_id"])
        _select(M, src, readonly=False)
        uid = str(row["uid"])
        if trash_imap:
            M.copy(uid, f'"{trash_imap}"')
        M.store(uid, "+FLAGS", "\\Deleted")
        M.expunge()
        db.delete_message(conn, msg_id)
        conn.commit()
    finally:
        try:
            M.logout()
        except Exception:
            pass


def _trash_folder(conn) -> str | None:
    cur = conn.execute("SELECT imap_name FROM folders WHERE id='trash'")
    r = cur.fetchone()
    return r["imap_name"] if r else "[Gmail]/Trash"


def save_draft(subject: str, body: str, to_addr: str = "") -> None:
    cfg = config.load()
    msg = email.message.EmailMessage()
    msg["From"] = cfg["email"]
    if to_addr:
        msg["To"] = to_addr
    msg["Subject"] = subject or "(sem assunto)"
    msg.set_content(body or "")
    conn = db.connect()
    M = connect()
    try:
        cur = conn.execute("SELECT imap_name FROM folders WHERE id='drafts'")
        r = cur.fetchone()
        draft_imap = r["imap_name"] if r else "[Gmail]/Drafts"
        M.append(f'"{draft_imap}"', "\\Draft", None, msg.as_bytes())
    finally:
        try:
            M.logout()
        except Exception:
            pass
    sync_folder_by_id("drafts")


def sync_folder_by_id(folder_id: str, limit: int = SYNC_LIMIT) -> int:
    conn = db.connect()
    cur = conn.execute("SELECT imap_name FROM folders WHERE id=?", (folder_id,))
    r = cur.fetchone()
    if not r:
        return 0
    M = connect()
    try:
        return sync_folder(M, conn, folder_id, r["imap_name"], limit)
    finally:
        try:
            M.logout()
        except Exception:
            pass


def fetch_one_new(folder_id: str = "inbox") -> dict | None:
    conn = db.connect()
    cur = conn.execute("SELECT imap_name FROM folders WHERE id=?", (folder_id,))
    r = cur.fetchone()
    if not r:
        return None
    M = connect()
    try:
        sync_folder(M, conn, folder_id, r["imap_name"], limit=5)
        conn.commit()
        msgs = db.list_messages(conn, folder_id, page=1, limit=1)
        return msgs[0] if msgs else None
    finally:
        try:
            M.logout()
        except Exception:
            pass
