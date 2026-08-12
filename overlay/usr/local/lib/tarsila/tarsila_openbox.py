#!/usr/bin/env python3
"""Diz ao Openbox ONDE a proxima janela deve nascer, antes de ela existir.

Por que isto existe
-------------------
Ate aqui a vaga era aplicada DEPOIS: esperavamos a janela aparecer e
mandavamos um "xdotool windowmove". O comentario no codigo antigo dizia que
isso acontecia "antes de ela pintar", e nao acontece. A janela so vira
evento para nos no MapNotify, e MapNotify chega DEPOIS de o Openbox ja ter
escolhido a posicao e colocado a janela na tela. Somando o custo de subir um
processo novo (xdotool), da tempo de sobra para o compositor pintar. O
usuario ve a janela nascer num lugar e pular para outro.

Essa corrida nao da para ganhar corrigindo depois -- so nao entrando nela.
Quem decide onde a janela nasce e o gerenciador de janelas, e o Openbox
aceita ser mandado: as regras <application> do rc.xml valem NO NASCIMENTO, e
<position force="yes"> vence a politica de posicionamento (aqui, Smart).

Como funciona
-------------
O tarsila-abrindo roda ANTES do aplicativo. Entao:

  1. escreve no rc.xml uma regra para a classe daquele aplicativo, com a
     vaga escolhida;
  2. manda "openbox --reconfigure";
  3. so entao dispara o aplicativo -- que nasce ja no lugar certo;
  4. quando a janela aparece, a regra e retirada.

O passo 4 nao e opcional: com force="yes" a regra valeria para TODA janela
daquela classe, para sempre, inclusive as abertas por outros caminhos.

Custa dois "openbox --reconfigure" por abertura. E o preco de nao ter salto.

Seguranca
---------
O rc.xml e a configuracao do gerenciador de janelas: corrompe-lo quebra a
area de trabalho inteira. Por isso, nesta ordem:

  * uma copia intocada e guardada na primeira vez (rc.xml.tarsila-original);
  * o que escrevemos vive entre marcadores, e so isso e substituido;
  * o texto novo e VALIDADO como XML antes de ir para o disco;
  * a troca e atomica (os.replace), entao nunca existe rc.xml pela metade;
  * duas aberturas ao mesmo tempo sao serializadas por trava -- quem nao
    pegar a trava simplesmente nao usa este caminho.

Qualquer falha devolve False, e quem chama volta ao comportamento antigo
(posicionar depois). Nenhum aplicativo pode deixar de abrir por causa disto.
"""

import fcntl
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

RC = os.path.expanduser("~/.config/openbox/rc.xml")
ORIGINAL = RC + ".tarsila-original"
TRAVA = os.path.expanduser("~/.config/tarsila/vaga.lock")

INICIO = "<!-- TARSILA-VAGA-INICIO (gerado automaticamente; nao editar) -->"
FIM = "<!-- TARSILA-VAGA-FIM -->"

# Tempo maximo esperando o reconfigure. Se estourar, seguimos assim mesmo:
# atrasar a abertura do aplicativo e pior que nascer no lugar errado.
LIMITE_RECONFIG = 4


