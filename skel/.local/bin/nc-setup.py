#!/usr/bin/env python3
"""Configura servidor Nextcloud e aplica opção B: WebDAV + ~/Nextcloud symlink."""
import json
import os
import subprocess
import importlib.util
from urllib.parse import urljoin

CONFIG_FILE = os.path.expanduser("~/.config/nextcloud-bridge/config.json")
MOUNT_BIN = os.path.expanduser("~/.local/bin/nc-mount.py")


def save_credentials(url, user, password):
    d = os.path.dirname(CONFIG_FILE)
    os.makedirs(d, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"url": url, "user": user, "app_password": password}, f)
    os.chmod(CONFIG_FILE, 0o600)


def setup():
    try:
        server = subprocess.check_output(
            ["zenity", "--entry", "--title=Nextcloud",
             "--text=URL do Servidor (ex: http://100.98.224.35:8083)"],
            text=True).strip()
        if not server:
            return
        user = subprocess.check_output(
            ["zenity", "--entry", "--title=Nextcloud", "--text=Usuário"],
            text=True).strip()
        if not user:
            return
        password = subprocess.check_output(
            ["zenity", "--password", "--title=Nextcloud",
             "--text=Senha ou App Password"],
            text=True).strip()
        if not password:
            return
    except subprocess.CalledProcessError:
        return

    try:
        import requests
        test_url = urljoin(server.rstrip("/") + "/", "ocs/v2.php/cloud/user")
        r = requests.get(
            test_url, auth=(user, password),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            timeout=10)
        if r.status_code != 200:
            subprocess.run(["zenity", "--error",
                            "--text=Falha na autenticação. Verifique URL, usuário e senha."])
            return
    except Exception as e:
        subprocess.run(["zenity", "--error", "--text=Erro de Conexão: " + str(e)])
        return

    try:
        save_credentials(server, user, password)
    except Exception as e:
        subprocess.run(["zenity", "--error",
                        "--text=Erro ao guardar credenciais: " + str(e)])
        return

    # Opção B via módulo canónico
    ok = False
    try:
        spec = importlib.util.spec_from_file_location("nc_mount", MOUNT_BIN)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ok = bool(mod.mount_and_link())
    except Exception:
        subprocess.run(["python3", MOUNT_BIN], check=False)
        ok = os.path.islink(os.path.expanduser("~/Nextcloud"))

    if ok:
        subprocess.run([
            "zenity", "--info",
            "--text=Conectado!\nA nuvem está em ~/Nextcloud\n(atalho NextCloud no Thunar)."
        ])
    else:
        subprocess.run([
            "zenity", "--warning",
            "--text=Credenciais salvas, mas não foi possível montar/ligar ~/Nextcloud.\n"
                    "Verifique rede/VPN e tente de novo."
        ])


if __name__ == "__main__":
    setup()
