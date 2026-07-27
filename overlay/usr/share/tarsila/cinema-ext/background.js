// ---------------------------------------------------------------------------
// Tarsila — service worker da extensão.
//   1) ponte de native messaging do Modo Cinema (comportamento original)
//   2) versão MOBILE nos sites da lista (ver sites-mobile.js)
// ---------------------------------------------------------------------------
importScripts("sites-mobile.js");

// --- 1) Modo Cinema: repassa a URL para o helper nativo ---------------------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  chrome.runtime.sendNativeMessage("br.tarsila.cinema", msg, (resp) => {
    if (chrome.runtime.lastError) {
      sendResponse({ ok: false, erro: chrome.runtime.lastError.message });
    } else {
      sendResponse(resp || { ok: false });
    }
  });
  return true; // resposta assíncrona
});

// --- 2) Versão mobile nos sites curados -------------------------------------
// São DOIS lados, e ambos são necessários:
//   header HTTP  -> decide o layout que o servidor entrega
//   navigator.*  -> decide o que a SPA faz depois de carregar
// Só um dos dois não basta: com o header sozinho o site carrega mobile e volta
// para desktop; com o navigator sozinho o servidor já mandou o layout pesado.
const TIPOS = ["main_frame", "sub_frame", "stylesheet", "script", "image",
               "font", "xmlhttprequest", "ping", "media", "websocket", "other"];
const ID_INJECAO = "tarsila-ua-mobile";

const padroes = () =>
  self.TARSILA_SITES_MOBILE.flatMap(d => [`*://${d}/*`, `*://*.${d}/*`]);

async function instalarRegras() {
  // Regras DINÂMICAS: PERSISTEM no perfil. Service worker MV3 é SOB
  // DEMANDA -- em perfil já estabelecido nada dispara e o aplicar() nunca
  // roda (perfil novo funcionava, o do usuário não). Com regra dinâmica,
  // instalada uma vez, continua valendo mesmo sem o SW acordar.
  // Ruleset ESTÁTICO não serve: o Chromium ignora modifyHeaders sobre
  // User-Agent nele, silenciosamente.
  const antigas = await chrome.declarativeNetRequest.getDynamicRules();
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: antigas.map(r => r.id),
    addRules: self.TARSILA_SITES_MOBILE.map((dominio, i) => ({
      id: i + 1,
      priority: 100,
      condition: { urlFilter: "||" + dominio, isUrlFilterCaseSensitive: false,
                   resourceTypes: TIPOS },
      action: { type: "modifyHeaders", requestHeaders: [
        { header: "User-Agent", operation: "set", value: self.TARSILA_UA_MOBILE }] }
    }))
  });
}

async function registrarInjecao() {
  try { await chrome.scripting.unregisterContentScripts({ ids: [ID_INJECAO] }); }
  catch (e) { /* ainda não existia */ }
  await chrome.scripting.registerContentScripts([{
    id: ID_INJECAO,
    matches: padroes(),
    js: ["sites-mobile.js", "ua-main.js", "toque.js"],
    runAt: "document_start",
    allFrames: true,
    world: "MAIN"
  }]);
}

async function recarregarAbas() {
  // O service worker sobe PREGUIÇOSAMENTE: quando o navegador abre direto numa
  // URL da lista, a primeira navegação corre na frente das regras e o site vem
  // desktop. Uma recarga resolve — e só acontece uma vez, no arranque.
  try {
    for (const aba of await chrome.tabs.query({ url: padroes() }))
      chrome.tabs.reload(aba.id);
  } catch (e) {}
}

async function aplicar() {
  await instalarRegras();
  await registrarInjecao();
  await recarregarAbas();
}
chrome.runtime.onInstalled.addListener(aplicar);
chrome.runtime.onStartup.addListener(aplicar);
aplicar();
