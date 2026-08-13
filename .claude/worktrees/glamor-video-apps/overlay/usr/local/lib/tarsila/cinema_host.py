#!/usr/bin/env python3
"""Tarsila — host nativo da extensao.

Duas funcoes:
  1) Modo Cinema: recebe uma URL e abre no mpv.
  2) Configuracoes: le e grava as preferencias em ~/.config/tarsila/.
     A extensao NAO consegue escrever em disco; por isso passa por aqui.

POLITICA: reproduz, nunca salva em disco.
"""
import json
import os
import struct
import subprocess
import sys

CFG = os.path.expanduser("~/.config/tarsila")

# Perfis de qualidade do Modo Cinema. Medido nesta box (Big Buck Bunny):
#   1080p60 H.264 -> 298% de CPU e 57C  (perto demais do teto de 400%)
#   480p30  H.264 ->  44% de CPU e 53C
# Por isso o 1080p do Automatico limita a 30fps: acima disso a placa nao sustenta.
QUALIDADE = {
    # "auto" NAO e a adaptacao do YouTube -- o mpv escolhe UM formato e fica
    # nele, nao ha negociacao durante a reproducao. Aqui "auto" significa "a
    # melhor que ESTA placa sustenta": H.264 ate 1080p e ate 30fps. AV1 e 4K
    # ficam de fora de proposito (sem VPU no mainline, tudo e software).
    "auto": ("bv*[height<=?1080][fps<=?30][vcodec^=avc1]+ba/"
             "bv*[height<=?720][vcodec^=avc1]+ba/bv*[height<=?720]+ba/best"),
    "1080": ("bv*[height<=?1080][vcodec^=avc1]+ba/"
             "bv*[height<=?1080]+ba/best"),
    "720":  "bv*[height<=?720][vcodec^=avc1]+ba/bv*[height<=?720]+ba/best",
    "480":  "bv*[height<=?480]+ba/best",
}


def ler_mensagem():
    bruto = sys.stdin.buffer.read(4)
    if len(bruto) < 4:
        sys.exit(0)
    return json.loads(sys.stdin.buffer.read(struct.unpack("<I", bruto)[0]).decode("utf-8"))


def responder(obj):
    dados = json.dumps(obj).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(dados)))
    sys.stdout.buffer.write(dados)
    sys.stdout.buffer.flush()


def abrir_no_mpv(url, qualidade=None):
    """A qualidade vem do microbotao ao lado do "Modo Cinema", por VIDEO.
    Escolher na hora e melhor que uma tela de configuracao: o usuario decide
    olhando o video que quer ver, e nao precisa lembrar que a opcao existe."""
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "erro": "URL invalida"}
    fmt = QUALIDADE.get(qualidade) or QUALIDADE["auto"]
    # Ja tem video aberto? Entao o clique e repetido: o usuario achou que o
    # primeiro nao pegou porque o mpv demora a pintar a tela (o yt-dlp precisa
    # resolver o endereco antes). Abrir um segundo mpv so piora tudo.
    if subprocess.run(["pgrep", "-x", "mpv"],
                      stdout=subprocess.DEVNULL).returncode == 0:
        return {"ok": True, "jaAberto": True}

    cmd = ["mpv", "--fs", "--hwdec=auto-safe", "--ytdl=yes",
           "--ytdl-format=" + fmt, "--no-terminal", "--osc=yes", url]
    # tarsila-abrindo segura a ampulheta e bloqueia cliques ate o mpv pintar.
    if os.access("/usr/local/bin/tarsila-abrindo", os.X_OK):
        cmd = ["/usr/local/bin/tarsila-abrindo"] + cmd
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return {"ok": True}
    except FileNotFoundError:
        return {"ok": False, "erro": "mpv nao instalado"}
    except Exception as exc:
        return {"ok": False, "erro": str(exc)}


def main():
    msg = ler_mensagem()
    try:
        responder(abrir_no_mpv(msg.get("url", ""), msg.get("qualidade")))
    except Exception as exc:
        responder({"ok": False, "erro": str(exc)})


if __name__ == "__main__":
    main()
