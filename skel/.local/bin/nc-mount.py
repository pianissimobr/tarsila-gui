#!/usr/bin/env python3
# Monta o Nextcloud (gvfs) se configurado e ainda nao montado. Roda no login.
import os, json, subprocess
from urllib.parse import quote
CFG = os.path.expanduser("~/.config/nextcloud-bridge/config.json")
try:
    c = json.load(open(CFG))
except Exception:
    raise SystemExit(0)
url, user, pw = c.get("url"), c.get("user"), c.get("app_password")
if not all([url, user, pw]):
    raise SystemExit(0)
try:
    if "/remote.php/webdav" in subprocess.run(["gio", "mount", "-l"],
            capture_output=True, text=True, timeout=10).stdout:
        raise SystemExit(0)
except SystemExit:
    raise
except Exception:
    pass
dav = url.rstrip("/").replace("https://", "davs://").replace("http://", "dav://")
dav = dav.replace("davs://", "davs://" + quote(user) + "@", 1)
dav = dav.replace("dav://", "dav://" + quote(user) + "@", 1) + "/remote.php/webdav/"
try:
    subprocess.run(["gio", "mount", dav], input=(pw + "\n").encode(), timeout=30)
except Exception:
    pass
