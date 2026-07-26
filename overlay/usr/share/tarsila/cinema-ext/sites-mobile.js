// ---------------------------------------------------------------------------
// Tarsila — sites que devem ser servidos na versão MOBILE.
//
// PARA ADICIONAR UM SITE: basta acrescentar o domínio em TARSILA_SITES_MOBILE.
// Nada mais precisa mudar — o service worker lê esta lista e registra sozinho
// tanto a regra de rede quanto a injeção na página.
//
// Use o domínio "de raiz" (sem www). O casamento é por sufixo de domínio, então
// "facebook.com" cobre www.facebook.com, m.facebook.com, web.facebook.com etc.
//
// NÃO colocar aqui: web.whatsapp.com — o WhatsApp Web RECUSA user-agent mobile
// e manda usar o celular. Ele quer desktop, que já é o padrão.
// ---------------------------------------------------------------------------
self.TARSILA_SITES_MOBILE = [
  "youtube.com",
  "facebook.com",
  "instagram.com",
  "x.com",
];

// iPad em vez de celular: numa TV a janela é deitada e larga, então o layout de
// tablet aproveita a tela; o de celular deixaria duas tarjas pretas enormes.
self.TARSILA_UA_MOBILE =
  "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 " +
  "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
