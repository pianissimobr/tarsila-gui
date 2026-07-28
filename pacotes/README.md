# Fontes dos pacotes

O Tarsila instala dois programas próprios por `.deb`, e não pelo `overlay/`:
o **assistente de e-mail** (`claws-mail-suite`) e a **Agenda**
(`agenda-tarsila`). Os fontes deles moravam fora de qualquer repositório —
só em `~/Downloads` de uma máquina — enquanto a tvbox recebia correção atrás
de correção editada no lugar. Reconstruir um pacote desfazia essas correções
sem avisar. É esse buraco que este diretório fecha.

## claws-mail-suite

`build-deb-openbox.sh` monta o pacote inteiro. Ele carrega os programas
embutidos como *heredoc*:

- `configurar-claws` — o motor: grava a conta no Claws, deduz servidor,
  porta e criptografia, abre a página de senha de aplicativo
- `configurar-claws-gui` — a tela que o usuário vê; chama o motor em modo
  não-interativo (`--abrir`, `--gravar`, `--geometria-login`)

A interface gráfica **não existia neste fonte**: ficou só na tvbox desde
26/07/2026. Quem reconstruísse o pacote voltava ao assistente antigo em
`yad`, sem perceber.

## agenda-tarsila

Árvore pronta para `dpkg-deb --build`. O código é o mesmo que está em
`overlay/opt/agenda-tarsila/`.

### O `credentials.json` fica aqui, cifrado

O pacote instala `/etc/agenda-tarsila/credentials.json`: são as credenciais
do app no Google Cloud, criadas pelo desenvolvedor. **Sem esse arquivo a
Agenda não conecta na conta Google sozinha** e configurar vira trabalho
manual — então ele precisa acompanhar o fonte. Mas em texto claro ele se
espalha com qualquer clone.

A saída é guardar no Git só a versão cifrada:

    pacotes/segredo.sh abrir      # antes de construir o .deb
    pacotes/segredo.sh guardar    # depois de trocar o arquivo

O que está versionado é `credentials.json.gpg` (AES-256, senha simétrica). O
texto claro é barrado pelo `.gitignore` e nunca entra em commit.

A senha mora **fora do repositório**, em `~/.config/tarsila/senha-credenciais`
(também aceita a variável `TARSILA_SENHA_CREDENCIAIS`, ou é perguntada na
hora). Guarde uma cópia dela em lugar seguro: sem a senha, o jeito de
recuperar é gerar credenciais novas no Google Cloud.

#### Qual é o risco de verdade

Este é um cliente do tipo **`installed`** (aplicativo de desktop). A própria
documentação do Google diz que, nesse tipo, o segredo do cliente não é
tratado como segredo — ele é embutido no programa distribuído, e o padrão de
OAuth para aplicativos nativos parte do princípio de que não há como
escondê-lo. Ele **não dá acesso à agenda de ninguém**: para chegar aos dados
de um usuário ainda é preciso que essa pessoa passe pela tela de
consentimento do Google, e o token que sai dali é dela, guardado na máquina
dela.

O que um vazamento permite é mais modesto, e ainda assim indesejável:
alguém pode se passar pelo nosso app numa tela de consentimento, e pode
queimar a cota do projeto no Google Cloud até derrubá-lo ou fazê-lo ser
sinalizado. Por isso ciframos — mas é cinto e suspensório, não a última
linha de defesa. Se um dia a senha se perder, dá para gerar credenciais
novas no console sem drama.

## Antes de mexer

    pacotes/verificar.sh

Confere se os programas embutidos no `build-deb` ainda são idênticos aos que
o `overlay/` instala. O mesmo arquivo vive nos dois lugares: o `overlay/` é
o que o `install.sh` copia para a máquina, `pacotes/` é de onde o `.deb`
nasce. Quando os dois desandam, é o `.deb` que ganha — e a correção some.
