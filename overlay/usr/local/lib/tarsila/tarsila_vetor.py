#!/usr/bin/env python3
"""Acende e apaga o vetor de abertura, e diz quando o aplicativo pintou.

Este modulo e importado pelo tarsila-abrindo. Tudo aqui e a prova de falha:
o tarsila-abrindo esta no caminho de abertura de TODO aplicativo do sistema,
entao nenhuma falha daqui pode impedir um programa de abrir. Toda funcao
engole a propria excecao e devolve algo inofensivo.

O ciclo:

  1. reserva_vaga()  -> pergunta ao tarsila-vaga.py onde a janela vai nascer
  2. acende()        -> escreve a vaga no arquivo; o tarsila-tela-estados
                        (que ja esta rodando) mostra o desenho em milissegundos
  3. espera_pintar() -> XDamage: espera o conteudo do app ser desenhado
  4. apaga()         -> esvazia o arquivo; o desenho sai com fade

Por que XDamage e nao "a janela apareceu": medido nesta box, entre a janela
ser mapeada e o conteudo estar pintado passam de 0,6 a 1,7 s -- a janela
existe e esta VAZIA. Sair nesse momento devolveria ao usuario exatamente a
moldura vazia que motivou o pedido. O damage e o unico sinal que diz "isto
aqui foi desenhado", e nao depende de conhecer o aplicativo.
"""

import ctypes
import os
import select
import subprocess
import time
from ctypes import byref, c_int, c_long, c_ulong, c_void_p, Structure

RT = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
PEDIDO_VETOR = os.path.join(RT, "tarsila-vetor.txt")
TAMANHOS = os.path.expanduser("~/.config/tarsila/tamanhos.txt")
# Arquivo NOVO de proposito (04/08). O tamanhos.txt guardava outra grandeza --
# o minimo declarado -- e reaproveitar o nome faria os valores velhos, que sao
# lixo para este fim, passarem por medidas boas. Ver nascimento_conhecido().
NASCIMENTO = os.path.expanduser("~/.config/tarsila/nascimento.txt")

VAGA = "/usr/local/bin/tarsila-vaga.py"
PISO_ALTURA = 300      # janela no minimo declarado costuma ficar impraticavel
LARGURA_PADRAO = 420   # usados so quando o app ainda nao e conhecido
ALTURA_PADRAO = 320

# XDamage: 3 = XDamageReportNonEmpty -- um evento e depois silencio. E o modo
# mais barato; o bruto (0) manda um evento por retangulo redesenhado.
DAMAGE_NON_EMPTY = 3
SUBSTRUCTURE_NOTIFY = 1 << 19
PROPERTY_CHANGE = 1 << 22
MAP_NOTIFY = 19
PROPERTY_NOTIFY = 28


class _XEvent(Structure):
    _fields_ = [("pad", c_long * 24)]


class _XPropertyEvent(Structure):
    """Campos do PropertyNotify -- precisamos do atom que mudou.

    Sem olhar o atom, TODA propriedade alterada na raiz disparava uma
    consulta de lista de janelas (um "xprop -root" cada). Medido: isso fazia
    a versao nova custar MAIS que o polling que ela veio substituir --
    1,73 s de CPU contra 0,97 s. A raiz recebe muita propriedade que nao tem
    nada a ver com janela nova.
    """
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", c_int),
        ("display", c_void_p),
        ("window", c_ulong),
        ("atom", c_ulong),
        ("time", c_ulong),
        ("state", c_int),
    ]


class _XMapEvent(Structure):
    """Campos reais do MapNotify.

    Nao adianta contar posicoes no vetor de c_long: em 64 bits o campo 3 e o
    ponteiro do Display, nao a janela. Foi exatamente esse engano que fez o
    XDamageCreate receber um ponteiro no lugar de um id (BadDrawable) e --
    porque erro de X derruba o processo -- matou o tarsila-abrindo no meio,
    deixando o vetor aceso na tela. Declarando os campos, o ctypes cuida do
    alinhamento e o valor sai certo.
    """
    _fields_ = [
        ("type", c_int),
        ("serial", c_ulong),
        ("send_event", c_int),
        ("display", c_void_p),
        ("event", c_ulong),
        ("window", c_ulong),
        ("override_redirect", c_int),
    ]


