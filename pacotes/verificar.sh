#!/bin/bash
# Confere se os fontes dos pacotes ainda batem com o que o overlay instala.
#
# Por que isto existe: os mesmos programas aparecem em dois lugares. O
# overlay/ e o que o install.sh copia para a maquina; pacotes/ e de onde os
# .deb sao construidos. Se as duas copias desandarem, reconstruir um pacote
# desfaz correcoes silenciosamente -- foi exatamente o que aconteceu com o
# assistente de e-mail, que passou meses corrigido so na tvbox.
#
# Uso:  pacotes/verificar.sh          (da raiz do repositorio)
# Sai com 1 se algo divergir.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

falhas=0

conferir() {          # $1=rotulo  $2=arquivo A  $3=arquivo B
    if [ ! -f "$2" ] || [ ! -f "$3" ]; then
        printf '  FALTA   %s\n' "$1"; falhas=$((falhas + 1)); return
    fi
    if cmp -s "$2" "$3"; then
        printf '  ok      %s\n' "$1"
    else
        printf '  DIFERE  %s\n' "$1"
        diff -u "$2" "$3" | head -20
        falhas=$((falhas + 1))
    fi
}

# O build-deb do claws guarda os dois programas embutidos como heredoc.
# Extraimos e comparamos com o que o overlay instala.
BUILD=pacotes/claws-mail-suite/build-deb-openbox.sh
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

awk 'f && /^__FIM_ASSISTENTE__$/ {exit} f; /^cat > "\$PAYLOAD\/configurar-claws" <</ {f=1}' \
    "$BUILD" > "$TMP/configurar-claws"
awk 'f && /^__FIM_GUI__$/ {exit} f; /^cat > "\$PAYLOAD\/configurar-claws-gui" <</ {f=1}' \
    "$BUILD" > "$TMP/configurar-claws-gui"

conferir "configurar-claws"      "$TMP/configurar-claws"      overlay/usr/bin/configurar-claws
conferir "configurar-claws-gui"  "$TMP/configurar-claws-gui"  overlay/usr/bin/configurar-claws-gui
conferir "agenda_tarsila.py"     pacotes/agenda-tarsila/opt/agenda-tarsila/agenda_tarsila.py \
                                 overlay/opt/agenda-tarsila/agenda_tarsila.py

# ------------------------------------------------------------------
# O repositório tem TRÊS árvores que instalam arquivos, e cada uma tem o
# seu instalador:
#
#   overlay/         -> /            (install.sh)
#   skel/            -> ~            (install.sh)
#   openbox/deploy/  -> / e ~/.config  (openbox/deploy-install.sh)
#
# Um mesmo programa em duas delas é armadilha: dependendo de qual
# instalador rodou por último, a máquina fica com uma versão ou com a
# outra. Já aconteceu — a polybar existia em openbox/deploy e foi
# duplicada em skel sem que ninguém notasse.
echo
echo "Arquivos em mais de uma árvore:"
python3 - <<'PY'
import os
from collections import defaultdict

# O destino final é o que importa: dois arquivos que pousam no mesmo
# lugar colidem, mesmo com caminhos diferentes no repositório.
destinos = defaultdict(list)
for base, prefixo in (("overlay", "/"),
                      ("skel", "~/"),
                      ("openbox/deploy/usr", "/usr/"),
                      ("openbox/deploy/etc", "/etc/"),
                      ("openbox/deploy/home", "~/.config/")):
    if not os.path.isdir(base):
        continue
    for raiz, _, arquivos in os.walk(base):
        for a in arquivos:
            caminho = os.path.join(raiz, a)
            destinos[prefixo + os.path.relpath(caminho, base)].append(caminho)

colisoes = {d: c for d, c in destinos.items() if len(c) > 1}
for destino, copias in sorted(colisoes.items()):
    print("  COLIDE  %s" % destino)
    for c in copias:
        print("            %s" % c)
if not colisoes:
    print("  nenhum")
PY

if [ "$falhas" -eq 0 ]; then
    echo
    echo "Tudo conferido."
else
    echo
    echo "$falhas divergencia(s)."
fi
exit $(( falhas > 0 ))
