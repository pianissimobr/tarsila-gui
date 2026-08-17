#!/usr/bin/env python3
"""
OmniClone LiveUSB Creator - v1.0
Clona sistemas Linux em execução (Locais ou Remotos via SSH) para um Pendrive Bootável com Persistência.
Perfeito para TV Boxes ARM, Raspberry Pi e ambientes de desenvolvimento.
"""

import os
import sys
import subprocess
import re
import shutil
import time

# Pacotes temporários instalados que devem ser limpos no final
PACOTES_INSTALADOS_PELO_SCRIPT = []

def print_banner():
    print("""
    =========================================================
       ██████╗ ███╗   ███╗███╗   ██╗██╗ ██████╗██╗      ██████╗ ███╗   ██╗███████╗
      ██╔═══██╗████╗ ████║████╗  ██║██║██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
      ██║   ██║██╔████╔██║██╔██╗ ██║██║██║     ██║     ██║   ██║██╔██╗ ██║█████╗  
      ██║   ██║██║╚██╔╝██║██║╚██╗██║██║██║     ██║     ██║   ██║██║╚██╗██║██╔══╝  
      ╚██████╔╝██║ ╚═╝ ██║██║ ╚████║██║╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
       ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝ ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
                            LiveUSB & Persistence Creator
    =========================================================
    """)

def run_cmd(cmd, check=True, shell=False):
    if shell:
        print(f"[*] Executando: {cmd}")
    else:
        print(f"[*] Executando: {' '.join(cmd)}")
    subprocess.run(cmd, check=check, shell=shell)

def ensure_dependencies(remote_mode=False):
    global PACOTES_INSTALADOS_PELO_SCRIPT
    ferramentas = {
        "parted": "parted",
        "mkfs.vfat": "dosfstools",
        "mkfs.ext4": "e2fsprogs",
        "mksquashfs": "squashfs-tools",
        "wipefs": "util-linux",
        "lsblk": "util-linux",
        "udevadm": "udev"
    }
    
    if remote_mode:
        ferramentas["sshfs"] = "sshfs"

    pacotes_para_instalar = set()
    for comando, pacote in ferramentas.items():
        if shutil.which(comando) is None:
            pacotes_para_instalar.add(pacote)
            
    if pacotes_para_instalar:
        PACOTES_INSTALADOS_PELO_SCRIPT = list(pacotes_para_instalar)
        print(f"\n[*] Instalando dependências temporárias: {', '.join(PACOTES_INSTALADOS_PELO_SCRIPT)}...")
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        subprocess.run(["apt-get", "update", "-qq"], env=env, check=False)
        try:
            subprocess.run(["apt-get", "install", "-y", "-qq"] + PACOTES_INSTALADOS_PELO_SCRIPT, env=env, check=True)
        except subprocess.CalledProcessError:
            print("[!] Erro fatal ao instalar dependências. Verifique a internet.")
            sys.exit(1)

def cleanup_dependencies():
    if PACOTES_INSTALADOS_PELO_SCRIPT:
        print(f"\n[*] Limpando rastros do sistema... Removendo {', '.join(PACOTES_INSTALADOS_PELO_SCRIPT)}")
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        subprocess.run(["apt-get", "purge", "-y", "-qq"] + PACOTES_INSTALADOS_PELO_SCRIPT, env=env, check=False)
        subprocess.run(["apt-get", "autoremove", "-y", "-qq"], env=env, check=False)
        print("[+] Limpeza concluída!")

def get_disk_size_gb(disk_path):
    try:
        output = subprocess.check_output(["lsblk", "-b", "-n", "-d", "-o", "SIZE", disk_path], text=True).strip()
        return f"{int(output) / (1024 ** 3):.2f} GB"
    except Exception:
        return "Tamanho Desconhecido"

def get_part_name(disk, num):
    return f"{disk}p{num}" if any(x in disk for x in ["nvme", "mmcblk", "loop"]) else f"{disk}{num}"