# Erro de X mata o processo por padrao. Como este modulo roda dentro do
# tarsila-abrindo -- que abre TODOS os aplicativos do sistema --, um
# BadWindow numa janela que fechou no meio do caminho nao pode derrubar
# nada. O tratador engole o erro e a vida segue.
_TRATADOR = ctypes.CFUNCTYPE(c_int, c_void_p, c_void_p)


def _ignora_erro(_dpy, _ev):
    return 0


_GUARDA_TRATADOR = _TRATADOR(_ignora_erro)


# --------------------------------------------------------------- tamanhos
def chave_do_app(cmd):
    """Nome estavel para o aplicativo, a partir da linha de comando.

    O .desktop chama "tarsila-abrindo tarsila-uma-janela ajustes ... ", entao
    o primeiro argumento nem sempre e o programa. Pegamos o ultimo pedaco que
    parece nome de programa.
    """
    try:
        for parte in reversed(cmd):
            p = os.path.basename(parte.strip())
            if p and not p.startswith("-") and not p.startswith("%") \
               and not p.startswith("^"):
                return p
    except Exception:
        pass
    return "desconhecido"


def _linha_do_cache(chave):
    """A linha crua do cache para esta chave, ou None."""
    try:
        with open(NASCIMENTO, encoding="utf-8") as f:
            for linha in f:
                partes = linha.split()
                if partes and partes[0] == chave:
                    return partes
    except OSError:
        pass
    return None


def tem_vetor(chave):
    """Este aplicativo pode ganhar desenho?

    SO O QUE ESTA NA GRADE CURADA (/usr/share/tarsila/applications e
    /usr/share/tarsila/games). O cache e semeado pelo tarsila-aprender-janelas
    a partir dessas duas pastas e NUNCA ganha chave nova em tempo de execucao
    -- por isso "estar no cache" e o mesmo que "estar na grade".

    Tudo o mais abre sem desenho e sem regra de posicao, de proposito: um
    aplicativo que o sistema nao conhece nao tem tamanho nem classe confiaveis,
    e desenhar um retangulo inventado na frente dele e pior que nao desenhar.

    Ha ainda a condicao opcional (campo "se=" no cache): o desenho so vale se
    aquele arquivo existir. E como o Tarsila Email diz "so desenhe quando eu
    tiver conta configurada" -- sem ela ele abre o assistente, que e outra
    janela, de outro tamanho.
    """
    partes = _linha_do_cache(chave)
    if not partes:
        return False
    for campo in partes[4:]:
        if campo.startswith("se="):
            alvo = os.path.expanduser(campo[3:])
            if not os.path.exists(alvo):
                return False
    return True


def nascimento_conhecido(chave):
    """(largura, altura, classe) com que este app nasceu da ultima vez.

    POR QUE NAO E MAIS O MINIMO DECLARADO (corrigido em 04/08)
    ----------------------------------------------------------
    Antes guardavamos o minimo de WM_NORMAL_HINTS, argumentando que era o
    unico numero estavel. Estavel ele e -- mas nao e o tamanho com que a
    janela nasce, e sim o menor tamanho a que ela aceita ser encolhida. Para
    quase todo GTK isso e a barra de ferramentas e mais nada. O que estava
    gravado na TV:

        mousepad 405 79     xfce4-terminal 320 73     vlc 489 74
        qpdfview 331 60     tarsila-store 1008 111    thunar 352 141

    79 pixels de altura. Como a leitura ainda empurrava tudo para um piso de
    300, o desenho saia praticamente do mesmo tamanho para todo aplicativo --
    era esse o "vetor de tamanho unico".

    Agora guardamos a MOLDURA REAL medida no nascimento. Pela mesma razao o
    sistema parou de redimensionar a janela: ela nasce do tamanho que o
    proprio aplicativo pede (o "tamanho quente", que ele guardou da ultima
    sessao), e nosso papel e desenhar aquilo -- nao impor outra coisa.

    Continua havendo um limite honesto: na PRIMEIRA vez que um aplicativo
    abre nesta maquina nao ha o que saber, e cai no tamanho padrao.
    """
    try:
        with open(NASCIMENTO, encoding="utf-8") as f:
            for linha in f:
                partes = linha.split()
                if len(partes) >= 3 and partes[0] == chave:
                    classe = partes[3] if len(partes) >= 4 else ""
                    return int(partes[1]), int(partes[2]), classe
    except Exception:
        pass
    return None


