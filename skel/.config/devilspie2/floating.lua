-- devilspie2: toda janela nova cai na janela de trabalho 2. Por padrao
-- nunca maximizada. Chromium segue a regra de todo mundo (07/08).
--
-- TAMANHO E POSICAO: por conta do proprio app e do posicionamento
-- inteligente do gerenciador. O antigo encaixe em "slots"/cascata
-- foi removido em 2026-07-19 - NAO reintroduzir posicionamento forcado.

local SYSTEM_CLASSES = { Xfdesktop = true, ["Xfce4-panel"] = true,
                         Plank = true,
                         ["Tarsila-tela-estados"] = true }
if SYSTEM_CLASSES[get_window_class()] then
  return
end

-- Nao ha mais "estados de tela" a consultar. Ate aqui este arquivo lia
-- tarsila-topbar-state.txt e tarsila-polybar-mode.txt para decidir se
-- chamava o tarsila-goto2.sh. O segundo arquivo nao existia no runtime desde
-- 06/08, entao a condicao era sempre falsa e TODA janela nova disparava um
-- goto2.sh -- que por sua vez rodava um wmctrl -lx, um laco de wmctrl -ir por
-- janela e um xdotool. Custo puro, em cima do caminho mais quente do sistema.

local wclass = get_window_class() or ""
if wclass == "Yad"
   or wclass == "Tarsila-dock-manager"
   or wclass == "tarsila-dock-manager"
   or wclass == "Tarsila-deb-gui.py"
   or wclass == "tarsila-deb-gui.py" then
  return
end

unmaximize()

local function area_util()
  local p = io.popen("xprop -root _NET_WORKAREA 2>/dev/null")
  if not p then return nil end
  local linha = p:read("*a"); p:close()
  local x, y, l, a = linha:match("=%s*(%d+),%s*(%d+),%s*(%d+),%s*(%d+)")
  if not x then return nil end
  return tonumber(x), tonumber(y), tonumber(l), tonumber(a)
end

local function conter(limite_l, limite_a, alvo_l, alvo_a, centralizar)
  local jx, jy, jl, ja = get_window_geometry()
  local ax, ay, al, aa = area_util()
  if not al then return end
  if jl <= al * limite_l and ja <= aa * limite_a then return end
  local nl = math.min(jl, math.floor(al * alvo_l))
  local na = math.min(ja, math.floor(aa * alvo_a))
  if centralizar then
    set_window_geometry(math.floor(ax + (al - nl) / 2),
                        math.floor(ay + (aa - na) / 2), nl, na)
  else
    set_window_size(nl, na)
  end
end

local tipo = get_window_type()

if tipo == "WINDOW_TYPE_DIALOG" or tipo == "WINDOW_TYPE_UTILITY" then
  conter(0.75, 0.80, 0.60, 0.70, true)

elseif tipo == "WINDOW_TYPE_NORMAL" and not get_window_is_maximized() then
  local classe = (get_window_class() or ""):lower()
  if not classe:match("^tarsila") then
    conter(0.90, 0.90, 0.70, 0.75, false)
  end
end
