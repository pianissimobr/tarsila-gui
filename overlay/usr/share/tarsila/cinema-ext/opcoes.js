// Tela de ajustes da extensao. Ela NAO consegue escrever em disco, entao fala
// com o host nativo (br.tarsila.cinema), que grava em ~/.config/tarsila/.
// As mesmas chaves sao lidas pelo tarsila-chromium (gpu) e pelo host (qualidade).
const HOST = "br.tarsila.cinema";

const marcar = (nome, valor) => {
  const alvo = document.querySelector(`input[name="${nome}"][value="${valor}"]`);
  if (alvo) alvo.checked = true;
};

const aviso = (texto) => {
  const el = document.getElementById("aviso");
  el.textContent = texto;
  el.classList.add("ver");
  setTimeout(() => el.classList.remove("ver"), 2600);
};

chrome.runtime.sendNativeMessage(HOST, { acao: "ler" }, (r) => {
  if (chrome.runtime.lastError || !r || !r.ok) {
    aviso("Não consegui ler os ajustes.");
    return;
  }
  marcar("q", r.valores.qualidade || "boa");
  marcar("g", r.valores.gpu || "1");
});

document.getElementById("salvar").addEventListener("click", () => {
  const q = document.querySelector('input[name="q"]:checked');
  const g = document.querySelector('input[name="g"]:checked');
  const valores = {};
  if (q) valores.qualidade = q.value;
  if (g) valores.gpu = g.value;
  chrome.runtime.sendNativeMessage(HOST, { acao: "gravar", valores }, (r) => {
    if (chrome.runtime.lastError || !r || !r.ok) {
      aviso("Não consegui salvar.");
    } else {
      aviso("Salvo. Vale ao abrir o navegador de novo.");
    }
  });
});
