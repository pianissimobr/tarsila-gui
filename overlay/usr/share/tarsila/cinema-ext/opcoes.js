// Tela de Ajustes. A extensao NAO escreve em disco: quem grava e o host nativo
// (br.tarsila.cinema), em ~/.config/tarsila/. As mesmas chaves sao lidas pelo
// tarsila-chromium (funcao _pref) e pelo proprio host (qualidade).
const HOST = "br.tarsila.cinema";
const CAIXAS = ["gpu", "hwdec", "cinema", "mobile", "jitless", "tierb"];

const aviso = (texto) => {
  const el = document.getElementById("aviso");
  el.textContent = texto;
  el.classList.add("ver");
  setTimeout(() => el.classList.remove("ver"), 2800);
};

chrome.runtime.sendNativeMessage(HOST, { acao: "ler" }, (r) => {
  if (chrome.runtime.lastError || !r || !r.ok) { aviso("Não consegui ler os ajustes."); return; }
  const q = document.querySelector(
    `input[name="qualidade"][value="${r.valores.qualidade || "boa"}"]`);
  if (q) q.checked = true;
  for (const nome of CAIXAS) {
    const el = document.querySelector(`input[name="${nome}"]`);
    if (el) el.checked = (r.valores[nome] ?? "1") === "1";
  }
});

document.getElementById("salvar").addEventListener("click", () => {
  const valores = {};
  const q = document.querySelector('input[name="qualidade"]:checked');
  if (q) valores.qualidade = q.value;
  for (const nome of CAIXAS) {
    const el = document.querySelector(`input[name="${nome}"]`);
    if (el) valores[nome] = el.checked ? "1" : "0";
  }
  chrome.runtime.sendNativeMessage(HOST, { acao: "gravar", valores }, (r) => {
    if (chrome.runtime.lastError || !r || !r.ok) aviso("Não consegui salvar.");
    else aviso("Salvo. Vale ao abrir o navegador de novo.");
  });
});
