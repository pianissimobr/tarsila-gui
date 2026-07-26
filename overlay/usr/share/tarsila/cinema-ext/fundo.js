// Tarsila 2026-07-26 — reproducao em segundo plano no YouTube.
// O YouTube mobile PAUSA o video (e volta para t=0) assim que a pagina fica
// oculta; ao minimizar a janela, a musica morria. Aqui a pagina simplesmente
// nunca fica oculta: visibilityState/hidden ficam presos em "visivel" e os
// eventos de mudanca sao engolidos antes de chegar ao script do site.
// PRECISA rodar no mundo MAIN e em document_start, senao o site le os valores
// verdadeiros antes da gente sobrescrever.
// ESCOPO: so youtube.com. Nao aplicar em todo site — manter a pagina "sempre
// visivel" faz abas de fundo continuarem trabalhando e gastando CPU.
// CUSTO (medido 2026-07-26 nesta box, YouTube 480p): janela visivel = 148%
// de CPU; minimizada e tocando = 26%. Cai porque janela minimizada nao e
// composta nem pintada -- sobra decode + audio. Nao chega a ser so-audio como
// o YouTube desktop faz (isso o cliente nao consegue forcar), mas e barato.
(() => {
  const def = (o, p, v) => {
    try { Object.defineProperty(o, p, { get: () => v, configurable: true }); } catch (e) {}
  };
  def(document, "hidden", false);
  def(document, "visibilityState", "visible");
  def(document, "webkitHidden", false);
  def(document, "webkitVisibilityState", "visible");
  const engole = e => { e.stopImmediatePropagation(); };
  for (const ev of ["visibilitychange", "webkitvisibilitychange"])
    document.addEventListener(ev, engole, true);
  for (const ev of ["blur", "pagehide"])
    window.addEventListener(ev, engole, true);
})();
