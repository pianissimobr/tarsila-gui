"""Cliente HTTP para a API local do Tarsila Email."""
import json
import urllib.error
import urllib.request


class ApiError(Exception):
    pass


class Api:
    def __init__(self, port: int = 8475):
        self.base = f"http://127.0.0.1:{port}"

    def _request(self, method: str, path: str, data=None):
        url = self.base + path
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
                msg = err.get("error", e.reason)
            except Exception:
                msg = e.reason
            raise ApiError(msg) from e
        except urllib.error.URLError as e:
            raise ApiError(str(e.reason)) from e

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, data=None):
        return self._request("POST", path, data or {})

    def ok(self) -> bool:
        try:
            self.get("/api/status")
            return True
        except Exception:
            return False

    def fetch_bytes(self, path: str) -> bytes | None:
        url = path if path.startswith("http") else self.base + path
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return r.read()
        except Exception:
            return None
