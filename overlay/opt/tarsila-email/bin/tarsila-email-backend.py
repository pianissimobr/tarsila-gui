#!/usr/bin/env python3
"""Tarsila Email — API HTTP local (porta 8475)."""
import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from lib import config, db, imap_sync, smtp_send  # noqa: E402

PORT = int(os.environ.get("TARSILA_EMAIL_PORT", "8475"))
UI_DIR = RAIZ / "ui"
SETUP = RAIZ / "bin" / "tarsila-email-setup.py"
_sync_lock = threading.Lock()
_last_sync = {}
FOLDER_ORDER = ["inbox", "sent", "drafts", "starred", "spam", "trash"]


def _folders_list():
    conn = db.connect()
    cur = conn.execute("SELECT id, name, imap_name FROM folders")
    folders = [dict(r) for r in cur.fetchall()]
    folders.sort(
        key=lambda f: FOLDER_ORDER.index(f["id"])
        if f["id"] in FOLDER_ORDER else 99
    )
    return folders


def _lean_body(row, fmt):
    """Envia UM dos dois corpos (plain ou html), nao os dois.

    O corpo e o maior payload da API; mandar text/plain + text/html duplicados
    dobra a banda na TV Box. Cada cliente pede o formato que consome e o outro
    so vai junto quando o preferido nao existe (comportamento identico ao atual).
    """
    out = {
        "id": row["id"],
        "subject": row["subject"],
        "sender": row["sender"],
        "recipient": row["recipient"],
        "date_str": row["date_str"],
        "snippet": row["snippet"],
        "is_read": row["is_read"],
        "is_starred": row["is_starred"],
        "has_attachments": row["has_attachments"],
    }
    if fmt == "plain":
        out["body_plain"] = row["body_plain"] or ""
        if not row["body_plain"]:
            out["body_html"] = row["body_html"] or ""
    else:
        out["body_html"] = row["body_html"] or ""
        if not row["body_html"]:
            out["body_plain"] = row["body_plain"] or ""
    return out


