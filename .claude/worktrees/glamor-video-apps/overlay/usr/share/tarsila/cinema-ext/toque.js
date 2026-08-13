// ---------------------------------------------------------------------------
// Tarsila — traduz ARRASTO DE MOUSE em gestos de toque.
//
// POR QUE: a versão mobile de um site só liga os manipuladores de gesto se o
// navegador ANUNCIAR toque. O user-agent sozinho não faz isso — medido:
// com UA de iPad, ontouchstart continuava false. Quem liga é a flag
// --touch-events=enabled do Chromium (no tarsila-chromium). Mas ela apenas
// ANUNCIA a capacidade: o mouse continua emitindo eventos de mouse, então
// arrastar a barra de progresso ou deslizar continua sem efeito. Este script
// fecha a lacuna sintetizando touchstart/touchmove/touchend a partir do
// arrasto.
//
// SÓ EM ARRASTO, de propósito: cliques simples já funcionam com o mouse. Se
// sintetizássemos toque também no clique, a página trataria o mesmo gesto duas
// vezes (uma pelo toque, outra pelo clique) e botões disparariam em dobro.
// Por isso só entra em ação depois de LIMIAR pixels de movimento com o botão
// pressionado, e aí suprime o "click" final, que já foi consumido como gesto.
// ---------------------------------------------------------------------------
(() => {
  "use strict";
  if (!("ontouchstart" in window) || typeof Touch !== "function"
      || typeof TouchEvent !== "function") return;

  const LIMIAR = 8;                 // px antes de considerar que é arrasto
  let origem = null, alvo = null, arrastando = false;

  const toque = (e) => new Touch({
    identifier: 1, target: alvo,
    clientX: e.clientX, clientY: e.clientY,
    screenX: e.screenX, screenY: e.screenY,
    pageX: e.pageX, pageY: e.pageY,
    radiusX: 11, radiusY: 11, rotationAngle: 0, force: 1
  });

  const emitir = (tipo, e, manterLista) => {
    if (!alvo) return;
    const t = toque(e);
    const lista = manterLista ? [t] : [];
    try {
      alvo.dispatchEvent(new TouchEvent(tipo, {
        bubbles: true, cancelable: true, composed: true,
        touches: lista, targetTouches: lista, changedTouches: [t]
      }));
    } catch (err) { /* alvo pode ter sumido do DOM */ }
  };

  addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    origem = { x: e.clientX, y: e.clientY };
    alvo = e.target;
    arrastando = false;
  }, true);

  addEventListener("mousemove", (e) => {
    if (!origem) return;
    if (!arrastando) {
      if (Math.hypot(e.clientX - origem.x, e.clientY - origem.y) < LIMIAR) return;
      arrastando = true;
      emitir("touchstart", e, true);
    }
    emitir("touchmove", e, true);
  }, true);

  const soltar = (e) => {
    if (arrastando) {
      emitir("touchend", e, false);
      // o gesto já foi consumido: barra o clique que viria a seguir
      addEventListener("click", (c) => {
        c.stopImmediatePropagation(); c.preventDefault();
      }, { capture: true, once: true });
    }
    origem = null; alvo = null; arrastando = false;
  };
  addEventListener("mouseup", soltar, true);
  addEventListener("mouseleave", soltar, true);
})();