def _trava():
    """Abre a trava, ou None se outra abertura ja a tem.

    Nao esperamos: se duas janelas abrem juntas, a segunda usa o caminho
    antigo. Melhor um salto do que segurar a abertura.
    """
    try:
        os.makedirs(os.path.dirname(TRAVA), exist_ok=True)
        f = open(TRAVA, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except Exception:
        return None


def _solta(f):
    try:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
    except Exception:
        pass


def _sem_bloco(texto):
    """O rc.xml sem o nosso trecho -- inclusive se tiver sobrado de antes.

    A remocao precisa ser o INVERSO EXATO da insercao, senao cada abertura
    deixa um resto de indentacao e o arquivo cresce sozinho. Medido em
    bancada: 200 ciclos sem isto e o rc.xml nao voltava ao original.
    Por isso comemos tambem os espacos e a quebra de linha que antecedem o
    marcador de inicio -- que foi exatamente o que a insercao acrescentou.
    """
    while INICIO in texto and FIM in texto:
        i = texto.index(INICIO)
        j = texto.index(FIM) + len(FIM)
        if j <= i:
            break
        # Recua sobre a indentacao e a quebra de linha do proprio bloco.
        k = i
        while k > 0 and texto[k - 1] in " \t":
            k -= 1
        if k > 0 and texto[k - 1] == "\n":
            k -= 1
        texto = texto[:k] + texto[j:]
    return texto


def _escreve(texto):
    """Valida, guarda copia original e troca o arquivo de uma vez so."""
    ET.fromstring(texto)          # estoura antes de tocar no disco
    if not os.path.exists(ORIGINAL):
        shutil.copy2(RC, ORIGINAL)
    tmp = RC + ".tarsila-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, RC)


def _reconfigura():
    subprocess.run(["openbox", "--reconfigure"],
                   capture_output=True, timeout=LIMITE_RECONFIG)


def origem_area_util():
    """(x, y) de onde comeca a area util -- o canto de baixo da barra de cima.

    O <position> do Openbox NAO conta a partir do canto da tela: conta a
    partir da area util, a mesma que o _NET_WORKAREA anuncia. Medido na TV:
    area util (0, 24), regra pedindo y=49, janela nasceu em y=73 -- 24 a
    mais, exatamente a altura da barra. Sem esta compensacao toda janela
    nasce uma barra abaixo da vaga.
    """
    try:
        saida = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                               capture_output=True, text=True, timeout=3).stdout
        n = [int(p.strip()) for p in saida.split("=", 1)[1].split(",")[:2]]
        return n[0], n[1]
    except Exception:
        return 0, 0


def prepara(classe, x, y):
    """Manda a proxima janela de <classe> nascer em (x, y) -- da TELA.

    Devolve a trava (para o limpa() depois) ou None se nao deu -- e nao ter
    dado nunca e motivo para o aplicativo nao abrir.
    """
    if not classe or not os.path.exists(RC):
        return None
    trava = _trava()
    if trava is None:
        return None
    try:
        with open(RC, encoding="utf-8") as f:
            texto = f.read()
        if "<applications>" not in texto:
            _solta(trava)
            return None
        limpo = _sem_bloco(texto)
        # Da coordenada de tela (que e como as vagas sao calculadas) para a
        # coordenada de area util (que e como o Openbox le). Nunca negativo:
        # numero negativo, para ele, significa "contado a partir da direita".
        ox, oy = origem_area_util()
        x = max(0, int(x) - ox)
        y = max(0, int(y) - oy)
        # O bloco carrega a propria quebra de linha e indentacao inicial, e
        # termina no marcador de fim -- e o que _sem_bloco() sabe desfazer.
        # DUAS regras, uma por "class" e outra por "name". O Openbox casa
        # "class" com o res_class do WM_CLASS ("Mousepad") e "name" com o
        # res_name ("mousepad") -- e a fonte do nosso texto varia: quando ele
        # vem do StartupWMClass do .desktop costuma ser o minusculo
        # ("tarsila-email"), quando vem da nossa medicao e o maiusculo.
        # Emitir as duas cobre os dois casos; a que nao casar nao faz nada,
        # e o Openbox aplica todas as regras que casarem.
        regra = (
            '\n    <application %s="%s">'
            '\n      <position force="yes">'
            '\n        <x>%d</x>'
            '\n        <y>%d</y>'
            '\n      </position>'
            '\n    </application>'
        )
        alvo = _escapa(classe)
        bloco = ('\n    %s%s%s\n    %s'
                 % (INICIO,
                    regra % ("class", alvo, int(x), int(y)),
                    regra % ("name", alvo, int(x), int(y)),
                    FIM))
        novo = limpo.replace("<applications>", "<applications>" + bloco, 1)
        _escreve(novo)
        _reconfigura()
        return trava
    except Exception:
        # Se falhou no meio, tenta deixar o arquivo sem o nosso trecho.
        try:
            _restaura_sem_bloco()
        except Exception:
            pass
        _solta(trava)
        return None


def limpa(trava):
    """Tira a regra. Sempre chamado, mesmo se a janela nunca apareceu."""
    if trava is None:
        return
    try:
        _restaura_sem_bloco()
        _reconfigura()
    except Exception:
        pass
    finally:
        _solta(trava)


def _restaura_sem_bloco():
    with open(RC, encoding="utf-8") as f:
        texto = f.read()
    if INICIO not in texto:
        return
    _escreve(_sem_bloco(texto))


def _escapa(v):
    return (v.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))
