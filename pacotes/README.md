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

### O `credentials.json` não está aqui, e não deve estar

O pacote instala `/etc/agenda-tarsila/credentials.json`, que são as
credenciais de desenvolvedor do app no Google Cloud — **incluem o segredo do
cliente**. Este repositório é privado, mas segredo de cliente não se guarda
em repositório nenhum: basta um clone, um fork ou uma mudança de
visibilidade. Confirmei que ele nunca entrou em commit algum.

Para montar o pacote, ponha o arquivo em
`pacotes/agenda-tarsila/etc/agenda-tarsila/credentials.json` na hora do
build e não o adicione ao git (o `.gitignore` já barra). Sem ele o pacote
constrói e instala; o `postinst` só ajusta a permissão se o arquivo existir
— quem fica sem é o usuário, na hora de conectar a conta Google.

## Antes de mexer

    pacotes/verificar.sh

Confere se os programas embutidos no `build-deb` ainda são idênticos aos que
o `overlay/` instala. O mesmo arquivo vive nos dois lugares: o `overlay/` é
o que o `install.sh` copia para a máquina, `pacotes/` é de onde o `.deb`
nasce. Quando os dois desandam, é o `.deb` que ganha — e a correção some.
