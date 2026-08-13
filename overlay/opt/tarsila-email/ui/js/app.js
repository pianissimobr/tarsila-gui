const API = "";
const PAGE_SIZE = 10;
const FOLDER_ORDER = ["inbox", "sent", "drafts", "starred", "spam", "trash"];
const FOLDER_ICONS = {
  inbox: "📥", sent: "📤", drafts: "📝", starred: "⭐", spam: "🚫", trash: "🗑",
};

let folder = "inbox";
let page = 1;
let selectedId = null;
let attachments = [];
let searchQuery = "";
let accounts = [];

const $ = (s) => document.querySelector(s);
const list = $("#msg-list");
const loading = $("#loading");
const readView = $("#read-view");
const readEmpty = $(".read-empty");

async function api(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function fmtDate(s) {
  if (!s) return "";
  try {
    const d = new Date(s);
    const now = new Date();
    if (d.toDateString() === now.toDateString())
      return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  } catch { return s.slice(0, 12); }
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}

function showSyncToast(msg, isError = false) {
  const t = $("#sync-toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.classList.remove("hidden");
  clearTimeout(showSyncToast._tm);
  showSyncToast._tm = setTimeout(() => t.classList.add("hidden"), 10000);
}

function setProfile(st) {
  const img = $("#profile-img");
  const icon = $("#profile-icon");
  $("#account-label").textContent = st.email || "";
  $("#account-label").title = st.email || "";
  if (st.avatar) {
    img.src = st.avatar;
    img.onload = () => { img.classList.remove("hidden"); icon.classList.add("hidden"); };
    img.onerror = () => { img.classList.add("hidden"); icon.classList.remove("hidden"); };
  } else {
    img.classList.add("hidden");
    icon.classList.remove("hidden");
  }
}

async function init() {
  const st = await api("/api/bootstrap");
  if (!st.configured) {
    window.location.reload();
    return;
  }
  accounts = st.accounts || [];
  setProfile(st);
  renderFolders(st.folders || []);
  await syncAndLoad();
  bindEvents();
}

async function loadFolders() {
  const { folders } = await api("/api/folders");
  renderFolders(folders || []);
}

function renderFolders(folders) {
  const nav = $("#folder-nav");
  nav.innerHTML = "";
  const sorted = [...folders].sort(
    (a, b) => FOLDER_ORDER.indexOf(a.id) - FOLDER_ORDER.indexOf(b.id)
  );
  (sorted.length ? sorted : [{ id: "inbox", name: "Caixa de entrada" }]).forEach((f) => {
    const b = document.createElement("button");
    b.className = "folder-item" + (f.id === folder ? " active" : "");
    b.innerHTML = `<span>${FOLDER_ICONS[f.id] || "📁"}</span><span>${esc(f.name)}</span>`;
    b.onclick = () => {
      folder = f.id; page = 1; selectedId = null; searchQuery = "";
      $("#search").value = "";
      loadMessages(); updateFolderActive();
    };
    nav.appendChild(b);
  });
}

function updateFolderActive() {
  document.querySelectorAll(".folder-item").forEach((el) => el.classList.remove("active"));
  const items = [...$("#folder-nav").querySelectorAll(".folder-item")];
  const idx = FOLDER_ORDER.indexOf(folder);
  if (items[idx]) items[idx].classList.add("active");
  else if (items[0]) items[0].classList.add("active");
}

async function syncAndLoad() {
  loading.classList.remove("hidden");
  try {
    const { messages, has_more } = await api("/api/sync", {
      method: "POST",
      body: JSON.stringify({ folder, limit: PAGE_SIZE }),
    });
    showSyncToast("Sincronização feita");
    loading.classList.add("hidden");
    list.innerHTML = "";
    (messages || []).forEach((m) => list.appendChild(renderItem(m)));
    $("#btn-more").classList.toggle("hidden", !has_more || !!searchQuery);
  } catch (e) {
    showSyncToast("Erro de sincronização: " + e.message, true);
    await loadMessages();
  }
}

async function loadMessages(append = false) {
  if (!append) { list.innerHTML = ""; if (!searchQuery) page = 1; }
  loading.classList.remove("hidden");
  try {
    let url = `/api/messages?folder=${folder}&page=${page}&limit=${PAGE_SIZE}`;
    if (searchQuery) url += `&q=${encodeURIComponent(searchQuery)}`;
    const { messages, has_more } = await api(url);
    loading.classList.add("hidden");
    messages.forEach((m) => list.appendChild(renderItem(m)));
    $("#btn-more").classList.toggle("hidden", !has_more || !!searchQuery);
  } catch (e) {
    loading.textContent = "Erro: " + e.message;
  }
}

function renderItem(m) {
  const li = document.createElement("li");
  li.className = "msg-item" + (m.is_read ? "" : " unread") + (m.id === selectedId ? " active" : "");
  li.dataset.id = m.id;
  li.innerHTML = `
    <button class="msg-star ${m.is_starred ? "on" : ""}" data-star="${m.id}">★</button>
    <span class="msg-from">${esc(m.sender)}</span>
    <span class="msg-date">${fmtDate(m.date_str)}</span>
    <span class="msg-subject">${esc(m.subject)}</span>
    <span class="msg-snippet">${esc(m.snippet || "")}</span>`;
  li.onclick = (e) => {
    if (e.target.dataset.star) return;
    openMessage(m.id);
  };
  li.querySelector("[data-star]").onclick = async (e) => {
    e.stopPropagation();
    await api(`/api/messages/${m.id}/star`, { method: "POST", body: "{}" });
    loadMessages();
  };
  return li;
}

async function openMessage(id) {
  selectedId = id;
  document.querySelectorAll(".msg-item").forEach((el) =>
    el.classList.toggle("active", el.dataset.id === id));
  readEmpty.classList.add("hidden");
  readView.classList.remove("hidden");
  readView.innerHTML = "<p class='loading'>Abrindo…</p>";
  try {
    await api(`/api/messages/${id}/read`, { method: "POST", body: JSON.stringify({ read: true }) });
    const { message: m } = await api(`/api/messages/${id}?body=1&fmt=html`);
    const body = m.body_html
      ? `<div class="read-body">${m.body_html}</div>`
      : `<pre class="read-body">${esc(m.body_plain || m.snippet || "")}</pre>`;
    readView.innerHTML = `
      <div class="read-actions">
        <button id="act-reply">Responder</button>
        <button id="act-star">★ Estrela</button>
        <button id="act-trash" class="danger">Apagar</button>
      </div>
      <h1>${esc(m.subject)}</h1>
      <div class="read-meta"><strong>${esc(m.sender)}</strong><br>${esc(m.date_str)}</div>
      ${body}`;
    $("#act-trash").onclick = async () => {
      if (!confirm("Você deseja apagar esse e-mail?")) return;
      await api(`/api/messages/${id}/trash`, { method: "POST", body: "{}" });
      readView.classList.add("hidden");
      readEmpty.classList.remove("hidden");
      loadMessages();
    };
    $("#act-star").onclick = async () => {
      await api(`/api/messages/${id}/star`, { method: "POST", body: "{}" });
      openMessage(id);
    };
    $("#act-reply").onclick = () => {
      showCompose(m.sender.replace(/<.*>/, "").trim(), "Re: " + m.subject, "\n\n---\n" + (m.body_plain || ""));
    };
  } catch (e) {
    readView.innerHTML = `<p>Erro: ${esc(e.message)}</p>`;
  }
}

function showCompose(to = "", subject = "", body = "") {
  attachments = [];
  $("#compose-to").value = to;
  $("#compose-subject").value = subject;
  $("#compose-body").value = body;
  $("#attach-list").innerHTML = "";
  $("#compose-modal").classList.remove("hidden");
}

function renderAccountsModal() {
  const ul = $("#accounts-list");
  ul.innerHTML = "";
  accounts.forEach((a) => {
    const li = document.createElement("li");
    li.className = "account-item" + (a.active ? " active" : "");
    const av = a.avatar
      ? `<img src="${esc(a.avatar)}" alt="">`
      : `<span class="acc-icon">👤</span>`;
    li.innerHTML = `
      ${av}
      <div class="acc-info">
        <div class="acc-email">${esc(a.email)}</div>
        <div class="acc-name">${esc(a.name)}${a.active ? " · ativa" : ""}</div>
      </div>`;
    li.onclick = async () => {
      if (a.active) {
        $("#accounts-modal").classList.add("hidden");
        return;
      }
      await api("/api/accounts/switch", {
        method: "POST", body: JSON.stringify({ email: a.email }),
      });
      $("#accounts-modal").classList.add("hidden");
      folder = "inbox"; page = 1; selectedId = null;
      const st = await api("/api/status");
      accounts = st.accounts || [];
      setProfile(st);
      await loadFolders();
      await syncAndLoad();
    };
    ul.appendChild(li);
  });
}

function bindEvents() {
  $("#btn-compose").onclick = () => showCompose();
  $("#compose-close").onclick = () => $("#compose-modal").classList.add("hidden");
  $("#btn-sync").onclick = syncAndLoad;
  $("#btn-more").onclick = () => { page++; loadMessages(true); };

  let searchTimer;
  $("#search").oninput = (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchQuery = e.target.value.trim();
      page = 1;
      loadMessages();
    }, 300);
  };
  $("#search").onkeydown = (e) => {
    if (e.key === "Escape") {
      e.target.value = "";
      searchQuery = "";
      page = 1;
      loadMessages();
    }
  };

  $("#btn-profile").onclick = (e) => {
    e.stopPropagation();
    $("#profile-menu").classList.toggle("hidden");
  };
  document.addEventListener("click", () => $("#profile-menu").classList.add("hidden"));

  $("#menu-accounts").onclick = async (e) => {
    e.stopPropagation();
    $("#profile-menu").classList.add("hidden");
    const { accounts: accs } = await api("/api/accounts");
    accounts = accs;
    renderAccountsModal();
    $("#accounts-modal").classList.remove("hidden");
  };

  $("#menu-logout").onclick = async (e) => {
    e.stopPropagation();
    if (!confirm("Sair apaga todas as contas e dados locais. Continuar?")) return;
    await api("/api/logout", { method: "POST", body: "{}" });
    window.location.reload();
  };

  $("#accounts-close").onclick = () => $("#accounts-modal").classList.add("hidden");
  $("#btn-add-account").onclick = async () => {
    $("#accounts-modal").classList.add("hidden");
    await api("/api/accounts/open-setup", { method: "POST", body: "{}" });
  };

  $("#compose-files").onchange = async (e) => {
    for (const f of e.target.files) {
      const buf = await f.arrayBuffer();
      const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
      attachments.push({ name: f.name, data: b64 });
      const li = document.createElement("li");
      li.textContent = f.name;
      $("#attach-list").appendChild(li);
    }
  };
  $("#compose-send").onclick = async () => {
    const to = $("#compose-to").value.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    if (!to.length) return alert("Informe o destinatário");
    const dest = to.join(", ");
    if (!confirm(`Confirma o envio desse e-mail para ${dest}?`)) return;
    try {
      await api("/api/messages/send", {
        method: "POST",
        body: JSON.stringify({
          to, subject: $("#compose-subject").value,
          body: $("#compose-body").value, attachments,
        }),
      });
      $("#compose-modal").classList.add("hidden");
      folder = "sent";
      syncAndLoad();
    } catch (e) { alert("Erro ao enviar: " + e.message); }
  };
  $("#compose-draft").onclick = async () => {
    try {
      await api("/api/drafts", {
        method: "POST",
        body: JSON.stringify({
          to: $("#compose-to").value, subject: $("#compose-subject").value,
          body: $("#compose-body").value,
        }),
      });
      $("#compose-modal").classList.add("hidden");
      alert("Rascunho salvo no Gmail");
    } catch (e) { alert("Erro: " + e.message); }
  };
}

init();
