// Tarsila — completa o disfarce do lado do JavaScript da página.
// A regra de rede troca o cabeçalho HTTP (o servidor entrega o layout mobile),
// mas a SPA continua consultando navigator.userAgent depois de carregar. Sem
// isto, o site carrega mobile e volta para desktop sozinho.
// Roda em document_start, mundo MAIN — precisa ser ANTES do script do site.
(() => {
  const ua = self.TARSILA_UA_MOBILE;
  delete self.TARSILA_UA_MOBILE;      // não deixa lixo no escopo da página
  delete self.TARSILA_SITES_MOBILE;
  if (!ua) return;
  const def = (obj, prop, val) => {
    try { Object.defineProperty(obj, prop, { get: () => val, configurable: true }); }
    catch (e) {}
  };
  def(navigator, "userAgent", ua);
  def(navigator, "vendor", "Apple Computer, Inc.");
  def(navigator, "platform", "MacIntel");
  def(navigator, "maxTouchPoints", 5);   // sites checam isto p/ ligar gestos
})();
