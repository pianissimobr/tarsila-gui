#!/usr/bin/env python3
import os, sys, subprocess, json, requests
from urllib.parse import urljoin
import os, json, subprocess
from urllib.parse import unquote

CONFIG_FILE = os.path.expanduser("~/.config/nextcloud-bridge/config.json")

def get_credentials():
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return data.get("url"), data.get("user"), data.get("app_password")
    except Exception:
        return None, None, None

def save_credentials(url, user, password):
    d = os.path.dirname(CONFIG_FILE)
    os.makedirs(d, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"url": url, "user": user, "app_password": password}, f)
    os.chmod(CONFIG_FILE, 0o600)

def remote_path_of(filepath):
    """Caminho remoto (depois de /remote.php/webdav) a partir do local."""
    prefix = "/remote.php/webdav"
    idx = filepath.find(prefix)
    if idx != -1:
        return unquote(filepath[idx + len(prefix):])
    # montagem via gvfs: descobre a URI real (dav://...) do arquivo
    try:
        out = subprocess.check_output(
            ["gio", "info", "-a", "standard::target-uri", filepath],
            text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "target-uri:" in line:
                real = unquote(line.split("target-uri:", 1)[1].strip())
                j = real.find(prefix)
                if j != -1:
                    return real[j + len(prefix):]
    except Exception:
        pass
    return None

def notify(title, msg):
    """Aviso na tela; usa libnotify se houver, senão zenity, senão print."""
    try:
        import gi
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify
        Notify.init("Nextcloud")
        Notify.Notification.new(title, msg).show()
        return
    except Exception:
        pass
    try:
        subprocess.Popen(["notify-send", title, msg])
        return
    except Exception:
        pass
    try:
        subprocess.Popen(["zenity", "--info", "--title=" + title, "--text=" + msg])
        return
    except Exception:
        pass
    print(f"{title}: {msg}")

def share_link(filepath):
    url, user, token = get_credentials()
    if not all([url, user, token]):
        subprocess.run(["python3", os.path.expanduser("~/.local/bin/nc-setup.py")])
        return

    remote_path = remote_path_of(filepath)
    if remote_path is None:
        notify("Nextcloud", "O arquivo precisa estar dentro da pasta da nuvem montada.")
        return

    api_url = urljoin(url.rstrip("/") + "/", "ocs/v2.php/apps/files_sharing/api/v1/shares")
    headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
    payload = {"path": remote_path, "shareType": 3, "permissions": 1}

    try:
        r = requests.post(api_url, auth=(user, token), headers=headers, data=payload, timeout=10)
        if r.status_code == 200 and r.json().get("ocs", {}).get("data"):
            share_url = r.json()["ocs"]["data"]["url"]
            subprocess.run(["xclip", "-selection", "clipboard"], input=share_url.encode())
            notify("Link Copiado!", share_url)
        else:
            notify("Erro", "Falha ao gerar link no Nextcloud")
    except Exception as e:
        notify("Erro", str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        share_link(sys.argv[1])