def execute_usb_creation(disk, source_root):
    mnt_boot, mnt_live, mnt_pers = "/mnt/usb_boot", "/mnt/usb_live", "/mnt/usb_pers"
    for d in [mnt_boot, mnt_live, mnt_pers]:
        os.makedirs(d, exist_ok=True)

    print("\n[1] Preparando o disco e removendo montagens antigas...")
    subprocess.run(f"swapoff {disk}*", shell=True, stderr=subprocess.DEVNULL)
    subprocess.run(f"umount -l {disk}*", shell=True, stderr=subprocess.DEVNULL)
    run_cmd(["udevadm", "settle"])

    print("\n[2] Zerando tabela de partições e metadados (Opção Nuclear)...")
    run_cmd(["wipefs", "-a", disk])
    run_cmd(["dd", "if=/dev/zero", f"of={disk}", "bs=1M", "count=10", "status=progress"])
    run_cmd(["sync"])
    run_cmd(["partprobe", disk])
    run_cmd(["udevadm", "settle"])

    print("\n[3] Criando a Nova Tabela de Partições (Boot, Live, Persistence)...")
    run_cmd(["parted", "-s", disk, "mklabel", "msdos"])
    run_cmd(["parted", "-s", disk, "mkpart", "primary", "fat32", "1MiB", "257MiB"])
    run_cmd(["parted", "-s", disk, "set", "1", "boot", "on"])
    run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "257MiB", "60%"])
    run_cmd(["parted", "-s", disk, "mkpart", "primary", "ext4", "60%", "100%"])
    run_cmd(["partprobe", disk])
    run_cmd(["udevadm", "settle"])

    p1, p2, p3 = get_part_name(disk, 1), get_part_name(disk, 2), get_part_name(disk, 3)

    print("\n[4] Formatando as partições...")
    subprocess.run(f"umount -l {disk}*", shell=True, stderr=subprocess.DEVNULL)
    run_cmd(["mkfs.vfat", "-F", "32", "-n", "BOOT", p1])
    run_cmd(["mkfs.ext4", "-F", "-L", "LIVE", p2])
    run_cmd(["mkfs.ext4", "-F", "-L", "persistence", p3])

    print("\n[5] Montando o pendrive para escrita...")
    subprocess.run(f"umount -l {mnt_boot} {mnt_live} {mnt_pers}", shell=True, stderr=subprocess.DEVNULL)
    run_cmd(["mount", p1, mnt_boot])
    run_cmd(["mount", p2, mnt_live])
    run_cmd(["mount", p3, mnt_pers])

    print("\n[6] Extraindo o Kernel e arquivos de Boot da origem...")
    boot_src = os.path.join(source_root, "boot")
    run_cmd(f"cp -rL {boot_src}/. {mnt_boot}/", shell=True)

    print("\n[7] Injetando a configuração mágica de persistência...")
    with open(os.path.join(mnt_pers, "persistence.conf"), "w") as f:
        f.write("/ union\n")
    
    # Busca e altera o arquivo de boot
    patched = False
    for bf in ['uEnv.txt', 'boot.ini', 'extlinux/extlinux.conf', 'extlinux.conf']:
        filepath = os.path.join(mnt_boot, bf)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f: content = f.read()
            if "root=" in content or "append" in content.lower():
                new_content = re.sub(r'root=[^\s]+', 'boot=live components persistence', content)
                with open(filepath, 'w') as f: f.write(new_content)
                print(f"[+] Bootloader atualizado com sucesso em {bf}!")
                patched = True
                break
    if not patched:
        print("[!] Aviso: Não consegui editar o bootloader. Você terá que adicionar 'boot=live' manualmente.")

    print("\n[8] Esmagando o sistema (Gerando SquashFS) - Isso pode demorar...")
    os.makedirs(os.path.join(mnt_live, "live"), exist_ok=True)
    squashfs_path = os.path.join(mnt_live, "live", "filesystem.squashfs")
    
    # Exclusões baseadas no que não devemos copiar do sistema original
    excludes = ["proc", "sys", "dev", "run", "tmp", "var/tmp", "media", "mnt", "boot", "lost+found"]
    
    mksquashfs_cmd = ["mksquashfs", source_root, squashfs_path]
    for exc in excludes:
        mksquashfs_cmd.extend(["-e", exc])
    
    run_cmd(mksquashfs_cmd)

    print("\n[9] Finalizando e sincronizando os discos...")
    run_cmd(["sync"])
    run_cmd(["umount", "-l", mnt_boot, mnt_live, mnt_pers])
    
    print("\n=====================================================")
    print(" ✅ SUCESSO! SEU PENDRIVE CLONADO ESTÁ PRONTO.")
    print("=====================================================")

