-- Relogio do modo de espera do Tarsila.
-- Desenhado pelo PROPRIO mpv via OSD/ASS: sem janela extra, sem segundo
-- processo, e o texto acompanha o video em tela cheia.
-- Fonte Inter: alternativa livre mais proxima da San Francisco da Apple.
local mp = require 'mp'

-- Nomes em portugues FIXOS de proposito: o os.date do Lua embutido no mpv nao
-- honra o locale do sistema (saia "Sunday, 26 de July"), e depender de
-- os.setlocale aqui e fragil.
local DIAS = { "Domingo", "Segunda-feira", "Terca-feira", "Quarta-feira",
               "Quinta-feira", "Sexta-feira", "Sabado" }
local MESES = { "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro" }

local ultimo = nil
local function desenhar()
    local t = os.date("*t")
    local hora = string.format("%02d:%02d", t.hour, t.min)
    local data = string.format("%s, %d de %s", DIAS[t.wday], t.day, MESES[t.month])
    -- \an5 ancora no centro; \pos no meio de uma tela virtual 1920x1080
    -- \bord0 sem contorno; \shad sombra suave para legibilidade sobre o video
    local ass =
        "{\\an5\\pos(960,520)\\fnInter\\fs170\\b1\\bord0\\shad5\\4a&H90&\\1c&HFFFFFF&}"
        .. hora ..
        "\\N{\\fs46\\b0\\alpha&H35&\\shad3}" .. data
    -- So repinta quando o texto MUDA. Redesenhar o ASS a cada segundo sem
    -- necessidade custava caro: medido, o modo de espera ia de 50% para 91%
    -- de CPU so por causa disso. Agora o repinte acontece uma vez por minuto.
    if ass ~= ultimo then
        ultimo = ass
        mp.set_osd_ass(1920, 1080, ass)
    end
end

mp.add_periodic_timer(2, desenhar)
desenhar()

-- Sair ao primeiro sinal de uso. Teclas e botoes vem do input.conf; aqui
-- tratamos o MOVIMENTO do mouse, que nao gera tecla.
local base = nil
mp.observe_property("mouse-pos", "native", function(_, v)
    if not v then return end
    if base == nil then base = { x = v.x, y = v.y }; return end
    if v.x ~= base.x or v.y ~= base.y then mp.commandv("quit") end
end)