def area_util():
    """(largura, altura) da area util -- a tela menos as barras.

    Lida do _NET_WORKAREA, que e o que o proprio gerenciador anuncia. Sem
    resposta, devolve (0, 0) e quem chama trata como "nao sei".
    """
    try:
        saida = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                               capture_output=True, text=True, timeout=3).stdout
        n = [int(p.strip()) for p in saida.split("=", 1)[1].split(",")[:4]]
        return n[2], n[3]
    except Exception:
        return 0, 0


def nasce_maximizado(larg, alt):
    """A janela ocupa praticamente a area util inteira?

    Regra por MEDIDA, nao por nome de aplicativo. Quem nasce maximizado nao
    usa vaga -- ele toma a tela -- e portanto nao deve ter desenho nenhum: o
    vetor viraria um retangulo do tamanho da tela, que e o oposto de avisar
    onde a janela vai aparecer.

    Medido na TV: area util 1366x744; o Chromium nasce 1366x744 (100% x 100%)
    e a Agenda nasce 1188x744 (87% x 100%). Por isso a conta exige as DUAS
    dimensoes cheias: a Agenda e alta, nao maximizada, e continua com vaga.
    """
    au_l, au_a = area_util()
    if not au_l or not au_a:
        return False
    return larg >= au_l * 0.97 and alt >= au_a * 0.97


def guarda_nascimento(chave, larg, alt, classe="", permitir_novo=False):
    """Anota como este app nasceu, para a proxima abertura acertar.

    Guardar lixo e pior que nao guardar: um tamanho de zero faria a vaga da
    proxima vez ser calculada para uma janela inexistente.

    NAO CRIA CHAVE NOVA por padrao. Quem semeia o cache e o
    tarsila-aprender-janelas, a partir das pastas curadas; aqui so atualizamos
    o que ja esta la. Sem isso, qualquer programa aberto uma vez pelo
    tarsila-abrindo entrava na lista e passava a ganhar desenho -- justamente
    o contrario da regra combinada.

    Entrada marcada como "declarado" tambem nao e sobrescrita: quando o
    proprio aplicativo diz o tamanho com que nasce, a declaracao vale mais que
    a nossa medicao, que sempre fica uma geracao atrasada.
    """
    if not larg or not alt or larg < 120 or alt < 90:
        return
    atual = _linha_do_cache(chave)
    if atual is None and not permitir_novo:
        return
    if atual and "declarado" in atual[4:]:
        return
    # Nasce maximizado: fica gravado como "0 0", que e o combinado para
    # "conhecido, e sem vaga". Assim ele nao ganha desenho nem regra de
    # posicao -- e continua conhecido, o que evita reaprender toda vez.
    if nasce_maximizado(larg, alt):
        larg, alt = 0, 0
    try:
        antigos = {}
        if os.path.exists(NASCIMENTO):
            with open(NASCIMENTO, encoding="utf-8") as f:
                for linha in f:
                    partes = linha.split(None, 1)
                    if len(partes) == 2:
                        antigos[partes[0]] = partes[1].strip()
        # preserva os campos extras (se=..., declarado) da linha antiga
        extras = " ".join(atual[4:]) if atual else ""
        antigos[chave] = ("%d %d %s %s" % (larg, alt, classe, extras)).strip()
        os.makedirs(os.path.dirname(NASCIMENTO), exist_ok=True)
        tmp = NASCIMENTO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for n, r in sorted(antigos.items()):
                f.write("%s %s\n" % (n, r))
        os.replace(tmp, NASCIMENTO)
    except Exception:
        pass


