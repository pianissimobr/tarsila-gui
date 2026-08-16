#!/usr/bin/env python3
"""Onde a proxima janela vai nascer -- as "vagas" da area de trabalho.

Por que isto existe: o usuario queria um desenho (vetor) aparecendo no lugar
da janela ANTES de ela abrir. Isso so e possivel se soubermos a posicao de
antemao -- e nao ha como saber: quem escolhe a posicao e o Openbox, com a
politica Smart, no instante do MapRequest, olhando o que ja esta na tela.
Medido: a decisao sai ~16ms antes de a janela aparecer.

A saida foi inverter a pergunta: em vez de ADIVINHAR onde o Openbox poria,
nos DITAMOS. Este script decide a vaga, o devilspie2 forca a janela para ela
e o vetor desenha exatamente ali. Nada de previsao.

AS VAGAS (a regra e do usuario):

  1  25px da esquerda,  25px abaixo da barra
  2  25px da direita,   25px abaixo da barra
  3  60px da esquerda,  25px acima do Dock
  4  60px da direita,   25px acima do Dock
  5  centro da tela
  6  slot 5 deslocado +15/+15
  7  slot 6 deslocado +15/+15
  8+ ninguem: o Openbox decide sozinho e nos calamos

Os slots 3 e 4 foram ancorados 25px ACIMA DO DOCK, e nao "na metade da tela
para baixo" como pensado no inicio: com o topo em y=384 uma janela de 352 de
altura terminaria em 736, atras do Dock (que comeca em 689). Ancorando pela
base o encaixe fecha sempre, e fica simetrico com os 25px de folga da barra.

OCUPACAO: nao guardamos "app X esta na vaga N" em lugar nenhum. A ocupacao e
LIDA das janelas abertas a cada chamada -- para cada janela viva, calculamos
de qual vaga aquela posicao seria e marcamos como ocupada. Assim, quem fechou
libera a vaga sem precisar avisar ninguem, e um cache nunca fica mentindo
sobre a realidade. Fechou a vaga 2 com 5 apps abertos? A proxima abertura
ocupa a 2, porque a 2 esta livre de fato.

Uso:  tarsila-vaga.py <largura> <altura>     -> imprime "x y vaga" ou nada
      tarsila-vaga.py --mapa                 -> mostra as vagas e quem ocupa
"""

import os
import subprocess
import sys

FOLGA_BARRA = 25      # respiro abaixo da barra de cima
FOLGA_DOCK = 25       # respiro acima do Dock
MARGEM_LADO = 25      # vagas 1 e 2
MARGEM_LADO_BAIXO = 60  # vagas 3 e 4
PASSO_ESCADA = 15     # vagas 6, 7
ULTIMA_VAGA = 7       # da 8 em diante o Openbox assume
TOLERANCIA = 10       # px para considerar que uma janela "esta" numa vaga

# Classes que nao entram no sistema de vagas: as tres telas Tarsila que ja
# nascem em posicao propria combinada, e o Chromium, que nasce maximizado.
FORA_DO_SISTEMA = ("tarsila-config", "tarsila-lixeira", "tarsila-appfinder",
                   "chromium", "chromium-browser", "plank",
                   "tarsila-tela-estados", "yad", "tarsila-barra-menu")


def _roda(cmd, tempo=4):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=tempo).stdout
    except Exception:
        return ""


# Leituras que NAO mudam durante uma abertura, guardadas por execucao.
#
# Medido em 04/08/2026, perfilando o tarsila-abrindo: a escolha da vaga
# custava 1770 ms -- mais que o proprio aplicativo demorava para abrir. A
# causa: ocupadas() chama vagas(w, h) DENTRO do laco, uma vez por janela na
# tela, e cada vagas() refazia tela() e topo_do_dock(), que sao subprocessos
# xdotool. Com N janelas abertas eram N x (2 + janelas do Plank) processos
# para responder duas perguntas cuja resposta e sempre a mesma.
#
# Este processo vive alguns segundos; a tela nao muda de tamanho e a Dock nao
# muda de lugar nesse intervalo. Guardar e correto, nao e atalho.
_LEMBRADO = {}