def _json_handler(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, data):
        body = json.dumps(data, ensure_ascii=False, default=_json_handler).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            path = urlparse(self.path)
            qs = parse_qs(path.query)
            p = path.path

            if p == "/" or p == "/index.html":
                return self._serve_ui("index.html")
            if p.startswith("/css/") or p.startswith("/js/"):
                return self._serve_ui(p.lstrip("/"))

            if p == "/api/bootstrap":
                if not config.configured():
                    return self._send(200, {"configured": False})
                acc = config.load()
                return self._send(200, {
                    "configured": True,
                    "email": acc.get("email", ""),
                    "name": acc.get("name", ""),
                    "avatar": config.account_avatar(acc.get("email", "")),
                    "accounts": config.list_accounts(),
                    "folders": _folders_list(),
                })

            if p == "/api/status":
                if not config.configured():
                    return self._send(200, {"configured": False})
                acc = config.load()
                return self._send(200, {
                    "configured": True,
                    "email": acc.get("email", ""),
                    "name": acc.get("name", ""),
                    "avatar": config.account_avatar(acc.get("email", "")),
                    "accounts": config.list_accounts(),
                })

            if p.startswith("/api/avatar/local/"):
                key = p.rsplit("/", 1)[-1]
                from lib import avatar  # noqa: E402
                data = avatar.read_cache(key)
                if not data:
                    return self._send(404, {"error": "Avatar não encontrado"})
                ctype = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return

            if p == "/api/accounts":
                return self._send(200, {"accounts": config.list_accounts()})

            if not config.configured():
                return self._send(401, {"error": "Não configurado"})

            if p == "/api/folders":
                return self._send(200, {"folders": _folders_list()})

            if p == "/api/messages":
                folder = qs.get("folder", ["inbox"])[0]
                page = int(qs.get("page", ["1"])[0])
                limit = min(int(qs.get("limit", ["10"])[0]), 10)
                q = qs.get("q", [""])[0].strip()
                conn = db.connect()
                if q:
                    msgs = db.search_messages(conn, folder, q, limit)
                    total = len(msgs)
                    return self._send(200, {
                        "messages": msgs,
                        "page": 1,
                        "total": total,
                        "has_more": False,
                        "query": q,
                    })
                msgs = db.list_messages(conn, folder, page, limit)
                total = db.count_messages(conn, folder)
                return self._send(200, {
                    "messages": msgs,
                    "page": page,
                    "total": total,
                    "has_more": page * limit < total,
                })

            if p.startswith("/api/messages/") and p.count("/") == 3:
                msg_id = p.split("/")[-1]
                if qs.get("body"):
                    fmt = qs.get("fmt", ["html"])[0]
                    row = imap_sync.fetch_body(msg_id)
                    return self._send(200, {"message": _lean_body(row, fmt)})
                conn = db.connect()
                row = db.get_message(conn, msg_id)
                if not row:
                    return self._send(404, {"error": "Não encontrada"})
                return self._send(200, {"message": row})

            if p == "/api/sync/status":
                return self._send(200, {"last_sync": _last_sync})

            return self._send(404, {"error": "Rota não encontrada"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            data = self._read_json()

            if path == "/api/logout":
                config.logout_all()
                return self._send(200, {"ok": True})

            if path == "/api/accounts/open-setup":
                import subprocess
                subprocess.Popen(
                    [sys.executable, str(SETUP)],
                    env={
                        **os.environ,
                        "DISPLAY": os.environ.get("DISPLAY", ":0"),
                        "TARSILA_EMAIL_FROM_APP": "1",
                    },
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return self._send(200, {"ok": True})

            if path == "/api/accounts/switch":
                config.set_active(data.get("email", ""))
                return self._send(200, {"ok": True, "email": config.active_id()})

            if not config.configured():
                return self._send(401, {"error": "Não configurado"})

            if path == "/api/sync":
                with _sync_lock:
                    folder = data.get("folder")
                    limit = min(int(data.get("limit", 10)), 10)
                    if folder:
                        totals = {folder: imap_sync.sync_folder_by_id(folder, limit)}
                    else:
                        totals = imap_sync.sync_all(limit)
                    _last_sync.update(totals)
                # Devolve as mensagens ja sincronizadas da pasta pedida, para
                # a UI nao precisar de um segundo GET /api/messages logo em
                # seguida (economiza um round-trip a cada sync).
                result = {"ok": True, "synced": totals}
                if folder:
                    conn = db.connect()
                    result["messages"] = db.list_messages(conn, folder, 1, limit)
                    result["page"] = 1
                    result["total"] = db.count_messages(conn, folder)
                    result["has_more"] = limit < result["total"]
                return self._send(200, result)

            if path == "/api/messages/send":
                smtp_send.send_mail(
                    data.get("to", []),
                    data.get("subject", ""),
                    data.get("body", ""),
                    data.get("attachments"),
                )
                return self._send(200, {"ok": True})

            if path == "/api/drafts":
                imap_sync.save_draft(
                    data.get("subject", ""),
                    data.get("body", ""),
                    data.get("to", ""),
                )
                return self._send(200, {"ok": True})

            if path.startswith("/api/messages/") and path.endswith("/read"):
                msg_id = path.split("/")[3]
                imap_sync.mark_read(msg_id, data.get("read", True))
                return self._send(200, {"ok": True})

            if path.startswith("/api/messages/") and path.endswith("/star"):
                msg_id = path.split("/")[3]
                starred = imap_sync.toggle_star(msg_id)
                return self._send(200, {"ok": True, "starred": starred})

            if path.startswith("/api/messages/") and path.endswith("/trash"):
                msg_id = path.split("/")[3]
                imap_sync.move_to_trash(msg_id)
                return self._send(200, {"ok": True})

            return self._send(404, {"error": "Rota não encontrada"})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})

    def _serve_ui(self, rel):
        fp = UI_DIR / rel
        if not fp.is_file():
            return self._send(404, {"error": "Arquivo não encontrado"})
        ext = fp.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(ext, "application/octet-stream")
        data = fp.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    config.migrate_from_claws()
    config.migrate_data_layout()
    os.chdir(RAIZ)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Tarsila Email backend :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
