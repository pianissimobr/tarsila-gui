#!/bin/bash
# Guarda o credentials.json da Agenda no repositório, cifrado.
#
# O problema: sem esse arquivo a Agenda não conecta na conta Google sozinha,
# e configurar vira trabalho manual. Com ele em texto claro, um clone, um
# fork ou uma mudança de visibilidade do repositório espalha a credencial.
# A saída é guardar a versão cifrada no Git e a senha fora dele.
#
# Uso:
#   pacotes/segredo.sh abrir     decifra  -> credentials.json   (antes do build)
#   pacotes/segredo.sh guardar   cifra    -> credentials.json.gpg (depois de trocar)
#
# A senha é procurada nesta ordem:
#   1. variável TARSILA_SENHA_CREDENCIAIS
#   2. arquivo ~/.config/tarsila/senha-credenciais
#   3. perguntada na hora
#
# O texto claro nunca entra no Git: o .gitignore barra credentials.json.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

CLARO=pacotes/agenda-tarsila/etc/agenda-tarsila/credentials.json
CIFRADO="$CLARO.gpg"
GUARDA="$HOME/.config/tarsila/senha-credenciais"

senha() {
    if [ -n "${TARSILA_SENHA_CREDENCIAIS:-}" ]; then
        printf '%s' "$TARSILA_SENHA_CREDENCIAIS"; return 0
    fi
    if [ -r "$GUARDA" ]; then
        head -1 "$GUARDA"; return 0
    fi
    # Sem senha guardada: pergunta. O -s não ecoa o que for digitado.
    read -rsp "Senha do credentials.json: " s </dev/tty; echo >&2
    printf '%s' "$s"
}

case "${1:-}" in
abrir)
    [ -f "$CIFRADO" ] || { echo "Não achei $CIFRADO" >&2; exit 1; }
    mkdir -p "$(dirname "$CLARO")"
    if senha | gpg --batch --quiet --yes --passphrase-fd 0 \
                   --pinentry-mode loopback \
                   --output "$CLARO" --decrypt "$CIFRADO"; then
        chmod 600 "$CLARO"
        echo "Pronto: $CLARO"
    else
        rm -f "$CLARO"
        echo "Senha errada ou arquivo corrompido." >&2; exit 1
    fi
    ;;
guardar)
    [ -f "$CLARO" ] || { echo "Não achei $CLARO" >&2; exit 1; }
    if senha | gpg --batch --quiet --yes --passphrase-fd 0 \
                   --pinentry-mode loopback \
                   --symmetric --cipher-algo AES256 \
                   --output "$CIFRADO" "$CLARO"; then
        echo "Guardado: $CIFRADO"
        echo "Confira com: git status  (o texto claro deve continuar invisível)"
    else
        echo "Não consegui cifrar." >&2; exit 1
    fi
    ;;
*)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
