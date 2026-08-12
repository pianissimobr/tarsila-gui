#!/usr/bin/env python3
import os, sys, subprocess, json, requests
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
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
    """Caminho remoto (depois de /remote.php/webdav) a partir do local.

    Opção B: arquivos sob ~/Nextcloud (symlink gvfs) ou URI dav://.
    """
    from urllib.parse import unquote
    import os, subprocess
    prefix = "/remote.php/webdav"
    nc_home = os.path.expanduser("~/Nextcloud")

    # 1) caminho explícito com /remote.php/webdav
    idx = filepath.find(prefix)
    if idx != -1:
        return unquote(filepath[idx + len(prefix):]) or "/"

    # 2) sob ~/Nextcloud (symlink → gvfs) — opção B
    try:
        real_nc = os.path.realpath(nc_home)
        real_p = os.path.realpath(filepath)
        if real_p == real_nc or real_p.startswith(real_nc + os.sep):
            rel = real_p[len(real_nc):] or "/"
            return unquote(rel)
        # também se o path lógico começa com ~/Nextcloud
        if filepath == nc_home or filepath.startswith(nc_home + os.sep):
            rel = filepath[len(nc_home):] or "/"
            return unquote(rel)
    except Exception:
        pass

    # 3) montagem gvfs: URI real dav://...
    try:
        out = subprocess.check_output(
            ["gio", "info", "-a", "standard::target-uri", filepath],
            text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if "target-uri:" in line:
                real = unquote(line.split("target-uri:", 1)[1].strip())
                j = real.find(prefix)
                if j != -1:
                    return real[j + len(prefix):] or "/"
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

def open_online(filepath):
    url, user, token = get_credentials()
    if not all([url, user, token]):
        subprocess.run(["python3", os.path.expanduser("~/.local/bin/nc-setup.py")])
        return

    remote_path = remote_path_of(filepath)
    if remote_path is None:
        notify("Nextcloud", "O arquivo precisa estar dentro da pasta da nuvem montada.")
        return

    dav_url = urljoin(url.rstrip("/") + "/", "remote.php/webdav" + remote_path)
    headers = {"Depth": "0"}
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>'

    try:
        r = requests.request("PROPFIND", dav_url, auth=(user, token), headers=headers, data=body, timeout=10)
        if r.status_code == 207:
            xml = ET.fromstring(r.text)
            fileid_el = xml.find(".//{http://owncloud.org/ns}fileid")
            if fileid_el is not None:
                online_url = url.rstrip("/") + f"/index.php/f/{fileid_el.text}"
                subprocess.run(["xdg-open", online_url])
    except Exception:
        pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        open_online(sys.argv[1])
