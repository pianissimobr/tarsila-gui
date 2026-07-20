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
