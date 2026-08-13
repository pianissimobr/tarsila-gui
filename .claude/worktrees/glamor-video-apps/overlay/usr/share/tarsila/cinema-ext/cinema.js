(() => {
  "use strict";

  // Camada 1: sites que o yt-dlp comprovadamente extrai (lista conservadora).
  const SITES_SUPORTADOS = [
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
    "archive.org", "globoplay.globo.com"
  ];

  const hostOk = SITES_SUPORTADOS.some(s =>
    location.hostname === s || location.hostname.endsWith("." + s));

  // Camada 2: <video> com fonte direta (mp4/webm/HLS).
  function fonteDireta() {
    for (const v of document.querySelectorAll("video")) {
      const src = v.currentSrc || v.src || "";
      if (/^https?:\/\/.+\.(mp4|webm|m3u8)(\?|$)/i.test(src)) return src;
      for (const s of v.querySelectorAll("source")) {
        if (/^https?:\/\/.+\.(mp4|webm|m3u8)(\?|$)/i.test(s.src)) return s.src;
      }
    }
    return null;
  }

  // A qualidade e escolhida AQUI, no video que o usuario esta olhando, e nao
  // numa tela de configuracao que ele precisaria lembrar que existe. Comeca em
  // "Automatico" a cada video de proposito: assim ninguem fica preso a uma
  // escolha feita semanas atras e ja esquecida.
  const OPCOES = [
    ["auto", "Automático", "deixa o site decidir"],
    ["1080", "1080p", "mais nítido, pesa mais"],
    ["720", "720p", "equilíbrio"],
    ["480", "480p", "mais leve, para internet fraca"]
  ];
  let qualidade = "auto";

  let caixa = null, botao = null, seletor = null, menu = null;

  const ROTULO = () => OPCOES.find(o => o[0] === qualidade)[1];

  function fecharMenu() {
    if (menu) { menu.remove(); menu = null; }
  }

  function abrirMenu() {
    if (menu) { fecharMenu(); return; }
    menu = document.createElement("div");
    menu.setAttribute("style",
      "position:absolute;bottom:calc(100% + 8px);right:0;" +
      "background:#1a1a2e;border-radius:12px;overflow:hidden;" +
      "box-shadow:0 4px 16px rgba(0,0,0,.5);min-width:200px");
    for (const [valor, nome, dica] of OPCOES) {
      const atual = valor === qualidade;
      const item = document.createElement("button");
      item.setAttribute("style",
        "display:block;width:100%;text-align:left;border:none;cursor:pointer;" +
        "padding:11px 14px;font:14px sans-serif;color:#fff;" +
        "background:" + (atual ? "#2d6cdf" : "transparent"));
      const t = document.createElement("div");
      t.textContent = (atual ? "✓ " : "    ") + nome;
      t.setAttribute("style", "font-weight:600");
      const d = document.createElement("div");
      d.textContent = dica;
      d.setAttribute("style", "font-size:12px;opacity:.72;margin-left:20px");
      item.append(t, d);
      item.addEventListener("click", (ev) => {
        ev.stopPropagation();
        qualidade = valor;
        seletor.textContent = ROTULO() + " ▾";
        fecharMenu();
      });
      menu.appendChild(item);
    }
    caixa.appendChild(menu);
  }

  document.addEventListener("click", (ev) => {
    if (menu && caixa && !caixa.contains(ev.target)) fecharMenu();
  }, true);

  function montar() {
    caixa = document.createElement("div");
    caixa.setAttribute("style",
      "position:fixed;bottom:16px;right:16px;z-index:2147483647;" +
      "display:flex;align-items:stretch;" +
      "box-shadow:0 2px 10px rgba(0,0,0,.4);border-radius:24px;" +
      "font:600 14px sans-serif");

    botao = document.createElement("button");
    botao.textContent = "🎬 Modo Cinema";
    botao.setAttribute("style",
      "padding:10px 14px;border:none;cursor:pointer;background:#1a1a2e;" +
      "color:#fff;font:inherit;border-radius:24px 0 0 24px");

    // Microbotao colado no principal: mostra a escolha atual e abre a caixinha.
    seletor = document.createElement("button");
    seletor.textContent = ROTULO() + " ▾";
    seletor.title = "Qualidade deste vídeo";
    seletor.setAttribute("style",
      "padding:10px 13px;border:none;cursor:pointer;background:#25253f;" +
      "color:#fff;font:inherit;border-radius:0 24px 24px 0;" +
      "border-left:1px solid rgba(255,255,255,.18)");
    seletor.addEventListener("click", (ev) => { ev.stopPropagation(); abrirMenu(); });

    botao.addEventListener("click", () => {
      fecharMenu();
      botao.textContent = "⏳ Abrindo...";
      botao.disabled = true;
      chrome.runtime.sendMessage(
        { url: fonteDireta() || location.href, titulo: document.title,
          qualidade: qualidade },
        (resp) => {
          if (resp && resp.ok) {
            document.querySelectorAll("video").forEach(v => v.pause());
            botao.textContent = "🎬 Modo Cinema";
            botao.disabled = false;
          } else {
            botao.textContent = "Indisponível — assista aqui mesmo";
            seletor.remove();
            setTimeout(() => {
              if (caixa) { caixa.remove(); caixa = botao = seletor = null; }
            }, 4000);
          }
        });
    });

    caixa.append(botao, seletor);
    document.body.appendChild(caixa);
  }

  function avaliar() {
    const elegivel = (hostOk && document.querySelector("video") !== null)
                     || fonteDireta() !== null;
    if (elegivel && !caixa) montar();
    else if (!elegivel && caixa) {
      fecharMenu();
      caixa.remove();
      caixa = botao = seletor = null;
    }
  }

  avaliar();
  let agendado = false;
  new MutationObserver(() => {
    if (agendado) return;
    agendado = true;
    setTimeout(() => { agendado = false; avaliar(); }, 1500);
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
