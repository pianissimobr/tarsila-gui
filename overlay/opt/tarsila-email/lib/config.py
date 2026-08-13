"""Configuração multi-conta Tarsila Email."""
import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "tarsila-email"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = Path.home() / ".local" / "share" / "tarsila-email"
# Depois de um "Sair" explícito, não reimportar o Claws automaticamente
# no próximo open (senão o launcher recria a conta e pula o setup).
SKIP_CLAWS_MIGRATE = CONFIG_DIR / ".skip_claws_migrate"

GMAIL_IMAP = ("imap.gmail.com", 993)
GMAIL_SMTP = ("smtp.gmail.com", 465)
PASSKEY = b"passkey0"


def _encrypt(pw: str) -> str:
    raw = pw.encode()
    xored = bytes(b ^ PASSKEY[i % 8] for i, b in enumerate(raw))
    return base64.b64encode(xored).decode()


def _decrypt(enc: str) -> str:
    raw = base64.b64decode(enc)
    return bytes(b ^ PASSKEY[i % 8] for i, b in enumerate(raw)).decode()


def _read_store() -> dict:
    if not CONFIG_FILE.is_file():
        return {"active": "", "accounts": {}}
    data = json.loads(CONFIG_FILE.read_text())
    if "accounts" in data:
        return data
    if data.get("email"):
        email = data["email"]
        return {
            "active": email,
            "accounts": {email: data},
        }
    return {"active": "", "accounts": {}}


def _write_store(store: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(store, indent=2))
    CONFIG_FILE.chmod(0o600)


def configured() -> bool:
    """Há conta ativa utilizável (e-mail + senha), não só lixo no JSON."""
    store = _read_store()
    active = (store.get("active") or "").strip()
    accounts = store.get("accounts") or {}
    if not active or active not in accounts:
        return False
    acc = accounts[active]
    return bool(acc.get("email") and acc.get("password_enc"))


def active_id() -> str:
    return _read_store().get("active", "")


def list_accounts() -> list:
    store = _read_store()
    out = []
    for email, acc in store.get("accounts", {}).items():
        out.append({
            "email": email,
            "name": acc.get("name", email.split("@")[0]),
            "active": email == store.get("active"),
            "avatar": account_avatar(email),
        })
    return sorted(out, key=lambda a: a["email"])


def load() -> dict:
    store = _read_store()
    email = store.get("active", "")
    acc = store.get("accounts", {}).get(email, {})
    if acc:
        return acc
    return {}


def db_path(account_id: str | None = None) -> Path:
    aid = account_id or active_id()
    safe = aid.replace("@", "_at_").replace("/", "_")
    return DATA_DIR / safe / "mail.db"


def gravatar_url(email: str) -> str:
    from . import avatar
    return avatar.gravatar_url(email)


def account_avatar(email: str) -> str:
    from . import avatar
    return avatar.resolve_avatar_fast(email)


def save_account(email: str, password: str, name: str = "") -> None:
    store = _read_store()
    accounts = store.setdefault("accounts", {})
    accounts[email] = {
        "email": email,
        "name": name or email.split("@")[0],
        "password_enc": _encrypt(password.replace(" ", "")),
        "imap_host": GMAIL_IMAP[0],
        "imap_port": GMAIL_IMAP[1],
        "smtp_host": GMAIL_SMTP[0],
        "smtp_port": GMAIL_SMTP[1],
    }
    store["active"] = email
    _write_store(store)
    # Conta salva de propósito: permite migrate do Claws de novo só se
    # o usuário apagar tudo e nunca tiver clicado em Sair depois.
    if SKIP_CLAWS_MIGRATE.is_file():
        try:
            SKIP_CLAWS_MIGRATE.unlink()
        except OSError:
            pass
    db_path(email).parent.mkdir(parents=True, exist_ok=True)
    try:
        account_avatar(email)
    except Exception:
        pass


def set_active(email: str) -> None:
    store = _read_store()
    if email not in store.get("accounts", {}):
        raise ValueError("Conta não encontrada")
    store["active"] = email
    _write_store(store)


def password(cfg: dict | None = None) -> str:
    cfg = cfg or load()
    enc = cfg.get("password_enc", "")
    return _decrypt(enc) if enc else ""


def logout_all() -> None:
    """Apaga contas/dados e marca para NÃO reimportar o Claws no próximo open."""
    if CONFIG_DIR.is_dir():
        shutil.rmtree(CONFIG_DIR)
    if DATA_DIR.is_dir():
        shutil.rmtree(DATA_DIR)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SKIP_CLAWS_MIGRATE.write_text("1\n")
    try:
        SKIP_CLAWS_MIGRATE.chmod(0o600)
    except OSError:
        pass


def migrate_data_layout() -> None:
    """Move mail.db legado para pasta da conta ativa."""
    import shutil
    old_db = DATA_DIR / "mail.db"
    if not old_db.is_file() or not configured():
        return
    new_db = db_path()
    if new_db.is_file():
        return
    new_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_db), str(new_db))


def migrate_from_claws() -> bool:
    if configured():
        return True
    # Usuário pediu Sair: o setup é o caminho, não o Claws em silêncio.
    if SKIP_CLAWS_MIGRATE.is_file():
        return False
    acc = Path.home() / ".claws-mail" / "accountrc"
    if not acc.is_file():
        return False
    text = acc.read_text()
    if "receive_server=imap.gmail.com" not in text:
        return False
    m_addr = re.search(r"^address=(.+)$", text, re.M)
    if not m_addr:
        return False
    email = m_addr.group(1)
    enc = None
    m_pwd = re.search(r"^password=(.+)$", text, re.M)
    if m_pwd:
        enc = m_pwd.group(1)
    else:
        store = Path.home() / ".claws-mail" / "passwordstorerc"
        if store.is_file():
            bloco = re.search(r"\[account:1\]\s*\nrecv\s+(\S+)", store.read_text(), re.M)
            if bloco:
                enc = bloco.group(1)
    if not enc:
        return False
    pw = _decrypt(enc)
    m_name = re.search(r"^name=(.+)$", text, re.M)
    save_account(email, pw, m_name.group(1) if m_name else "")
    return True

# Compat legado
save = save_account