def tela():
    """(largura, altura) da tela."""
    if "tela" in _LEMBRADO:
        return _LEMBRADO["tela"]
    saida = _roda(["xdotool", "getdisplaygeometry"]).split()
    r = (int(saida[0]), int(saida[1])) if len(saida) >= 2 else (1366, 768)
    _LEMBRADO["tela"] = r
    return r


def altura_da_barra():
    if "barra" in _LEMBRADO:
        return _LEMBRADO["barra"]
    _LEMBRADO["barra"] = _altura_da_barra()
    return _LEMBRADO["barra"]


def _altura_da_barra():
    try:
        import os
        caminho = os.path.expanduser("~/.config/tarsila/bar-height")
        with open(caminho, encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return 24


def topo_do_dock(alt_tela):
    """Onde o Dock comeca. Se nao houver Dock, o fim da tela.

    O _NET_WORKAREA NAO serve aqui: o Openbox nao reserva espaco para o
    Plank (medido: workarea vai ate 768 com o Dock em 689). Por isso lemos a
    janela do Plank direto.
    """
    if "dock" in _LEMBRADO:
        return _LEMBRADO["dock"]
    _LEMBRADO["dock"] = _topo_do_dock(alt_tela)
    return _LEMBRADO["dock"]


def _topo_do_dock(alt_tela):
    """Le a Dock da MESMA listagem que janelas_abertas() usa."""
    for linha in _lista_janelas():
        partes = linha.split(None, 8)
        if len(partes) < 7 or "plank" not in partes[6].lower():
            continue
        try:
            y, larg = int(partes[3]), int(partes[4])
        except ValueError:
            continue
        # A Dock e larga; as outras janelas do Plank sao pequenas.
        if larg > alt_tela // 2 and 0 < y < alt_tela:
            return y
    return alt_tela


def vagas(w, h):
    """As 7 vagas para uma janela w x h. Lista de (numero, x, y)."""
    lt, at = tela()
    barra = altura_da_barra()
    dock = topo_do_dock(at)
    cx = (lt - w) // 2
    cy = barra + (dock - barra - h) // 2
    return [
        (1, MARGEM_LADO,                 barra + FOLGA_BARRA),
        (2, lt - MARGEM_LADO - w,        barra + FOLGA_BARRA),
        (3, MARGEM_LADO_BAIXO,           dock - FOLGA_DOCK - h),
        (4, lt - MARGEM_LADO_BAIXO - w,  dock - FOLGA_DOCK - h),
        (5, cx,                          cy),
        (6, cx + PASSO_ESCADA,           cy + PASSO_ESCADA),
        (7, cx + 2 * PASSO_ESCADA,       cy + 2 * PASSO_ESCADA),
    ]


def geometria_da_moldura(wid):
    """(x, y, largura, altura) da MOLDURA -- o mesmo referencial do windowmove.

    Cuidado que custou um teste: as tres ferramentas falam referenciais
    diferentes. Pedindo "windowmove 25 49" numa janela com extensoes
    (4, 4, 32, 5), o resultado foi:

        xdotool getwindowgeometry -> 33, 113   (soma a moldura de novo: inutil)
        xwininfo absoluto         -> 29,  81   (posicao do CLIENTE)
        moldura de verdade        -> 25,  49   = cliente menos (esquerda, topo)

    Entao a unica conta que fecha e xwininfo menos _NET_FRAME_EXTENTS, e e
    ela que precisa bater com a vaga -- porque a vaga sera aplicada com esse
    mesmo referencial.
    """
    info = _roda(["xwininfo", "-id", wid])
    if not info:
        return None
    dados = {}
    for linha in info.splitlines():
        linha = linha.strip()
        for rotulo, chave in (("Absolute upper-left X:", "x"),
                              ("Absolute upper-left Y:", "y"),
                              ("Width:", "w"), ("Height:", "h")):
            if linha.startswith(rotulo):
                try:
                    dados[chave] = int(linha.split()[-1])
                except ValueError:
                    pass
    if len(dados) < 4:
        return None

    esq = topo = 0
    ext = _roda(["xprop", "-id", wid, "_NET_FRAME_EXTENTS"])
    if "=" in ext:
        try:
            n = [int(p.strip()) for p in ext.split("=", 1)[1].split(",")]
            if len(n) >= 3:
                esq, topo = n[0], n[2]
        except ValueError:
            pass
    return dados["x"] - esq, dados["y"] - topo, dados["w"], dados["h"]


def janelas_abertas():
    """[(x, y, largura, altura)] das janelas de aplicativo, em moldura.

    DUAS leituras no total, nao duas por janela (corrigido em 04/08).
    Antes era um "wmctrl -lx" mais um "xwininfo" e um "xprop" POR JANELA --
    1 + 2N subprocessos. Com quatro janelas na tela isso era nove processos
    so para escolher onde a proxima ia nascer, e respondia por boa parte dos
    209 ms que a escolha da vaga ainda custava.

    Agora: "wmctrl -lGx" traz id, classe e geometria de todas de uma vez, e as
    extensoes da moldura sao lidas UMA vez -- elas vem do tema, entao valem
    para qualquer janela decorada. Medido nesta box: 4, 4, 32, 5.

    Limite conhecido: janela SEM decoracao recebe a mesma correcao e sai
    deslocada. Na pratica nao pesa, porque as janelas sem decoracao daqui
    (polybar, Plank, o proprio vetor, o Chromium) estao todas em
    FORA_DO_SISTEMA e nem chegam a ser medidas.
    """
    brutas = []
    for linha in _lista_janelas():
        partes = linha.split(None, 8)
        if len(partes) < 7:
            continue
        wid, classe = partes[0], partes[6].lower()
        if any(p in classe for p in FORA_DO_SISTEMA):
            continue
        try:
            brutas.append((wid, int(partes[2]), int(partes[3]),
                           int(partes[4]), int(partes[5])))
        except ValueError:
            continue
    if not brutas:
        return []

    esq, topo, dir_, base = _extensoes(brutas[0][0])
    return [(x - esq, y - topo, w + esq + dir_, h + topo + base)
            for _wid, x, y, w, h in brutas]


def _lista_janelas():
    """Saida do "wmctrl -lGx", lida UMA vez por execucao.

    Ela serve a dois clientes: janelas_abertas() e topo_do_dock(). Antes cada
    um fazia a propria leitura -- e a do Dock era a pior de todas, porque
    usava "xdotool search --class plank", que varre a arvore inteira de
    janelas do X. Medido em 04/08: 149 ms so para descobrir onde a Dock
    comeca, contra 20 ms do wmctrl que ja estava sendo chamado do lado.
    """
    if "wmctrl" not in _LEMBRADO:
        _LEMBRADO["wmctrl"] = _roda(["wmctrl", "-lGx"]).splitlines()
    return _LEMBRADO["wmctrl"]


def _extensoes(wid):
    """(esquerda, topo, direita, base) da decoracao, lidas uma vez."""
    ext = _roda(["xprop", "-id", wid, "_NET_FRAME_EXTENTS"])
    if "=" in ext:
        try:
            n = [int(p.strip()) for p in ext.split("=", 1)[1].split(",")]
            if len(n) >= 4:
                return n[0], n[2], n[1], n[3]   # esq, topo, dir, base
        except ValueError:
            pass
    return 0, 0, 0, 0


REGISTRO = os.path.expanduser("~/.config/tarsila/vagas.txt")


def ocupadas_registradas(ids_vivos):
    """Vagas tomadas, pelo NOSSO registro -- caminho rapido.

    Quem atribui as vagas somos nos, entao nos sabemos quem esta em qual sem
    perguntar nada ao X. O registro guarda "numero id-da-janela"; uma linha so
    vale enquanto aquela janela existir, e a lista de janelas vivas ja e lida
    de graca pelo tarsila-abrindo (o _NET_CLIENT_LIST que ele pega para saber
    qual janela e nova).

    Por que isto importa: a versao que lia da tela custava ~200 ms por
    abertura -- ela varria as janelas, media a moldura de cada uma e testava
    contra as sete vagas, tudo para redescobrir o que ja estava decidido. Aqui
    sao duas leituras de arquivo pequeno.

    Linha cuja janela morreu e simplesmente ignorada: a vaga volta a ficar
    livre sozinha, sem ninguem precisar limpar nada.
    """
    tomadas = set()
    vivos_int = set()
    for w in ids_vivos:
        try:
            vivos_int.add(int(w, 16))
        except (ValueError, TypeError):
            pass
    try:
        with open(REGISTRO, encoding="utf-8") as f:
            for linha in f:
                partes = linha.split()
                if len(partes) >= 2:
                    try:
                        if int(partes[1], 16) in vivos_int:
                            tomadas.add(int(partes[0]))
                    except (ValueError, TypeError):
                        pass
    except OSError:
        pass
    return tomadas


def registra(numero, wid):
    """Anota que a vaga <numero> passou a ser da janela <wid>."""
    if not numero or not wid:
        return
    try:
        wid = "0x%08x" % int(wid) if str(wid).isdigit() else str(wid)
        linhas = []
        try:
            with open(REGISTRO, encoding="utf-8") as f:
                for linha in f:
                    partes = linha.split()
                    # tira a linha antiga desta vaga e a desta janela
                    if len(partes) >= 2 and (partes[0] == str(numero)
                                             or partes[1] == wid):
                        continue
                    if partes:
                        linhas.append(linha.rstrip("\n"))
        except OSError:
            pass
        linhas.append("%d %s" % (numero, wid))
        os.makedirs(os.path.dirname(REGISTRO), exist_ok=True)
        tmp = REGISTRO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas[-20:]) + "\n")
        os.replace(tmp, REGISTRO)
    except Exception:
        pass


