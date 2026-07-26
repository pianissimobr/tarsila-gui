#!/usr/bin/env python3
import os, sys, subprocess, json, requests
from urllib.parse import urljoin, quote
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

def setup():
    try:
        server = subprocess.check_output(
            ["zenity", "--entry", "--title=Nextcloud", "--text=URL do Servidor (ex: https://nuvem.exemplo.com)"],
            text=True).strip()
        if not server: return

        user = subprocess.check_output(
            ["zenity", "--entry", "--title=Nextcloud", "--text=Usuário"], text=True).strip()
        if not user: return

        password = subprocess.check_output(
            ["zenity", "--password", "--title=Nextcloud", "--text=Senha ou App Password"], text=True).strip()
        if not password: return
    except subprocess.CalledProcessError:
        return

    test_url = urljoin(server.rstrip("/") + "/", "ocs/v2.php/cloud/user")
    headers = {"OCS-APIRequest": "true", "Accept": "application/json"}

    try:
        r = requests.get(test_url, auth=(user, password), headers=headers, timeout=10)
        if r.status_code != 200:
            subprocess.run(["zenity", "--error", "--text=Falha na autenticação. Verifique URL, usuário e senha."])
            return
    except Exception as e:
        subprocess.run(["zenity", "--error", "--text=Erro de Conexão: " + str(e)])
        return

    # Guarda credenciais em arquivo local (sem Secret Service / D-Bus)
    try:
        save_credentials(server, user, password)
    except Exception as e:
        subprocess.run(["zenity", "--error", "--text=Erro ao guardar credenciais: " + str(e)])
        return

    # Monta via GIO/GVFS. Usuário embutido na URL; senha pelo stdin do gio.
    host_url = server.rstrip("/")
    dav_url = host_url.replace("https://", "davs://").replace("http://", "dav://")
    dav_url = dav_url.replace("davs://", "davs://" + quote(user) + "@", 1)
    dav_url = dav_url.replace("dav://", "dav://" + quote(user) + "@", 1)
    dav_url = dav_url + "/remote.php/webdav/"
    try:
        subprocess.run(["gio", "mount", dav_url],
                       input=(password + "\n").encode(), timeout=30)
    except Exception:
        pass

    subprocess.run(["zenity", "--info", "--text=Conectado com sucesso!\nSua nuvem está disponível no Thunar."])

if __name__ == "__main__":
    setup()