# ------------------------------------------------------------------ vaga
def reserva_vaga(chave, ids_vivos=None):
    """(x, y, largura, altura, numero) onde a janela vai nascer, ou None.

    Sem conta pesada: o tamanho vem do cache de nascimento e a vaga livre vem
    do NOSSO registro, conferido contra a lista de janelas vivas que quem
    chama ja tem na mao. Duas leituras de arquivo pequeno -- e o desenho pode
    subir na hora.

    None quer dizer "sem vaga": as 7 estao ocupadas e o Openbox decide
    sozinho -- nesse caso nao ha vetor, porque nao saberiamos onde desenhar.

    O calculo e IMPORTADO, nao chamado como subprocesso. Medido: rodar o
    tarsila-vaga.py como programa custava 1573 ms, dos quais 394 ms eram so
    ligar um interpretador Python a mais -- e quem chama aqui ja e Python.
    Se o modulo nao estiver instalado, cai no subprocesso.
    """
    try:
        conhecido = nascimento_conhecido(chave)
        if conhecido:
            larg, alt = conhecido[0], conhecido[1]
            # "0 0" = nasce maximizado. Sem vaga, e portanto sem desenho e
            # sem regra de posicao: quem toma a tela nao tem onde ser posto.
            if not larg or not alt:
                return None
            # A mesma pergunta na LEITURA, e nao so na gravacao: caches
            # antigos guardaram o tamanho cheio como se fosse tamanho normal
            # (o Chromium estava la como 1366x744, e o desenho dele virava a
            # tela inteira). Assim eles se corrigem sem precisar reaprender.
            if nasce_maximizado(larg, alt):
                return None
        else:
            larg, alt = LARGURA_PADRAO, ALTURA_PADRAO
        try:
            import tarsila_vaga
            r = tarsila_vaga.escolhe(larg, alt, ids_vivos)
            if r is None:
                return None
            return r[0], r[1], larg, alt, r[2]
        except ImportError:
            pass
        r = subprocess.run([VAGA, str(larg), str(alt)],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
        x, y, n = (int(v) for v in r.stdout.split())
        return x, y, larg, alt, n
    except Exception:
        return None


def extents_do_tema():
    """(esquerda, topo) da decoracao. Lidos de uma janela decorada qualquer.

    Servem para compensar o set_window_geometry do devilspie2, que coloca a
    moldura em (x + esquerda, y + topo) em vez de (x, y). A compensacao foi
    tentada dentro do proprio Lua, mas as chamadas de geometria de la abortam
    o script naquele ponto -- e o efeito colateral era nenhuma geometria ser
    aplicada. Aqui a leitura e segura.

    O tema e o mesmo para todas as janelas decoradas, entao qualquer uma
    serve de referencia.
    """
    try:
        saida = subprocess.run(["wmctrl", "-l"], capture_output=True,
                               text=True, timeout=3).stdout
        for linha in saida.splitlines():
            wid = linha.split(None, 1)[0]
            ext = subprocess.run(["xprop", "-id", wid, "_NET_FRAME_EXTENTS"],
                                 capture_output=True, text=True,
                                 timeout=3).stdout
            if "=" not in ext:
                continue
            n = [int(p.strip()) for p in ext.split("=", 1)[1].split(",")]
            # Janela decorada tem barra de titulo; a sem decoracao da 0.
            if len(n) >= 3 and n[2] > 0:
                return n[0], n[2]
    except Exception:
        pass
    return 0, 0


def acende(vaga):
    """Pede o desenho na vaga. Quem desenha e o tarsila-tela-estados.

    Formato do arquivo: "pid x y w h". O PID identifica o processo dono;
    so ele pode apagar esta entrada. Isto evita que duas aberturas
    simultaneas pisem no desenho uma da outra (07/08)."""
    if not vaga:
        return
    try:
        with open(PEDIDO_VETOR, "w", encoding="utf-8") as f:
            f.write("%d %d %d %d %d\n" % (os.getpid(), vaga[0], vaga[1], vaga[2], vaga[3]))
    except Exception:
        pass


def aplica_vaga(wid, vaga):
    """Poe a janela na vaga -- CAMINHO DE RESERVA, nao o principal (04/08).

    O caminho principal agora e o tarsila_openbox: a vaga vira regra no
    rc.xml ANTES de o aplicativo subir, e a janela nasce no lugar. Esta
    funcao so roda quando aquele caminho nao pode ser usado -- primeira
    abertura do app (a classe ainda e desconhecida), duas janelas abrindo ao
    mesmo tempo, ou rc.xml fora do lugar.

    Ela move DEPOIS de a janela existir, entao o salto continua visivel aqui.
    E o preco de ainda assim acertar a posicao, em vez de deixar a janela
    onde calhou.

    NAO redimensiona mais. Antes havia um "xdotool windowsize" que forcava a
    janela ao tamanho do cache -- e o cache guardava o minimo declarado, algo
    como 405x79 no Mousepad. Ou seja: o sistema pegava uma janela que nascia
    no tamanho certo e a espremia. Quem manda no tamanho e o aplicativo.

    Quem posiciona e ESTE script, e nao o devilspie2, por dois motivos.

    O primeiro e pratico: passar a vaga para o Lua nao funcionou. O
    set_window_geometry de la coloca a moldura em (x + borda, y + titulo) em
    vez de (x, y), e a tentativa de corrigir isso lendo a geometria dentro do
    proprio Lua abortava o script -- resultado, NENHUMA geometria era
    aplicada e todo aplicativo caia no posicionamento do Openbox.

    O segundo e historico, e esta escrito no cabecalho do floating.lua: ja
    houve um encaixe em slots forcado por Lua, removido em 2026-07-19 porque
    desenhava janelas fora da tela, com o aviso de nao reintroduzir. Aqui a
    conta e verificavel: o windowmove do xdotool trabalha na MOLDURA, que e o
    mesmo referencial das vagas -- medido, pedindo 25,49 a moldura vai para
    25,49, sem compensacao nenhuma.
    """
    if not wid or not vaga:
        return
    try:
        x, y, _larg, _alt = vaga
        subprocess.run(["xdotool", "windowmove", str(wid), str(x), str(y)],
                       capture_output=True, timeout=4)
    except Exception:
        pass


def medida_de_nascimento(wid):
    """(largura, altura, classe) da janela recem-nascida, ou None.

    Medimos a MOLDURA, nao a area util: e o mesmo referencial das vagas e do
    desenho. O _NET_FRAME_EXTENTS da a espessura da decoracao desta janela --
    ler por janela, e nao um valor do tema, cobre as sem decoracao.

    Roda depois de o aplicativo ja estar na tela, fora do caminho critico.
    """
    if not wid:
        return None
    try:
        g = subprocess.run(["xdotool", "getwindowgeometry", "--shell", str(wid)],
                           capture_output=True, text=True, timeout=4).stdout
        larg = alt = 0
        for linha in g.splitlines():
            chave, _, valor = linha.partition("=")
            if chave == "WIDTH":
                larg = int(valor)
            elif chave == "HEIGHT":
                alt = int(valor)
        if not larg or not alt:
            return None

        ext = subprocess.run(["xprop", "-id", str(wid), "_NET_FRAME_EXTENTS"],
                             capture_output=True, text=True, timeout=4).stdout
        if "=" in ext:
            try:
                e = [int(p.strip()) for p in ext.split("=", 1)[1].split(",")]
                if len(e) >= 4:
                    larg += e[0] + e[1]      # esquerda + direita
                    alt += e[2] + e[3]       # topo + base
            except ValueError:
                pass

        classe = ""
        cl = subprocess.run(["xprop", "-id", str(wid), "WM_CLASS"],
                            capture_output=True, text=True, timeout=4).stdout
        if "=" in cl:
            # WM_CLASS(STRING) = "chromium", "Chromium" -- a classe e a
            # segunda, que e justamente a que o Openbox casa nas regras.
            aspas = [p.strip().strip('"') for p in cl.split("=", 1)[1].split(",")]
            if len(aspas) >= 2 and aspas[1]:
                classe = aspas[1]
            elif aspas and aspas[0]:
                classe = aspas[0]
        return larg, alt, classe
    except Exception:
        return None


def apaga():
    """So limpa se o PID do arquivo for o deste processo.

    Sem esta guarda, a abertura A escreve o vetor, a abertura B sobrescreve,
    e quando A termina de pintar seu apaga() mata o vetor de B -- que ainda
    esta abrindo. Com o token de PID, cada processo so responde pelo seu
    proprio desenho (07/08)."""
    try:
        with open(PEDIDO_VETOR, "r", encoding="utf-8") as f:
            conteudo = f.read().split()
        if len(conteudo) >= 5 and conteudo[0] == str(os.getpid()):
            with open(PEDIDO_VETOR, "w", encoding="utf-8") as f:
                f.write("")
    except Exception:
        pass



# ---------------------------------------------------------------- damage
class Observador:
    """Espera a janela nova aparecer e o conteudo dela ser pintado."""

    def __init__(self):
        self.ok = False
        try:
            self.x11 = ctypes.CDLL("libX11.so.6")
            self.xdmg = ctypes.CDLL("libXdamage.so.1")
            self.x11.XSetErrorHandler(_GUARDA_TRATADOR)
            self.x11.XOpenDisplay.restype = c_void_p
            self.dpy = self.x11.XOpenDisplay(None)
            if not self.dpy:
                return
            self.x11.XDefaultRootWindow.restype = c_ulong
            self.x11.XDefaultRootWindow.argtypes = [c_void_p]
            self.raiz = self.x11.XDefaultRootWindow(c_void_p(self.dpy))
            ev, err = c_int(), c_int()
            if not self.xdmg.XDamageQueryExtension(c_void_p(self.dpy),
                                                   byref(ev), byref(err)):
                return
            self.ev_base = ev.value
            self.xdmg.XDamageCreate.restype = c_ulong
            self.x11.XSelectInput(
                c_void_p(self.dpy), c_ulong(self.raiz),
                c_long(SUBSTRUCTURE_NOTIFY | PROPERTY_CHANGE))
            # Atom da lista de janelas: so ele nos interessa entre as muitas
            # propriedades que mudam na raiz.
            self.x11.XInternAtom.restype = c_ulong
            self.atom_lista = self.x11.XInternAtom(
                c_void_p(self.dpy), b"_NET_CLIENT_LIST", False)
            self.x11.XFlush(c_void_p(self.dpy))
            self.ok = True
        except Exception:
            self.ok = False

    def _e_janela_real(self, wid):
        """A janela do aplicativo, e nao uma auxiliar do toolkit.

        Todo app GTK mapeia junto uma janelinha de 10x10 (e outras menores).
        Sem este filtro o damage era criado NELA: como ela pinta na hora, o
        vetor sumia em ~1,9 s -- antes de a janela de verdade sequer nascer
        (medido: mousepad so aparece aos ~2,4 s) -- e o tamanho minimo lido
        vinha vazio, entao nada era aprendido.

        Usa XGetGeometry direto, sem abrir processo.
        """
        try:
            raiz = c_ulong()
            x = c_int()
            y = c_int()
            larg = ctypes.c_uint()
            alt = ctypes.c_uint()
            borda = ctypes.c_uint()
            prof = ctypes.c_uint()
            ok = self.x11.XGetGeometry(
                c_void_p(self.dpy), c_ulong(wid), byref(raiz),
                byref(x), byref(y), byref(larg), byref(alt),
                byref(borda), byref(prof))
            if not ok:
                return False
            return larg.value >= 150 and alt.value >= 100
        except Exception:
            return False

    def _clientes(self):
        """Janelas de aplicativo segundo o gerenciador (_NET_CLIENT_LIST)."""
        saida = set()
        try:
            texto = subprocess.run(
                ["xprop", "-root", "_NET_CLIENT_LIST"],
                capture_output=True, text=True, timeout=3).stdout
            _, _, lista = texto.partition("#")
            for p in lista.split(","):
                p = p.strip()
                if p:
                    try:
                        saida.add(int(p, 16))
                    except ValueError:
                        pass
        except Exception:
            pass
        return saida

    def cliente_de(self, moldura):
        """Desce da moldura do Openbox para a janela do aplicativo.

        Escutando a raiz, os MapNotify que chegam sao das MOLDURAS que o
        gerenciador cria, nao das janelas dos aplicativos. Isso estragava
        duas coisas: o damage era criado na moldura -- que pinta a decoracao
        de imediato, apagando o vetor aos ~1,5 s, antes de o conteudo existir
        -- e o WM_NORMAL_HINTS lido vinha vazio, porque ele mora no cliente.

        Devolve o maior filho (o cliente ocupa quase toda a moldura).
        """
        try:
            raiz = c_ulong()
            pai = c_ulong()
            filhos = ctypes.POINTER(c_ulong)()
            n = ctypes.c_uint()
            ok = self.x11.XQueryTree(c_void_p(self.dpy), c_ulong(moldura),
                                     byref(raiz), byref(pai),
                                     byref(filhos), byref(n))
            if not ok or not n.value:
                return moldura
            melhor, maior = moldura, 0
            for i in range(n.value):
                f = filhos[i]
                area = self._area(f)
                if area > maior:
                    melhor, maior = f, area
            try:
                self.x11.XFree(filhos)
            except Exception:
                pass
            return melhor
        except Exception:
            return moldura

    def _area(self, wid):
        try:
            raiz = c_ulong()
            x = c_int()
            y = c_int()
            larg = ctypes.c_uint()
            alt = ctypes.c_uint()
            borda = ctypes.c_uint()
            prof = ctypes.c_uint()
            if not self.x11.XGetGeometry(
                    c_void_p(self.dpy), c_ulong(wid), byref(raiz),
                    byref(x), byref(y), byref(larg), byref(alt),
                    byref(borda), byref(prof)):
                return 0
            return larg.value * alt.value
        except Exception:
            return 0

    def espera_pintar(self, limite, ja_existiam, ao_achar=None):
        """Bloqueia ate o conteudo da janela nova ser desenhado.

        ao_achar(wid) e chamado no INSTANTE em que a janela e descoberta --
        antes de ela pintar. E ali que a vaga e aplicada: mexer na geometria
        depois da pintura daria um salto visivel; feito antes, o usuario so
        ve a janela ja no lugar certo, ainda por baixo do vetor.

        Devolve o id da janela nova (para ler o tamanho minimo dela) ou None.
        """
        if not self.ok:
            time.sleep(min(limite, 2.0))
            return None
        alvo = None
        dam = None
        ev = _XEvent()
        fim = time.time() + limite
        # Espera BLOQUEANTE no descritor da conexao com o X, em vez de
        # perguntar "chegou evento?" de 4 em 4 ms.
        #
        # Medido: o laco com XPending + sleep(0,004) dava ~1500 voltas numa
        # abertura de 6 s e fazia esta versao custar 2,03 s de CPU contra
        # 1,08 s do polling antigo que ela veio substituir -- ou seja, o
        # "orientado a evento" gastava o DOBRO. Com select o processo fica
        # realmente parado ate o X falar.
        try:
            fd = self.x11.XConnectionNumber(c_void_p(self.dpy))
        except Exception:
            fd = -1
        try:
            while time.time() < fim:
                if not self.x11.XPending(c_void_p(self.dpy)):
                    if fd >= 0:
                        select.select([fd], [], [], max(0.0, fim - time.time()))
                    else:
                        time.sleep(0.05)
                    continue
                self.x11.XNextEvent(c_void_p(self.dpy), byref(ev))
                tipo = ev.pad[0] & 0x7F

                # A janela do aplicativo e descoberta pela LISTA OFICIAL do
                # gerenciador (_NET_CLIENT_LIST), nao pelo MapNotify.
                #
                # Motivo: escutando a raiz, os MapNotify que chegam sao das
                # MOLDURAS que o Openbox cria. Descer a arvore ate o cliente
                # na mao levou a janelas intermediarias -- o damage nao
                # disparava e o WM_NORMAL_HINTS vinha vazio. A lista do
                # gerenciador ja diz exatamente quais sao as janelas dos
                # aplicativos, sem adivinhacao. E ela muda por EVENTO
                # (PropertyNotify na raiz), nao por polling.
                # Só consulta a lista quando o evento diz que ELA mudou.
                # Sem este filtro, qualquer propriedade da raiz abria um
                # "xprop" -- era o que fazia esta versao custar mais CPU que
                # o polling antigo.
                interessa = False
                if tipo == PROPERTY_NOTIFY:
                    prop = ctypes.cast(
                        byref(ev), ctypes.POINTER(_XPropertyEvent)).contents
                    interessa = (prop.atom == self.atom_lista)
                elif tipo == MAP_NOTIFY:
                    interessa = True

                if alvo is None and interessa:
                    novas = self._clientes() - ja_existiam
                    if novas:
                        alvo = max(novas, key=self._area)
                        if ao_achar is not None:
                            try:
                                ao_achar(alvo)
                            except Exception:
                                pass
                        try:
                            dam = self.xdmg.XDamageCreate(
                                c_void_p(self.dpy), c_ulong(alvo),
                                c_int(DAMAGE_NON_EMPTY))
                            self.x11.XFlush(c_void_p(self.dpy))
                        except Exception:
                            return alvo       # sem damage: ja pode sair
                elif alvo is not None and tipo == self.ev_base:
                    return alvo               # pintou
            return alvo
        except Exception:
            return alvo
        finally:
            if dam:
                try:
                    self.xdmg.XDamageDestroy(c_void_p(self.dpy), c_ulong(dam))
                except Exception:
                    pass

    # minimo_declarado() foi retirado em 04/08. Ele lia o "minimum size" do
    # WM_NORMAL_HINTS e era a fonte do tamanho do desenho -- mas esse numero
    # e o menor tamanho a que a janela aceita ser encolhida, nao o tamanho com
    # que ela nasce. Ver nascimento_conhecido(). Quem mede agora e
    # medida_de_nascimento(), que le a moldura de verdade.

    def fecha(self):
        try:
            self.x11.XCloseDisplay(c_void_p(self.dpy))
        except Exception:
            pass