def ocupadas():
    """Numeros das vagas ocupadas, LENDO A TELA -- caminho lento.

    Continua existindo para o "--mapa" e como rede de seguranca: se o registro
    se perder, esta leitura reconstroi a verdade a partir do que esta na tela.

    Para cada janela viva perguntamos: com o TAMANHO DELA, em que vaga essa
    posicao cairia? Se bater, a vaga esta ocupada.
    """
    tomadas = set()
    for x, y, w, h in janelas_abertas():
        for numero, vx, vy in vagas(w, h):
            if abs(x - vx) <= TOLERANCIA and abs(y - vy) <= TOLERANCIA:
                tomadas.add(numero)
                break
    return tomadas


def escolhe(w, h, ids_vivos=None):
    """(x, y, numero) da menor vaga livre, ou None se todas cheias.

    Com ids_vivos, usa o registro (rapido). Sem, le da tela (lento)."""
    tomadas = (ocupadas_registradas(ids_vivos) if ids_vivos is not None
               else ocupadas())
    for numero, x, y in vagas(w, h):
        if numero not in tomadas:
            return x, y, numero
    return None


def main():
    if "--mapa" in sys.argv:
        tomadas = ocupadas()
        print("vaga  ocupada")
        for numero, x, y in vagas(400, 300):
            print("  %d   %s   (exemplo 400x300: +%d+%d)"
                  % (numero, "SIM" if numero in tomadas else "livre", x, y))
        return 0

    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    try:
        w, h = int(sys.argv[1]), int(sys.argv[2])
    except ValueError:
        return 2

    r = escolhe(w, h)
    if r is None:
        return 1          # sem vaga: quem chamou deixa o Openbox decidir
    print("%d %d %d" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
