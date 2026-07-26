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
# Por isso "maxima" limita a 30fps em 1080p: acima disso a placa nao sustenta.
QUALIDADE = {
    "economica": "bv*[height<=?480]+ba/best",
    "boa":       "bv*[height<=?720][vcodec^=avc1]+ba/bv*[height<=?720]+ba/best",
    "maxima":    ("bv*[height<=?1080][fps<=?30][vcodec^=avc1]+ba/"
                  "bv*[height<=?720][vcodec^=avc1]+ba/"
                  "bv*[height<=?720]+ba/best"),
}
# Chaves expostas na tela de Ajustes. As de 0/1 sao lidas pelo
# tarsila-chromium (funcao _pref); "qualidade" e lida aqui mesmo; "mobile" e
# lida pelo service worker da extensao, que pergunta a este host no arranque.
PADROES = {
    "qualidade": "boa",   # economica | boa | maxima
    "gpu": "1",
    "jitless": "1",
    "tierb": "1",
    "hwdec": "1",
    "cinema": "1",
    "mobile": "1",
}
LIGA_DESLIGA = [k for k in PADROES if k != "qualidade"]


def ler(chave):
    try:
        with open(os.path.join(CFG, chave), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return PADROES.get(chave, "")


def gravar(chave, valor):
    os.makedirs(CFG, exist_ok=True)
    with open(os.path.join(CFG, chave), "w", encoding="utf-8") as f:
        f.write(str(valor).strip() + "\n")


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


def abrir_no_mpv(url):
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "erro": "URL invalida"}
    fmt = QUALIDADE.get(ler("qualidade"), QUALIDADE["boa"])
    cmd = ["mpv", "--fs", "--hwdec=auto-safe", "--ytdl=yes",
           "--ytdl-format=" + fmt, "--no-terminal", "--osc=yes", url]
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
    acao = msg.get("acao", "cinema")
    try:
        if acao == "ler":
            responder({"ok": True, "valores": {k: ler(k) for k in PADROES}})
        elif acao == "gravar":
            for chave, valor in (msg.get("valores") or {}).items():
                if chave == "qualidade" and valor in QUALIDADE:
                    gravar("qualidade", valor)
                elif chave in LIGA_DESLIGA and str(valor) in ("0", "1"):
                    gravar(chave, valor)
            responder({"ok": True, "valores": {k: ler(k) for k in PADROES}})
        else:
            responder(abrir_no_mpv(msg.get("url", "")))
    except Exception as exc:
        responder({"ok": False, "erro": str(exc)})


if __name__ == "__main__":
    main()
