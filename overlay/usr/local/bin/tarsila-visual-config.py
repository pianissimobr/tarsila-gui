#!/usr/bin/env python3
"""
tarsila-visual-config.py - Configurações visuais para Tarsila/Openbox
Versão para Openbox (sem XFCE) - via SSH-safe
"""

import os
import subprocess
import sys
import time
import re
from pathlib import Path

# ============================================================================
# DETECÇÃO DE AMBIENTE DA SESSÃO GRÁFICA REAL
# ============================================================================

def get_session_env():
    """Obtém DISPLAY e DBUS da sessão do usuário (openbox-session ou xfce4-session)."""
    env = {}
    try:
        # Procura pelo processo do openbox-session (ou xfce4-session)
        cmd = ["pgrep", "-u", str(os.getuid()), "-f", "openbox-session|xfce4-session|openbox"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        pids = result.stdout.strip().split()
        if not pids:
            # Tenta achar qualquer processo com X11 (ex: plank, polybar)
            cmd = ["pgrep", "-u", str(os.getuid()), "-f", "plank|polybar|openbox"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            pids = result.stdout.strip().split()
        
        for pid in pids:
            if pid.isdigit():
                env_file = f"/proc/{pid}/environ"
                if os.path.exists(env_file):
                    with open(env_file, 'rb') as f:
                        content = f.read()
                    for item in content.split(b'\0'):
                        if item:
                            key, sep, val = item.partition(b'=')
                            if sep:
                                env[key.decode()] = val.decode()
                    if 'DISPLAY' in env and 'DBUS_SESSION_BUS_ADDRESS' in env:
                        break
    except Exception as e:
        print(f"⚠️ Erro ao detectar ambiente: {e}")
    
    return env

def setup_environment():
    session_env = get_session_env()
    
    if 'DISPLAY' in session_env:
        os.environ['DISPLAY'] = session_env['DISPLAY']
        print(f"✅ DISPLAY definido: {os.environ['DISPLAY']}")
    else:
        os.environ['DISPLAY'] = ':0'
        print(f"⚠️ DISPLAY não detectado, usando fallback: :0")
    
    if 'DBUS_SESSION_BUS_ADDRESS' in session_env:
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = session_env['DBUS_SESSION_BUS_ADDRESS']
        print("✅ DBUS_SESSION_BUS_ADDRESS definido da sessão")
    else:
        print("⚠️ DBUS_SESSION_BUS_ADDRESS não detectado. Tentando dbus-launch...")
        try:
            result = subprocess.run(["dbus-launch", "--sh-syntax"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if line.startswith("DBUS_SESSION_BUS_ADDRESS="):
                    addr = line.split("=", 1)[1].strip()
                    os.environ['DBUS_SESSION_BUS_ADDRESS'] = addr
                    print("✅ DBUS_SESSION_BUS_ADDRESS obtido via dbus-launch")
                    break
        except Exception:
            pass
        if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            print("⚠️ Não foi possível obter DBUS. Alguns comandos podem falhar.")

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

USER_HOME = os.path.expanduser("~")
OPENBOX_RC = Path(USER_HOME) / ".config/openbox/rc.xml"
BACKUP_SUFFIX = ".backup"

def run_cmd(cmd, check=False, env=None):
    if env is None:
        env = os.environ.copy()
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"⚠️ Comando falhou: {' '.join(cmd)}")
            print(f"   Erro: {result.stderr.strip()}")
        return result
    except Exception as e:
        print(f"⚠️ Erro ao executar {' '.join(cmd)}: {e}")
        return None

def backup_file(filepath):
    if filepath.exists():
        backup = filepath.with_suffix(BACKUP_SUFFIX)
        if not backup.exists():
            import shutil
            shutil.copy2(filepath, backup)
            print(f"✅ Backup criado: {backup}")
        return True
    return False

def dconf_set(key, value):
    cmd = ["dconf", "write", key, value]
    result = run_cmd(cmd)
    return result and result.returncode == 0

def restart_openbox():
    cmd = ["openbox", "--reconfigure"]
    result = run_cmd(cmd)
    if result and result.returncode == 0:
        print("✅ Openbox reconfigurado")
        return True
    return False

def restart_plank():
    run_cmd(["pkill", "-x", "plank"])
    time.sleep(0.5)
    subprocess.Popen(["plank"], env=os.environ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ Plank reiniciado")
    return True

def restart_polybar():
    # Recarrega o polybar se estiver rodando
    run_cmd(["polybar-msg", "cmd", "restart"])
    print("✅ Polybar reiniciado (se estiver rodando)")
    return True

# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

def configure_rounded_borders():
    print("\n🔧 Configurando bordas arredondadas...")
    picom_config = Path(USER_HOME) / ".config/picom/picom.conf"
    picom_config.parent.mkdir(parents=True, exist_ok=True)
    
    picom_content = """
backend = "xrender";
corner-radius = 8;
rounded-corners-exclude = [
    "class_g = 'Plank'",
    "class_g = 'Polybar'",
    "class_g = 'xfce4-panel'",
    "window_type = 'dock'",
    "window_type = 'desktop'"
];
shadow = false;
unredir-if-possible = false;
use-damage = true;
vsync = false;
xrender-sync-fence = false;
"""
    with open(picom_config, 'w') as f:
        f.write(picom_content)
    
    run_cmd(["pkill", "-x", "picom"])
    time.sleep(0.3)
    subprocess.Popen(["picom", "-b", "--backend", "xrender", "--config", str(picom_config)],
                     env=os.environ,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ Picom configurado com bordas arredondadas")
    return True

def configure_click_focus():
    print("\n🔧 Configurando foco ao clicar...")
    if not OPENBOX_RC.exists():
        print(f"⚠️ {OPENBOX_RC} não encontrado")
        return False
    
    backup_file(OPENBOX_RC)
    with open(OPENBOX_RC, 'r') as f:
        content = f.read()
    
    focus_settings = """
  <focus>
    <focusNew>yes</focusNew>
    <followMouse>no</followMouse>
    <focusLast>yes</focusLast>
    <underMouse>no</underMouse>
    <raiseOnFocus>yes</raiseOnFocus>
  </focus>"""
    
    pattern = r'<focus>.*?</focus>'
    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, focus_settings, content, flags=re.DOTALL)
    else:
        content = re.sub(r'(<openbox_config[^>]*>)', r'\1' + focus_settings, content, count=1)
    
    with open(OPENBOX_RC, 'w') as f:
        f.write(content)
    print("✅ Foco ao clicar configurado no rc.xml")
    return True

def configure_dock_behavior():
    print("\n🔧 Configurando comportamento da Dock...")
    dock_settings = {
        "/net/launchpad/plank/docks/dock1/hide-mode": "'dodge-maximized'",
        "/net/launchpad/plank/docks/dock1/hide-delay": "3000",
        "/net/launchpad/plank/docks/dock1/position": "'bottom'",
        "/net/launchpad/plank/docks/dock1/pinned-only": "true",
        "/net/launchpad/plank/docks/dock1/lock-items": "true",
        "/net/launchpad/plank/docks/dock1/theme": "'Tarsila'",
    }
    for key, value in dock_settings.items():
        if dconf_set(key, value):
            print(f"  ✅ {key} = {value}")
        else:
            print(f"  ⚠️ Falha ao configurar {key}")
    restart_plank()
    return True

def configure_drag_limit():
    print("\n🔧 Configurando limite de arraste...")
    devilspie_dir = Path(USER_HOME) / ".config/devilspie2"
    devilspie_dir.mkdir(parents=True, exist_ok=True)
    lua_script = devilspie_dir / "window-limits.lua"
    
    lua_content = """
function window_limits(window)
    local wm_class = window:get_window_class()
    if wm_class == "Plank" or wm_class == "polybar" or 
       wm_class == "xfce4-panel" or wm_class == "xfdesktop" then
        return
    end
    if window:is_maximized() then
        return
    end
    local top_bar_height = 34
    local x, y, w, h = window:get_geometry()
    if y < top_bar_height then
        window:set_geometry(x, top_bar_height, w, h)
    end
end
register_script("window_limits")
"""
    with open(lua_script, 'w') as f:
        f.write(lua_content)
    
    run_cmd(["pkill", "-x", "devilspie2"])
    time.sleep(0.3)
    subprocess.Popen(["devilspie2"], env=os.environ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ Devilspie2 configurado com limite de arraste")
    return True

def configure_top_bar():
    print("\n🔧 Ajustando top bar (polybar)...")
    # O polybar é gerenciado pelo tarsila-ob-bar.sh, não precisa configurar aqui
    # Mas podemos reiniciar para garantir
    restart_polybar()
    return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("🎨 TARSILA - CONFIGURAÇÃO VISUAL (Openbox)")
    print("=" * 60)
    
    if os.geteuid() == 0:
        print("⚠️ Este script NÃO deve ser executado como root.")
        sys.exit(1)
    
    setup_environment()
    
    if not os.environ.get('DISPLAY'):
        print("❌ Não foi possível obter o DISPLAY. Encerrando.")
        sys.exit(1)
    
    configure_rounded_borders()
    configure_click_focus()
    configure_dock_behavior()
    configure_drag_limit()
    configure_top_bar()
    restart_openbox()
    
    print("\n" + "=" * 60)
    print("✅ Configurações aplicadas!")
    print("   Se a Dock não aparecer, execute: plank &")
    print("   Se a barra não recarregar, execute: polybar-msg cmd restart")
    print("=" * 60)

if __name__ == "__main__":
    main()
