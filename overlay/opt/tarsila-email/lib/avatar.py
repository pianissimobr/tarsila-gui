"""Avatar — foto de perfil Gmail/Google com cache local."""
import hashlib
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

CACHE_DIR = config.DATA_DIR / "avatars"
UA = "Mozilla/5.0 (compatible; TarsilaEmail/2.0)"


def gravatar_url(email: str) -> str:
    h = hashlib.md5(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{h}?d=mp&s=128"


def cache_id(email: str) -> str:
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def local_url(email: str) -> str:
    return f"/api/avatar/local/{cache_id(email)}"


def _cache_path(email: str, ext: str = "img") -> Path:
    return CACHE_DIR / f"{cache_id(email)}.{ext}"


def _detect_ext(data: bytes, ctype: str = "") -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if ctype and "png" in ctype:
        return "png"
    if ctype and "jpeg" in ctype or "jpg" in ctype:
        return "jpg"
    return "png"


def _write_cache(email: str, data: bytes, ctype: str = "") -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = _detect_ext(data, ctype)
    path = _cache_path(email, ext)
    path.write_bytes(data)
    # remove legado .jpg/.png duplicado
    for old in ("jpg", "png", "img"):
        if old != ext:
            legacy = _cache_path(email, old)
            if legacy.is_file() and legacy != path:
                legacy.unlink(missing_ok=True)
    return path


def _try_download(url: str) -> tuple[bytes, str] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
            ctype = r.headers.get_content_type() or ""
            if len(data) > 400 and ctype.startswith("image"):
                return data, ctype
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        pass
    return None


def resolve_avatar(email: str) -> str:
    """Baixa (se preciso) e devolve a URL local do avatar. Bloqueante.

    Usado pelo assistente de configuracao e pela UI GTK — sempre dentro de
    uma thread de fundo, nunca na thread da interface.
    """
    email = email.strip().lower()
    for ext in ("png", "jpg", "img"):
        if _cache_path(email, ext).is_file():
            return local_url(email)

    quoted = urllib.parse.quote(email)
    for url in (
        f"https://unavatar.io/google/{quoted}",
        f"https://www.google.com/s2/photos/profile/{quoted}?sz=128",
        gravatar_url(email),
    ):
        got = _try_download(url)
        if got:
            data, ctype = got
            _write_cache(email, data, ctype)
            return local_url(email)
    return gravatar_url(email)


# Controle de downloads em segundo plano: nao deixar dois pedidos baixarem o
# mesmo avatar ao mesmo tempo (abre-se o status e o setup em sequencia).
_DOWNLOADING = set()
_DOWNLOAD_LOCK = threading.Lock()


def resolve_avatar_fast(email: str) -> str:
    """Igual a resolve_avatar, mas NUNCA bloqueia em rede.

    Se o avatar ja esta em cache, devolve a URL local. Se nao, devolve o
    gravatar externo na hora e dispara o download em segundo plano — o cache
    aparece no proximo pedido. Usado no backend (ex.: /api/status), onde um
    fetch de 3 servicos externos em serie atrasaria a resposta em ate 30s.
    """
    email = email.strip().lower()
    for ext in ("png", "jpg", "img"):
        if _cache_path(email, ext).is_file():
            return local_url(email)

    with _DOWNLOAD_LOCK:
        if email in _DOWNLOADING:
            return gravatar_url(email)
        _DOWNLOADING.add(email)

    def baixar():
        try:
            resolve_avatar(email)
        finally:
            with _DOWNLOAD_LOCK:
                _DOWNLOADING.discard(email)

    threading.Thread(target=baixar, daemon=True).start()
    return gravatar_url(email)


def read_cache(cache_key: str) -> bytes | None:
    for ext in ("png", "jpg", "img"):
        path = CACHE_DIR / f"{cache_key}.{ext}"
        if path.is_file():
            return path.read_bytes()
    return None


def read_cache_for_email(email: str) -> bytes | None:
    cid = cache_id(email)
    return read_cache(cid)
