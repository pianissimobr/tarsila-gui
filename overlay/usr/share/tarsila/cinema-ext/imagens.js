(() => {
  "use strict";

  function larguraDoCandidato(cand) {
    const m = cand.match(/\s(\d+)w\s*$/);
    return m ? parseInt(m[1], 10) : Number.MAX_SAFE_INTEGER;
  }

  function otimizar(img) {
    if (img.dataset.tarsilaOk) return;
    img.dataset.tarsilaOk = "1";
    img.loading = "lazy";
    img.decoding = "async";

    if (img.srcset && img.srcset.includes(",")) {
      const candidatos = img.srcset.split(",").map(s => s.trim()).filter(Boolean);
      let menor = candidatos[0];
      for (const c of candidatos) {
        if (larguraDoCandidato(c) < larguraDoCandidato(menor)) menor = c;
      }
      if (larguraDoCandidato(menor) !== Number.MAX_SAFE_INTEGER) {
        img.srcset = menor;
        img.sizes = "";
      }
    }
  }

  document.querySelectorAll("img").forEach(otimizar);

  let agendado = false;
  new MutationObserver(() => {
    if (agendado) return;
    agendado = true;
    setTimeout(() => {
      agendado = false;
      document.querySelectorAll("img:not([data-tarsila-ok])").forEach(otimizar);
    }, 1000);
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
