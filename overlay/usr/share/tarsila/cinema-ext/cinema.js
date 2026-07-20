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

  let botao = null;

  function avaliar() {
    const direto = fonteDireta();
    const temVideo = document.querySelector("video") !== null;
    const elegivel = (hostOk && temVideo) || direto !== null;

    if (elegivel && !botao) {
      botao = document.createElement("button");
      botao.textContent = "\uD83C\uDFAC Modo Cinema";
      botao.setAttribute("style",
        "position:fixed;bottom:16px;right:16px;z-index:2147483647;" +
        "padding:10px 16px;border-radius:24px;border:none;cursor:pointer;" +
        "background:#1a1a2e;color:#fff;font:600 14px sans-serif;" +
        "box-shadow:0 2px 10px rgba(0,0,0,.4)");
      botao.addEventListener("click", () => {
        botao.textContent = "\u23F3 Abrindo...";
        botao.disabled = true;
        chrome.runtime.sendMessage(
          { url: direto || location.href, titulo: document.title },
          (resp) => {
            if (resp && resp.ok) {
              document.querySelectorAll("video").forEach(v => v.pause());
              botao.textContent = "\uD83C\uDFAC Modo Cinema";
              botao.disabled = false;
            } else {
              botao.textContent = "Indispon\u00edvel \u2014 assista aqui mesmo";
              setTimeout(() => { if (botao) { botao.remove(); botao = null; } }, 4000);
            }
          });
      });
      document.body.appendChild(botao);
    } else if (!elegivel && botao) {
      botao.remove();
      botao = null;
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
