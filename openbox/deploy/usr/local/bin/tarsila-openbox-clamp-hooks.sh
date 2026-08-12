#!/bin/bash
# Insere hooks de Release (botão esquerdo) no rc.xml do Openbox, se ainda não existirem.
#
# Dois grupos de hooks:
#  - Titlebar / Client / Frame (contexto do PONTO DE SOLTA): cobre a maioria
#    dos casos, mas só dispara se o release acontecer sobre aquele contexto
#    específico da própria janela.
#  - MoveResize (contexto ativo durante TODO o arraste, independente do que
#    está visualmente sob o cursor no momento do release): é o que garante o
#    clamp mesmo soltando em cima da própria polybar -- caso em que o ponto
#    de release cai sobre o módulo (relógio/ícones), não mais sobre
#    "Titlebar", e os hooks acima não disparam. Testado em 2026-08-02: o
#    xev-root usado antes para cobrir esse caso nunca capturava eventos de
#    botão nesta sessão (só Motion/Leave) -- MoveResize é nativo do Openbox
#    3.6.1 e não depende de nenhum processo externo.

RC="$HOME/.config/openbox/rc.xml"

[ -f "$RC" ] || exit 0

python3 <<'PY'
from pathlib import Path
import re

rc = Path.home() / ".config/openbox/rc.xml"
text = rc.read_text(encoding="utf-8")
marker = "tarsila-clamp-on-release.sh"
changed = False

hook = """
      <mousebind button="Left" action="Release">
        <action name="Execute"><command>/usr/local/bin/tarsila-clamp-on-release.sh</command></action>
      </mousebind>"""

alt_hook = """
      <mousebind button="A-Left" action="Release">
        <action name="Execute"><command>/usr/local/bin/tarsila-clamp-on-release.sh</command></action>
      </mousebind>"""


def insert_after_drag(xml: str, context: str, button: str, snippet: str) -> str:
    pattern = (
        rf'(<context name="{context}">.*?'
        rf'<mousebind button="{button}" action="Drag">.*?</mousebind>)'
    )
    m = re.search(pattern, xml, flags=re.S)
    if not m:
        return xml
    if snippet.strip() in xml[m.start():m.end() + 200]:
        return xml
    insert_at = m.end(1)
    return xml[:insert_at] + snippet + xml[insert_at:]


before = text
text = insert_after_drag(text, "Titlebar", "Left", hook)
text = insert_after_drag(text, "Client", "A-Left", alt_hook)
text = insert_after_drag(text, "Frame", "A-Left", alt_hook)
if text != before:
    changed = True

# Contexto MoveResize -- cria se não existir, injeta os binds se existir mas
# ainda não tiver o marker.
mr_match = re.search(r'<context name="MoveResize">(.*?)</context>', text, flags=re.S)
if mr_match and marker in mr_match.group(1):
    pass  # já tem
elif mr_match:
    insert_at = mr_match.start(1)
    text = text[:insert_at] + hook + alt_hook + text[insert_at:]
    changed = True
else:
    block = f'    <context name="MoveResize">{hook}{alt_hook}\n    </context>\n'
    idx = text.find("  </mouse>")
    if idx != -1:
        text = text[:idx] + block + text[idx:]
        changed = True

if changed:
    rc.write_text(text, encoding="utf-8")
    print("openbox rc.xml: clamp hooks ok (Titlebar/Client/Frame + MoveResize)")
else:
    print("openbox rc.xml: já atualizado")
PY

openbox --reconfigure 2>/dev/null || true
