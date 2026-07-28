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
