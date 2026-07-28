-- devilspie2: toda janela nova cai na janela de trabalho 2. Por padrao
-- nunca maximizada - excecao: o Chromium sempre abre maximizado (pedido
-- explicito do usuario, unico app com essa excecao).
--
-- TAMANHO E POSICAO: por conta do proprio app e do posicionamento
-- inteligente do xfwm4. O antigo encaixe em "slots"/cascata (que
-- forcava geometria via set_window_geometry2) desenhava janelas fora
-- da tela e foi removido de proposito em 2026-07-19 - NAO reintroduzir
-- posicionamento forcado aqui; este script so garante o estado
-- (workspace/nao-maximizada), nunca a geometria.
--
-- GUARDA CRITICA: janelas de shell/sistema (area de trabalho, painel,
-- dock) NUNCA podem ser tocadas por este script. Elas tambem disparam
-- "window_open" quando (re)criadas (ex: reiniciar o xfdesktop), e sem
-- essa guarda o resto do script tenta trocar workspace/maximizar essas
-- janelas como se fossem um app comum - foi exatamente isso que
-- deslocou o xfdesktop da tela (0,0) para uma posicao de cascata,
-- deixando faixas pretas onde devia estar o papel de parede.
-- Comparado por WM_CLASS (classe, nao instancia).
local SYSTEM_CLASSES = { Xfdesktop = true, ["Xfce4-panel"] = true, Plank = true }
if SYSTEM_CLASSES[get_window_class()] then
  return
end

-- SUBPROCESSO (regra de UX 2026-07-19): se o usuario esta com um app
-- MAXIMIZADO (janela de trabalho 3) e uma janela nova abre a partir
-- dele (ex.: Chromium abre a pasta Downloads no Arquivos), NAO puxar
-- tudo para a janela de trabalho 2 - o app maximizado fica como esta e
-- a janela nova flutua por cima. MAX vem do estado do top bar
-- (tarsila-title.sh grava em tarsila-topbar-state.txt).
local function app_maximizado()
  local rt = os.getenv("XDG_RUNTIME_DIR") or "/tmp"
  local f = io.open(rt .. "/tarsila-topbar-state.txt")
  if not f then return false end
  local conteudo = f:read("*a")
  f:close()
  return conteudo:match("MAX=1") ~= nil
end

if not app_maximizado() then
  os.execute("/usr/local/bin/tarsila-goto2.sh")
end

-- Dialogos do yad (AppFinder e afins), o Gerenciar Dock e o instalador
-- de .deb dimensionam a si mesmos e sao pequenos de proposito - nada a
-- fazer alem de deixa-los em paz.
local wclass = get_window_class() or ""
if wclass == "Yad"
   or wclass == "Tarsila-dock-manager"
   or wclass == "tarsila-dock-manager"
   or wclass == "Tarsila-deb-gui.py"
   or wclass == "tarsila-deb-gui.py" then
  return
end

if get_window_class() == "Chromium" then
  maximize()
  undecorate()
else
  unmaximize()
end

-- TAMANHO DAS JANELAS (2026-07-28): nada nasce desproporcional.
--
-- A pergunta natural e "cada aplicativo nao tem uma configuracao propria de
-- tamanho de abertura?". Tem, e e justamente por isso que nao da para
-- resolver por ali:
--
--   * O padrao do X para isso e o WM_NORMAL_HINTS, onde o programa declara
--     tamanho minimo e preferido. E conselho, nao regra, e cada um preenche
--     como quer: o VLC declara "22 by 22" -- abrir no minimo que ele declara
--     daria uma janela de selo postal.
--   * Cada um ainda guarda a propria geometria no seu canto e no seu
--     formato: o VLC grava a dele em vlc-qt-interface.conf como um bloco
--     binario @ByteArray do Qt, que nao se edita a mao.
--
-- Nao existe lugar comum onde mexer. O unico ponto por onde TODAS as
-- janelas passam e este. Entao a regra e de proporcao, nao de aplicativo:
-- quem nasce grande demais para a area util encolhe e vai para o centro.
--
-- Casos medidos: "Salvar como" do AbiWord com 822px de altura numa tela de
-- 768 (botoes Salvar/Cancelar fora da tela); o do Gnumeric com 697 de 734
-- (95% da altura para escolher um nome de arquivo); o VLC abrindo com
-- 1366x699, a largura inteira da tela.
--
-- Isto NAO e o posicionamento em cascata removido em 2026-07-19 e que nao
-- deve voltar: aquele impunha geometria a TODA janela e desenhava janela
-- fora da tela. Aqui ninguem e tocado por nascer -- so quem passa de um
-- limite folgado. Nenhum aplicativo e citado pelo nome e nenhuma medida e
-- fixa: tudo sai da area util que o proprio gerenciador anuncia
-- (_NET_WORKAREA, que ja desconta a barra de cima).

local function area_util()
  local p = io.popen("xprop -root _NET_WORKAREA 2>/dev/null")
  if not p then return nil end
  local linha = p:read("*a"); p:close()
  local x, y, l, a = linha:match("=%s*(%d+),%s*(%d+),%s*(%d+),%s*(%d+)")
  if not x then return nil end
  return tonumber(x), tonumber(y), tonumber(l), tonumber(a)
end

-- Encolhe a janela SE ela passar do limite, e centraliza no que sobrou.
local function conter(limite_l, limite_a, alvo_l, alvo_a)
  local _, _, jl, ja = get_window_geometry()
  local ax, ay, al, aa = area_util()
  if not al then return end
  if jl <= al * limite_l and ja <= aa * limite_a then return end
  local nl = math.min(jl, math.floor(al * alvo_l))
  local na = math.min(ja, math.floor(aa * alvo_a))
  set_window_geometry(math.floor(ax + (al - nl) / 2),
                      math.floor(ay + (aa - na) / 2), nl, na)
end

local tipo = get_window_type()

if tipo == "WINDOW_TYPE_DIALOG" or tipo == "WINDOW_TYPE_UTILITY" then
  -- Caixa de dialogo: o limite e mais apertado, porque dialogo grande e
  -- sempre desconfortavel -- ele deveria caber sobre a janela que o chamou.
  conter(0.75, 0.80, 0.60, 0.70)

elseif tipo == "WINDOW_TYPE_NORMAL" and not get_window_is_maximized() then
  -- Janela comum: limite bem folgado, so para pegar quem abre ocupando a
  -- tela inteira sem estar maximizado. Quem foi maximizado de proposito
  -- (o Chromium) nao entra aqui.
  --
  -- As telas do proprio Tarsila ficam de fora: elas ja nascem no tamanho
  -- que combinamos, e algumas sao altas de proposito (a de Ajustes vai
  -- quase ate a barra de cima porque o usuario pediu assim).
  local classe = (get_window_class() or ""):lower()
  if not classe:match("^tarsila") then
    conter(0.90, 0.90, 0.70, 0.75)
  end
end
