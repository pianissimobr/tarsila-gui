/* ═══════════════════════════════════════════════════════════════
   TARSILA STORE — motor v2 (app nativo)
   · Modo NATIVO (http://127.0.0.1:8474): estado real do dpkg via
     backend; instalar/desinstalar silenciosos; atalho na área de
     trabalho aparece/some sozinho (modelo Android).
   · Modo ARQUIVO (file://): degrada para protocolo tarsila:// +
     copiar comando, com estado em localStorage.
   · Tema claro (gelo) padrão; escuro opcional, persistido.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── TEMA ──────────────────────────────────────────────── */
  const TEMA_LS = 'tarsila.tema';
  function aplicarTema(t) {
    document.documentElement.dataset.tema = t;
    localStorage.setItem(TEMA_LS, t);
    const b = document.getElementById('tema-toggle');
    if (b) { b.textContent = t === 'claro' ? '🌙' : '☀️';
             b.title = t === 'claro' ? 'Mudar para tema escuro' : 'Mudar para tema claro'; }
  }
  aplicarTema(localStorage.getItem(TEMA_LS) || 'claro');

  /* ── MODO ──────────────────────────────────────────────── */
  const NATIVO = location.protocol === 'http:' || location.protocol === 'https:';

  /* ── DADOS ─────────────────────────────────────────────── */
  const APPS  = (window.CATALOGO_APPS  || []).map(normApp);
  const JOGOS = (window.CATALOGO_JOGOS || []).map(normJogo);
  const TUDO  = APPS.concat(JOGOS);

  function normApp(a) {
    return { tipo:'app', name:a.name, cat:a.category,
      catLabel:(a.category||'').replace(/^\S+\s/,''),
      pkg:a.pkg, apt:!!a.pkg, instalacao:a.pkg?'apt install '+a.pkg:'',
      desc:a.description, url:a.url||'', ram:a.ram||0,
      ptbr:null, gamepad:null, gpu3d:null,
      licenca:a.licenca||'', destaque:a.destaque||'',
      trilho:null, ico:a.ico||a.pkg, id:'app:'+(a.pkg||a.name) };
  }
  function normJogo(j) {
    return { tipo:'jogo', name:j.name, cat:'🎮 Jogos',
      catLabel:j.genero||'Jogos', pkg:j.pkg, apt:!!j.apt,
      instalacao:j.instalacao||'', desc:j.description, url:'',
      ram:j.ram||0, ptbr:j.ptbr, gamepad:j.gamepad, gpu3d:j.gpu3d,
      licenca:j.licenca||'', destaque:j.destaque||'',
      trilho:j.trilho, ico:j.ico, id:'jogo:'+(j.pkg||j.name) };
  }

  /* ── ESTADO DE INSTALAÇÃO (chaveado por pkg) ───────────── */
  const LS = 'tarsila.instalados';
  let instalados = new Set(NATIVO ? [] : JSON.parse(localStorage.getItem(LS)||'[]'));
  let emAndamento = new Set();          // pkgs com tarefa rodando
  const salvarLS = () => { if (!NATIVO) localStorage.setItem(LS, JSON.stringify([...instalados])); };
  const estaInstalado = it => !!it.pkg && instalados.has(it.pkg);
  const estaOcupado   = it => !!it.pkg && emAndamento.has(it.pkg);

  async function api(rota, metodo) {
    const r = await fetch(rota, { method: metodo || 'GET' });
    if (!r.ok) throw new Error((await r.json().catch(()=>({}))).erro || r.status);
    return r.json();
  }
  async function sincronizar() {
    if (!NATIVO) return;
    try {
      const d = await api('/api/instalados');
      instalados = new Set(d.instalados);
      repintarTudo();
    } catch (_) { /* backend fora do ar: loja segue navegável */ }
  }

  /* ── CAPAS ─────────────────────────────────────────────── */
  const CORES = {
    'Internet':['#3E7CB1','#27567e'], 'Escritório':['#F2B705','#b3860a'],
    'Multimídia':['#D9593D','#9c3a26'], 'Gráficos':['#C86B85','#8f4359'],
    'Games':['#1FA97A','#136c4e'], 'Jogos':['#1FA97A','#136c4e'],
    'Educação':['#E88D3C','#a95e1e'] };
  const corDe = it => CORES[Object.keys(CORES).find(k=>it.cat.includes(k))||'Internet'];
  function hash(s){ let h=0; for(let i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))>>>0; return h; }
  function capaSVG(item) {
    const [c1,c2] = corDe(item); const h = hash(item.name);
    const r1=40+h%45, r2=30+(h>>3)%50, r3=25+(h>>6)%40;
    const x1=(h>>2)%100, y1=(h>>4)%100, x2=(h>>5)%100, y2=(h>>7)%100;
    return '<svg class="blob" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'+
      '<rect width="100" height="100" fill="'+c2+'"/>'+
      '<circle cx="'+x1+'" cy="'+y1+'" r="'+r1+'" fill="'+c1+'" opacity="0.88"/>'+
      '<circle cx="'+x2+'" cy="'+y2+'" r="'+r2+'" fill="#F5F1E6" opacity="0.12"/>'+
      '<circle cx="'+((x1+60)%100)+'" cy="'+((y2+40)%100)+'" r="'+r3+'" fill="#101418" opacity="0.22"/></svg>';
  }
  function iniciais(nome){
    const p = nome.replace(/[^\p{L}\d ]/gu,'').split(' ').filter(Boolean);
    return (p.length>1 ? p[0][0]+p[1][0] : nome.slice(0,2)).toUpperCase();
  }
  /* Capa real do card: procura capas/<ico>.jpg e, se não houver, tenta
     capas/<ico>.png (importação de ícones em qualquer dos dois formatos);
     sem arquivo nenhum, fica o blob SVG gerado + iniciais. */
  function fotoTag(item, classe) {
    return '<img class="'+classe+'" loading="eager" decoding="sync" data-tarsila-ok="1" alt="" '+
      'src="capas/'+encodeURIComponent(item.ico)+'.jpg" '+
      'onerror="if(!this.dataset.png){this.dataset.png=1;this.src=this.src.replace(/\\.jpg$/,\'.png\');}else{this.remove();}" '+
      'onload="this.parentElement.classList.add(\'foto-ok\')">';
  }

  /* ── HELPERS ───────────────────────────────────────────── */
  const $ = s => document.querySelector(s);
  const esc = s => String(s??'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function badges(item, mini) {
    const b=[]; const cls = mini?'mini':'badge';
    if (item.ram) b.push('<span class="'+cls+' '+(mini?'m-ram':'b-ram')+'">'+(item.ram>=1024?(item.ram/1024)+' GB':item.ram+' MB')+' RAM</span>');
    if (!mini) {
      if (item.ptbr)    b.push('<span class="badge b-ok">PT-BR</span>');
      if (item.gamepad) b.push('<span class="badge b-ok">🎮 Controle</span>');
      if (item.gpu3d)   b.push('<span class="badge b-warn">Requer 3D</span>');
      if (item.licenca) b.push('<span class="badge">'+esc(item.licenca)+'</span>');
      if (!item.apt)    b.push('<span class="badge b-sol">Instalação manual</span>');
    }
    if (estaInstalado(item)) b.push('<span class="'+(mini?'mini m-inst':'badge b-ok')+'">✓ Instalado</span>');
    return b.join('');
  }

  /* Nome do app sempre visível embaixo (decisão de UX p/ público leigo) */
  function cardHTML(item) {
    return '<button class="card" data-id="'+esc(item.id)+'" data-pkg="'+esc(item.pkg||'')+'" aria-label="'+esc(item.name)+'">'+
      '<div class="capa">'+capaSVG(item)+fotoTag(item,'capa-foto')+
        '<div class="capa-badges">'+badges(item,true)+'</div>'+
        '<div class="capa-ini">'+esc(iniciais(item.name))+'</div>'+
        '<div class="capa-pkg">'+esc(item.pkg||item.tipo)+'</div>'+
      '</div>'+
      '<div class="card-info"><h3>'+esc(item.name)+'</h3><p>'+esc(item.desc)+'</p></div>'+
    '</button>';
  }
  function railHTML(titulo, itens) {
    if (!itens.length) return '';
    return '<section class="rail">'+
      '<div class="rail-head"><h2>'+esc(titulo)+'</h2><span class="rail-n">'+itens.length+' títulos</span></div>'+
      '<button class="rail-arrow prev" aria-label="Anterior">‹</button>'+
      '<div class="rail-body">'+itens.map(cardHTML).join('')+'</div>'+
      '<button class="rail-arrow next" aria-label="Próximo">›</button></section>';
  }

  /* ── HERO ──────────────────────────────────────────────── */
  const DESTAQUES = [
    ...JOGOS.filter(j=>j.destaque && j.apt).slice(0,4),
    ...APPS.filter(a=>['FreeTube','AbiWord','Pinta'].includes(a.name))
  ].slice(0,6);
  let heroIdx=0, heroTimer=null;

  function pintarHero(i) {
    heroIdx=i; const d=DESTAQUES[i]; if(!d) return;
    $('#hero-art').innerHTML = capaSVG(d)+fotoTag(d,'hero-foto');
    $('#hero-eyebrow').textContent = (d.tipo==='jogo'?'Jogo em destaque · ':'App em destaque · ')+d.catLabel;
    $('#hero-title').textContent = d.name;
    $('#hero-meta').innerHTML = badges(d);
    $('#hero-desc').textContent = d.destaque ? d.desc+' — '+d.destaque : d.desc;
    configurarBotaoAcao($('#hero-install'), d);
    $('#hero-details').onclick = () => abrirModal(d);
    document.querySelectorAll('#hero-dots button').forEach((el,j)=>el.classList.toggle('on',j===i));
  }
  function iniciarHero() {
    $('#hero-dots').innerHTML = DESTAQUES.map((_,i)=>'<button role="tab" aria-label="Destaque '+(i+1)+'"></button>').join('');
    document.querySelectorAll('#hero-dots button').forEach((el,i)=>
      el.addEventListener('click',()=>{ pintarHero(i); reiniciarTimer(); }));
    pintarHero(0); reiniciarTimer();
  }
  function reiniciarTimer() {
    clearInterval(heroTimer);
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches)
      heroTimer = setInterval(()=>pintarHero((heroIdx+1)%DESTAQUES.length), 9000);
  }

  function montarHome() {
    const r=[];
    r.push(railHTML('Novos na loja', TUDO.slice(0,12)));
    r.push(railHTML('Superleves — rodam com 256 MB', TUDO.filter(x=>x.ram>0&&x.ram<=256)));
    r.push(railHTML('Jogos para jogar no controle', JOGOS.filter(j=>j.gamepad)));
    ['🌐 Internet','💼 Escritório','🎬 Multimídia','🎨 Gráficos','🎓 Educação','🎮 Games','💻 Programação','🛡️ Utilitários'].forEach(c=>
      r.push(railHTML(c, APPS.filter(a=>a.cat===c))));
    ['Corrida','Plataforma','Estratégia','RPG & Aventura','Tiro & Ação','Gestão & Simulação','Arcade & Casual','Educativo'].forEach(t=>
      r.push(railHTML('🎮 '+t, JOGOS.filter(j=>j.trilho===t))));
    $('#rails-home').innerHTML = r.join('');
  }

  document.addEventListener('click', e => {
    const arrow = e.target.closest('.rail-arrow');
    if (arrow) {
      const body = arrow.parentElement.querySelector('.rail-body');
      body.scrollBy({ left:(arrow.classList.contains('next')?1:-1)*body.clientWidth*.85, behavior:'smooth' });
      return;
    }
    const card = e.target.closest('.card');
    if (card) { const it = TUDO.find(x=>x.id===card.dataset.id); if (it) abrirModal(it); }
  });

  /* ── GRID ──────────────────────────────────────────────── */
  let filtroAtivo='', gridItens=[];
  function montarGrid(titulo, sub, itens, chips) {
    gridItens = itens;
    $('#grid-title').textContent = titulo;
    $('#grid-sub').textContent = sub;
    const fdiv = $('#grid-filters');
    if (chips && chips.length) {
      fdiv.innerHTML = '<button data-f="" class="'+(!filtroAtivo?'on':'')+'">Todos</button>'+
        chips.map(c=>'<button data-f="'+esc(c)+'" class="'+(filtroAtivo===c?'on':'')+'">'+esc(c)+'</button>').join('');
      fdiv.onclick = e => {
        const b=e.target.closest('button'); if(!b) return;
        filtroAtivo=b.dataset.f;
        fdiv.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));
        pintarGrid();
      };
    } else fdiv.innerHTML='';
    pintarGrid();
  }
  function pintarGrid() {
    const vis = filtroAtivo
      ? gridItens.filter(x=>x.cat.includes(filtroAtivo)||x.trilho===filtroAtivo)
      : gridItens;
    $('#grid').innerHTML = vis.map(cardHTML).join('');
    $('#grid-empty').hidden = vis.length>0;
  }

  /* ── MODAL ─────────────────────────────────────────────── */
  let modalItem=null;
  function configurarBotaoAcao(botao, item) {
    botao.disabled = false;
    botao.classList.remove('done','btn-remove');
    botao.classList.add('btn-sol');
    if (!item.apt) { botao.textContent='Instalação manual'; botao.onclick=()=>instalar(item); return; }
    if (estaOcupado(item)) {
      botao.disabled = true;
      botao.textContent = instalados.has(item.pkg) ? 'Removendo…' : 'Instalando…';
    } else if (estaInstalado(item)) {
      botao.classList.remove('btn-sol');
      botao.classList.add('btn-remove');
      botao.textContent = '🗑  Desinstalar';
      botao.onclick = () => desinstalar(item);
    } else {
      botao.textContent = '▶  Instalar';
      botao.onclick = () => instalar(item);
    }
  }
  function abrirModal(item) {
    modalItem=item;
    $('#m-art').innerHTML = capaSVG(item)+fotoTag(item,'hero-foto');
    $('#m-cat').textContent = item.cat+(item.tipo==='jogo'?' · '+item.catLabel:'');
    $('#m-title').textContent = item.name;
    $('#m-meta').innerHTML = badges(item);
    $('#m-desc').textContent = item.desc;
    const q=$('#m-quote');
    q.hidden=!item.destaque; q.textContent=item.destaque?'“'+item.destaque+'”':'';
    $('#m-status').textContent = estaOcupado(item)
      ? 'Trabalhando em segundo plano — pode continuar navegando.' : '';
    configurarBotaoAcao($('#m-install'), item);
    $('#m-copy').onclick = () => copiarCmd(item);
    const site=$('#m-site');
    site.hidden=!item.url; if(item.url) site.href=item.url;
    $('#m-cmd').textContent = item.apt ? 'sudo apt install '+item.pkg : item.instalacao;
    $('#modal').hidden=false;
    document.body.style.overflow='hidden';
    $('.modal-x').focus();
  }
  function fecharModal(){ $('#modal').hidden=true; modalItem=null; document.body.style.overflow=''; }
  $('#modal').addEventListener('click', e=>{ if(e.target.closest('[data-close]')) fecharModal(); });

  /* ── INSTALAR / DESINSTALAR ────────────────────────────── */
  async function instalar(item) {
    if (!item.apt) {
      copiarCmd(item);
      toast('Este título não está no apt — instruções copiadas: '+item.instalacao);
      return;
    }
    if (NATIVO) {
      try {
        await api('/api/instalar/'+item.pkg, 'POST');
        emAndamento.add(item.pkg);
        toast('Instalando '+item.name+' em segundo plano…');
        repintarTudo(); vigiarTarefas();
      } catch (e) { toast('Não foi possível iniciar: '+e.message); }
      return;
    }
    // modo file:// — protocolo legado
    try {
      const f=document.createElement('iframe'); f.style.display='none';
      f.src='tarsila://install/'+encodeURIComponent(item.pkg);
      document.body.appendChild(f); setTimeout(()=>f.remove(),4000);
    } catch(_){}
    instalados.add(item.pkg); salvarLS();
    toast('Instalação de '+item.name+' solicitada ao sistema.');
    repintarTudo();
  }
  async function desinstalar(item) {
    if (NATIVO) {
      try {
        await api('/api/desinstalar/'+item.pkg, 'POST');
        emAndamento.add(item.pkg);
        toast('Removendo '+item.name+'…');
        repintarTudo(); vigiarTarefas();
      } catch (e) { toast('Não foi possível iniciar: '+e.message); }
      return;
    }
    instalados.delete(item.pkg); salvarLS();
    copiarCmd(item, 'sudo apt remove '+item.pkg);
    toast('Comando de remoção copiado: sudo apt remove '+item.pkg);
    repintarTudo();
  }

  /* Polling das tarefas do backend */
  let vigia=null;
  function vigiarTarefas() {
    if (vigia || !NATIVO) return;
    vigia = setInterval(async () => {
      try {
        const d = await api('/api/tarefas');
        let mudou=false;
        for (const [pkg,t] of Object.entries(d.tarefas||{})) {
          if (!emAndamento.has(pkg)) continue;
          if (t.estado==='ok') {
            emAndamento.delete(pkg); mudou=true;
            const it = TUDO.find(x=>x.pkg===pkg);
            if (t.acao==='instalar') {
              instalados.add(pkg);
              toast('✓ '+(it?it.name:pkg)+' instalado — o atalho já está na área de trabalho.');
            } else {
              instalados.delete(pkg);
              toast((it?it.name:pkg)+' removido do computador.');
            }
          } else if (t.estado==='erro') {
            emAndamento.delete(pkg); mudou=true;
            toast('Falha com '+pkg+': verifique a internet e tente de novo.');
          }
        }
        if (mudou) { await sincronizar(); }
        if (!emAndamento.size) { clearInterval(vigia); vigia=null; }
      } catch(_){}
    }, 2500);
  }

  function copiarCmd(item, forcado) {
    const cmd = forcado || (item.apt ? 'sudo apt install '+item.pkg : item.instalacao);
    const fim = () => toast('Comando copiado: '+cmd);
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(cmd).then(fim, ()=>copiarLegado(cmd,fim));
    else copiarLegado(cmd,fim);
  }
  function copiarLegado(txt,fim){
    const t=document.createElement('textarea');
    t.value=txt; document.body.appendChild(t); t.select();
    try{ document.execCommand('copy'); }catch(_){}
    t.remove(); fim();
  }

  function repintarTudo() {
    // atualiza badges dos cards visíveis, hero e modal aberto
    document.querySelectorAll('.card').forEach(c => {
      const it = TUDO.find(x=>x.id===c.dataset.id); if(!it) return;
      const bd = c.querySelector('.capa-badges');
      if (bd) bd.innerHTML = badges(it, true);
    });
    pintarHero(heroIdx);
    if (modalItem) {
      $('#m-meta').innerHTML = badges(modalItem);
      $('#m-status').textContent = estaOcupado(modalItem)
        ? 'Trabalhando em segundo plano — pode continuar navegando.' : '';
      configurarBotaoAcao($('#m-install'), modalItem);
    }
  }

  let toastTimer=null;
  function toast(msg){
    const t=$('#toast'); t.textContent=msg; t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer=setTimeout(()=>t.classList.remove('show'),4200);
  }

  /* ── BUSCA ─────────────────────────────────────────────── */
  const busca=$('#search'); let buscaTimer=null;
  busca.addEventListener('input', () => {
    clearTimeout(buscaTimer);
    buscaTimer=setTimeout(()=>{
      const q=busca.value.trim().toLowerCase();
      if(!q){ irPara(location.hash.startsWith('#/busca')?'#/':location.hash||'#/'); return; }
      location.hash='#/busca';
      const norm=s=>s.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu,'');
      const nq=norm(q);
      const res=TUDO.filter(x=>norm(x.name).includes(nq)||norm(x.desc).includes(nq)||
        (x.pkg&&x.pkg.includes(nq))||norm(x.catLabel).includes(nq));
      filtroAtivo=''; mostrar('grid');
      montarGrid('Resultados para “'+busca.value.trim()+'”', res.length+' títulos encontrados', res, null);
    },160);
  });
  document.addEventListener('keydown', e=>{
    if(e.key==='/'&&document.activeElement!==busca){ e.preventDefault(); busca.focus(); }
    if(e.key==='Escape'){ if(!$('#modal').hidden) fecharModal(); else busca.blur(); }
  });

  /* ── ROTAS ─────────────────────────────────────────────── */
  function mostrar(view){
    $('#view-home').hidden = view!=='home';
    $('#view-grid').hidden = view!=='grid';
    window.scrollTo(0,0);
  }
  function marcarNav(rota){
    document.querySelectorAll('.nav-links a').forEach(a=>
      a.classList.toggle('on', a.dataset.route===rota));
  }
  function irPara(hash){
    filtroAtivo='';
    if(hash==='#/apps'){
      mostrar('grid'); marcarNav('apps');
      montarGrid('Aplicativos', APPS.length+' apps curados para ARM — instalação com um clique',
        APPS, ['Internet','Escritório','Multimídia','Gráficos','Educação','Games','Programação','Utilitários']);
    } else if(hash==='#/jogos'){
      mostrar('grid'); marcarNav('jogos');
      montarGrid('Jogos', JOGOS.length+' jogos open source testados em hardware modesto',
        JOGOS, ['Corrida','Plataforma','Estratégia','RPG & Aventura','Tiro & Ação','Gestão & Simulação','Arcade & Casual','Educativo']);
    } else if(hash==='#/leves'){
      mostrar('grid'); marcarNav('leves');
      const leves=TUDO.filter(x=>x.ram>0&&x.ram<=512).sort((a,b)=>a.ram-b.ram);
      montarGrid('Superleves','Títulos que rodam confortavelmente com até 512 MB de RAM',leves,null);
    } else if(hash==='#/busca'){
      mostrar('grid'); marcarNav('');
    } else {
      mostrar('home'); marcarNav('home');
    }
  }
  window.addEventListener('hashchange',()=>irPara(location.hash));

  let navTick=false;
  window.addEventListener('scroll',()=>{
    if(navTick) return; navTick=true;
    requestAnimationFrame(()=>{
      $('#nav').classList.toggle('solid', window.scrollY>24);
      navTick=false;
    });
  },{passive:true});

  /* ── BOOT ──────────────────────────────────────────────── */
  document.getElementById('tema-toggle').addEventListener('click', ()=>
    aplicarTema(document.documentElement.dataset.tema==='claro'?'escuro':'claro'));
  aplicarTema(document.documentElement.dataset.tema); // sincroniza ícone do botão

  montarHome();
  iniciarHero();
  irPara(location.hash||'#/');
  $('#foot-count').textContent =
    APPS.length+' apps · '+JOGOS.length+' jogos · '+(NATIVO?'modo nativo':'modo arquivo');
  sincronizar();
  if (NATIVO) setInterval(sincronizar, 60000);  // re-scan periódico do dpkg
})();
