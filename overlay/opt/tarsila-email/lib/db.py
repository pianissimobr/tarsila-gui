"""SQLite — cache local de mensagens."""
import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    imap_name TEXT NOT NULL,
    unread INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    folder_id TEXT NOT NULL,
    uid INTEGER NOT NULL,
    subject TEXT,
    sender TEXT,
    recipient TEXT,
    date_str TEXT,
    snippet TEXT,
    body_html TEXT,
    body_plain TEXT,
    is_read INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0,
    has_attachments INTEGER DEFAULT 0,
    synced_at REAL,
    FOREIGN KEY (folder_id) REFERENCES folders(id)
);
CREATE INDEX IF NOT EXISTS idx_msg_folder ON messages(folder_id, uid DESC);
CREATE TABLE IF NOT EXISTS sync_state (
    folder_id TEXT PRIMARY KEY,
    last_uid INTEGER DEFAULT 0,
    last_sync REAL
);
"""


def connect(account_id: str | None = None) -> sqlite3.Connection:
    path = config.db_path(account_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_folder(conn, fid: str, name: str, imap_name: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO folders (id, name, imap_name) VALUES (?, ?, ?)",
        (fid, name, imap_name),
    )


def upsert_message(conn, row: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO messages
        (id, folder_id, uid, subject, sender, recipient, date_str, snippet,
         body_html, body_plain, is_read, is_starred, has_attachments, synced_at)
        VALUES (:id, :folder_id, :uid, :subject, :sender, :recipient, :date_str,
                :snippet, :body_html, :body_plain, :is_read, :is_starred,
                :has_attachments, :synced_at)""",
        row,
    )


def list_messages(conn, folder_id: str, page: int = 1, limit: int = 10) -> list:
    off = (page - 1) * limit
    cur = conn.execute(
        """SELECT id, subject, sender, recipient, date_str,
                  snippet, is_read, is_starred, has_attachments
           FROM messages WHERE folder_id = ?
           ORDER BY uid DESC LIMIT ? OFFSET ?""",
        (folder_id, limit, off),
    )
    return [dict(r) for r in cur.fetchall()]


def get_message(conn, msg_id: str) -> dict | None:
    cur = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
    r = cur.fetchone()
    return dict(r) if r else None


def count_messages(conn, folder_id: str) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE folder_id = ?", (folder_id,)
    )
    return cur.fetchone()[0]


def update_flags(conn, msg_id: str, is_read=None, is_starred=None) -> None:
    if is_read is not None:
        conn.execute("UPDATE messages SET is_read = ? WHERE id = ?", (is_read, msg_id))
    if is_starred is not None:
        conn.execute(
            "UPDATE messages SET is_starred = ? WHERE id = ?", (is_starred, msg_id)
        )


def delete_message(conn, msg_id: str) -> None:
    conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))


def prune_cache(conn, max_messages: int = 500) -> None:
    cur = conn.execute("SELECT COUNT(*) FROM messages")
    n = cur.fetchone()[0]
    if n <= max_messages:
        return
    excess = n - max_messages
    conn.execute(
        """DELETE FROM messages WHERE id IN (
            SELECT id FROM messages ORDER BY synced_at ASC LIMIT ?)""",
        (excess,),
    )


def search_messages(conn, folder_id: str, query: str, limit: int = 10) -> list:
    q = f"%{query.strip()}%"
    cur = conn.execute(
        """SELECT id, subject, sender, recipient, date_str,
                  snippet, is_read, is_starred, has_attachments
           FROM messages WHERE folder_id = ?
           AND (subject LIKE ? OR sender LIKE ? OR snippet LIKE ? OR recipient LIKE ?)
           ORDER BY uid DESC LIMIT ?""",
        (folder_id, q, q, q, q, limit),
    )
    return [dict(r) for r in cur.fetchall()]


def last_sync_uid(conn, folder_id: str) -> int:
    cur = conn.execute("SELECT last_uid FROM sync_state WHERE folder_id = ?", (folder_id,))
    r = cur.fetchone()
    return r[0] if r else 0


def set_sync(conn, folder_id: str, last_uid: int) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO sync_state (folder_id, last_uid, last_sync)
           VALUES (?, ?, ?)""",
        (folder_id, last_uid, time.time()),
    )