def main():
    if os.geteuid() != 0:
        print("[!] Erro: Este script requer privilégios de administrador (sudo).")
        sys.exit(1)

    print_banner()

    # MENU INTERATIVO: Local ou Remoto?
    print("O que você deseja clonar para o pendrive?")
    print(" [1] ESTE computador (Sistema Local)")
    print(" [2] UM OUTRO computador na rede (Remoto via SSH)")
    escolha = input("Opção (1/2): ").strip()

    is_remote = (escolha == '2')
    remote_mountpoint = "/mnt/omniclone_remote"
    source_root = "/"

    # Se for remoto, coleta os dados
    if is_remote:
        print("\n--- Configuração Remota ---")
        remote_ip = input("IP do dispositivo remoto (ex: 192.168.0.100): ").strip()
        remote_user = input("Usuário SSH (ex: root): ").strip()
        remote_port = input("Porta SSH (pressione ENTER para 22): ").strip() or "22"
        source_root = remote_mountpoint

    # Validação do Pendrive
    disk = input("\nDigite o caminho do Pendrive (ex: /dev/sdb): ").strip()
    if not os.path.exists(disk):
        print(f"[!] Erro: Dispositivo {disk} não encontrado.")
        sys.exit(1)

    disk_size = get_disk_size_gb(disk)
    print("\n" + "="*60)
    print(f" ⚠️  ALERTA DE SEGURANÇA: {disk} ({disk_size}) SERÁ APAGADO!")
    print("="*60)
    confirm = input("Digite 'SIM' para FORMATAR e continuar: ")
    if confirm != "SIM":
        print("\n[!] Operação cancelada. Nenhum disco foi alterado.")
        sys.exit(0)

    # Verifica e instala dependências locais (incluindo sshfs se remoto)
    ensure_dependencies(remote_mode=is_remote)

    try:
        if is_remote:
            # Monta o sistema remoto
            os.makedirs(remote_mountpoint, exist_ok=True)
            print(f"\n[*] Conectando via SSH a {remote_user}@{remote_ip}...")
            print("    (Se pedir senha, digite a senha do dispositivo remoto)")
            
            # Comando SSHFS (Monta a raiz '/' do alvo no nosso /mnt/omniclone_remote)
            sshfs_cmd = ["sshfs", f"{remote_user}@{remote_ip}:/", remote_mountpoint, "-p", remote_port]
            subprocess.run(sshfs_cmd, check=True)
            print("[+] Sistema remoto montado com sucesso!")

        # Roda a mágica da cópia!
        execute_usb_creation(disk, source_root)

    except KeyboardInterrupt:
        print("\n\n[!] Operação CANCELADA pelo usuário (Ctrl+C).")
    except Exception as e:
        print(f"\n[!] ERRO DURANTE A EXECUÇÃO: {e}")
    finally:
        # Bloco de Limpeza (Roda sempre)
        if is_remote:
            print("\n[*] Desmontando o sistema remoto...")
            subprocess.run(["umount", "-l", remote_mountpoint], check=False, stderr=subprocess.DEVNULL)
            if os.path.exists(remote_mountpoint):
                os.rmdir(remote_mountpoint)
        
        cleanup_dependencies()

if __name__ == "__main__":
    main()
