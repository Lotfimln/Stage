// js/dashboard.js
(() => {
  const { api, state } = window.core;     // fetch + JWT
  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));
  const shorten = (s, n=40) => (s && s.length>n ? s.slice(0,n-1)+'…' : (s||'(N/A)'));

  // ---------- Thème Chart.js sombre
  const baseOpts = {
    responsive: true, maintainAspectRatio: false,
    scales: {
      x: { grid: { color: "rgba(255,255,255,.08)" }, ticks: { color: "#cbd5e1" } },
      y: { grid: { color: "rgba(255,255,255,.08)" }, ticks: { color: "#cbd5e1" } },
    },
    plugins: {
      legend:  { labels: { color: "#e5e7eb" } },
      tooltip: { titleColor: "#e5e7eb", bodyColor: "#e5e7eb" },
    },
  };

// ---------- Zoom modal (robuste)
const zoom = (() => {
  const modal  = document.getElementById("zoomModal");
  const title  = document.getElementById("zoomTitle");
  const canvas = document.getElementById("zoomCanvas");
  const ctx    = canvas?.getContext("2d");
  let zchart   = null;

  function destroy() { if (zchart) { try { zchart.destroy(); } catch {} zchart = null; } }

  function buildConfig(srcChart) {
    return {
      type: srcChart.config.type,
      data: {
        labels: Array.isArray(srcChart.data?.labels) ? [...srcChart.data.labels] : [],
        datasets: (srcChart.data?.datasets || []).map(ds => ({
          ...JSON.parse(JSON.stringify(ds)),
          data: Array.isArray(ds.data) ? [...ds.data] : ds.data
        }))
      },
      options: { ...baseOpts, responsive: true, maintainAspectRatio: false }
    };
  }

  function sizeCanvas() {
    const wrap = modal?.querySelector(".chart-wrap");
    if (!wrap) return;
    const r = wrap.getBoundingClientRect();
    canvas.style.width  = r.width + "px";
    canvas.style.height = r.height + "px";
    canvas.width  = Math.max(1, Math.floor(r.width));
    canvas.height = Math.max(1, Math.floor(r.height));
  }

  function openFrom(srcChart, heading) {
    if (!modal || !ctx || !srcChart) return;
    destroy();
    title.textContent = heading || srcChart.canvas?.dataset?.zoomTitle || "";

    modal.classList.add("open");

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        sizeCanvas();
        zchart = new Chart(ctx, buildConfig(srcChart));
        zchart.resize();
      });
    });
  }

  // close handlers
  modal?.addEventListener("click", (e) => {
    if (e.target === modal || e.target.classList.contains("zoom-close")) {
      destroy();
      modal.classList.remove("open");
    }
  });
  window.addEventListener("resize", () => { if (modal?.classList.contains("open")) { sizeCanvas(); zchart?.resize(); } });

  return { openFrom };
})();

function enableZoom(canvas, chart, title = "") {
  if (!canvas) return;
  if (title) canvas.dataset.zoomTitle = title;
  canvas.style.cursor = "zoom-in";
  canvas.addEventListener("click", () => zoom.openFrom(chart, title));
}

  // ========== KPIs ==========
  async function loadKPIs(){
    try{
      const o = await api("/api/stats/overview");
      // tolérant aux champs
      const set = (id, v) => { const el=document.getElementById(id); if(el) el.textContent = (v ?? "—"); };
      const peopleTotal   = o.people_present ?? (typeof o.people_total==="number" && typeof o.non_positionnes==="number" ? o.people_total - o.non_positionnes : o.people_total);
      set("kpiPeople",  peopleTotal);
      set("kpiNonPos",  o.non_positionnes ?? o.nonPos ?? "—");
      set("kpiThemes",  o.themes_total    ?? o.themes_active ?? "—");
      set("kpiStructs", o.structures_total?? o.structures_active ?? "—");
      set("kpiAvg",     o.avg_themes_per_person ?? o.themes_per_person ?? "—");
    }catch(e){}
  }

  // ========== Top charts ==========
  const charts = {};
  async function loadTopCharts(){
    try{
      const [themes, structs] = await Promise.all([
        api("/api/stats/top/themes?limit=10"),
        api("/api/stats/top/structures?limit=10"),
      ]);

      // Top thématiques
      const c1 = document.getElementById("chTopThemes")?.getContext("2d");
      if (c1){
        const chart = new Chart(c1, {
          type:"bar",
          data:{
            labels: (themes||[]).map(x => shorten(x.label ?? x.LABEL ?? String(x.id ?? x.ID), 28)),
            datasets:[{ label:"Personnes", data:(themes||[]).map(x => x.cnt ?? x.CNT ?? x.count ?? 0) }]
          },
          options: baseOpts
        });
        charts.topThemes = chart;
        enableZoom(c1.canvas, chart, "Top thématiques");
      }

      // Top structures
      const c2 = document.getElementById("chTopStructs")?.getContext("2d");
      if (c2){
        const chart = new Chart(c2, {
          type:"bar",
          data:{
            labels: (structs||[]).map(x => shorten(x.label ?? x.LABEL ?? String(x.id ?? x.ID), 45)),
            datasets:[{ label:"Personnes", data:(structs||[]).map(x => x.cnt ?? x.CNT ?? x.count ?? 0) }]
          },
          options: { ...baseOpts, indexAxis:"y", scales:{ x:baseOpts.scales.y, y:baseOpts.scales.x } }
        });
        charts.topStructs = chart;
        enableZoom(c2.canvas, chart, "Top structures");
      }
    }catch(e){}
  }
  async function initModQueries(){
  const sel = document.getElementById('qrySelect');
  const paramsBox = document.getElementById('qryParams');
  const runBtn = document.getElementById('qryRun');
  const outBox = document.getElementById('qryOut');
  if (!sel || !paramsBox || !runBtn) return;

  // charge le catalogue
  sel.innerHTML = '<option value="">— choisir une requête —</option>';
  try{
    const queries = await api('/api/queries');
    (queries || []).forEach(q=>{
      const o = document.createElement('option');
      o.value = q.id; o.textContent = q.label || q.id; o.dataset.q = JSON.stringify(q);
      sel.appendChild(o);
    });
  }catch(e){ sel.innerHTML = '<option value="">(erreur de chargement)</option>'; }

  function renderParams(){
    paramsBox.innerHTML = '';
    const opt = sel.options[sel.selectedIndex]; if (!opt || !opt.value) return;
    const q = JSON.parse(opt.dataset.q || '{}');
    const fields = normalizeFields(q);

    fields.forEach(f=>{
      const wrap = document.createElement('div'); wrap.style.minWidth='220px';
      const lab  = document.createElement('div'); lab.className='small muted'; lab.textContent = f.label;
      let input;

      if (f.type==='select'){
        input = document.createElement('select');
        (f.options||[]).forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; input.appendChild(o); });
        if (f.default!==undefined) input.value=f.default;
      } else if (f.type==='checkbox'){
        input = document.createElement('input'); input.type='checkbox'; input.checked = !!f.default;
      } else {
        input = document.createElement('input'); input.type='text';
        if (f.placeholder) input.placeholder = f.placeholder;
        if (f.default!==undefined && typeof f.default!=='object') input.value = f.default;
      }
      input.id = 'qry_' + f.key;

      // mapping → pickers
      const k = f.key.toLowerCase();
      if (k==='root_theme_id')                      attachPicker(input,{mode:'single',fetcher:fetchThemesLike,minChars:0});
      if (k==='structure_id')                       attachPicker(input,{mode:'single',fetcher:fetchStructsLike,minChars:0});
      if (k==='theme_ids' || k==='exclude_theme_ids')        attachPicker(input,{mode:'multi', fetcher:fetchThemesLike,  minChars:0});
      if (k==='structure_ids' || k==='include_structures' || k==='exclude_structures')
                                                      attachPicker(input,{mode:'multi', fetcher:fetchStructsLike, minChars:0});
      if (/(^|_)person(_id)?$/.test(k) || k==='idpers') attachPicker(input,{mode:'single',fetcher:fetchPeopleLike,minChars:0});

      wrap.appendChild(lab); wrap.appendChild(input); paramsBox.appendChild(wrap);
    });
  }

  sel.onchange = renderParams;

  runBtn.onclick = async () => {
    const opt = sel.options[sel.selectedIndex];
    if (!opt || !opt.value) { alert('Choisis une requête.'); return; }

    const q = JSON.parse(opt.dataset.q || '{}');
    const fields = normalizeFields(q);

    const body = {};
    fields.forEach(f=>{
      const el = document.getElementById('qry_' + f.key);
      let val;
      if (el._getValue) val = el._getValue();
      else if (f.type==='checkbox') val = el.checked;
      else val = el.value;

      const t = String(f.rawType || '').toLowerCase();
      if (t==='int' || t==='int?') val = (val===''||val==null)?null:Number(val);
      else if (t==='int[]'){
        if (Array.isArray(val)) val = val.map(Number).filter(n=>!Number.isNaN(n));
        else val = String(val||'').split(/[,\s;]+/).filter(Boolean).map(Number).filter(n=>!Number.isNaN(n));
      } else if (t==='bool') val = !!val;

      body[f.key] = val;
    });

    const rows = await api(`/api/queries/${opt.value}`, { method:'POST', body: JSON.stringify(body) });
    renderTable(rows, 'qryTable');
    outBox.style.display = '';
  };
}

  // === Helpers pour requêtes modulables =====================================

  // 3.1 — fetchers
  async function fetchThemesLike(q){
    const term = (q ?? '').trim();
    try{
      const rows = await window.core.api('/api/themes/find?q=' + encodeURIComponent(term));
      return (rows||[]).map(r => ({ id:Number(r.id ?? r.ID), label:String(r.label ?? r.LABEL) }));
    }catch{return []}
  }
  async function fetchPeopleLike(q){
    const term = (q ?? '').trim();
    try{
      const rows = await window.core.api('/api/people/find?q=' + encodeURIComponent(term));
      return (rows||[]).map(r => ({ id:Number(r.idpers ?? r.IDPERS), label:`${r.prenom??r.PRENOM??''} ${r.nom??r.NOM??''}`.trim() }));
    }catch{return []}
  }
  async function fetchStructsLike(q){
    const term = (q ?? '').trim();
    try{
      const rows = await window.core.api('/api/structures/find?q=' + encodeURIComponent(term));
      return (rows||[]).map(r => ({ id:Number(r.id ?? r.ID), label:String(r.label ?? r.LABEL ?? r.id) }));
    }catch{return []}
  }

  // 3.2 — petit picker générique (single/multi)
  function attachPicker(input, { mode='single', fetcher, minChars=0 }){
    if (!input || input._pickerInstalled) return;
    input._pickerInstalled = true; input.autocomplete = 'off';

    // zone chips (pour le multi)
    const chips = document.createElement('div');
    chips.className = 'chips';
    input.parentNode.insertBefore(chips, input);

    const sel = []; // [{id,label}]
    const list = document.createElement('div');
    Object.assign(list.style, {position:'fixed',left:'0',top:'0',width:'280px',maxHeight:'240px',
      overflowY:'auto',zIndex:'999999',display:'none',background:'#0f172a',
      border:'1px solid #1f2937',borderRadius:'8px',padding:'4px 0',
      boxShadow:'0 8px 24px rgba(0,0,0,.35)'});
    document.body.appendChild(list);

    function hide(){ list.style.display='none'; }
    function show(){ position(); list.style.display='block'; }
    function position(){
      const r = input.getBoundingClientRect();
      list.style.left = `${r.left}px`; list.style.top = `${r.bottom+2}px`; list.style.width = `${r.width}px`;
    }
    function redrawChips(){
      chips.innerHTML = '';
      (mode==='multi' ? sel : (sel[0]?[sel[0]]:[])).forEach((it,idx)=>{
        const b = document.createElement('span'); b.className='chip'; b.textContent = it.label;
        const x = document.createElement('button'); x.type='button'; x.textContent='×';
        Object.assign(x.style,{border:'none',background:'transparent',cursor:'pointer',color:'inherit'});
        x.onclick = () => { sel.splice(idx,1); if(mode==='single') input.value=''; redrawChips(); };
        b.appendChild(x); chips.appendChild(b);
      });
    }
    function choose(it){
      if (mode==='multi'){ if (!sel.find(s=>s.id===it.id)) sel.push(it); input.value=''; }
      else { sel.splice(0,sel.length,it); input.value = it.label; }
      redrawChips(); hide();
    }
    function renderList(rows){
      list.innerHTML = '';
      rows.slice(0,25).forEach(r=>{
        const a = document.createElement('div'); a.textContent=r.label;
        Object.assign(a.style,{padding:'8px 10px',cursor:'pointer'});
        a.onmousedown = (e)=>{ e.preventDefault(); choose(r); };
        list.appendChild(a);
      });
      rows.length ? show() : hide();
    }
    async function run(q){ try{ renderList(await fetcher(q)); }catch{ renderList([]); } }

    input.addEventListener('focus', ()=> run(minChars?input.value.trim():''));
    input.addEventListener('input', ()=> {
      const q = input.value.trim();
      if (q.length < minChars) { hide(); return; }
      run(q);
    });
    document.addEventListener('click', (e)=>{ if(e.target!==input && !list.contains(e.target)) hide(); });

    // expose la valeur collectée
    input._getValue = () => (mode==='multi' ? sel.map(s=>s.id) : (sel[0]?.id ?? null));
  }

  // 3.3 — normalisation des champs (compatible ancien/nouveau format)
  function normalizeFields(q){
    if (q && q.schema && Array.isArray(q.schema.fields)) {
      return q.schema.fields.map(f => ({
        key: f.key, label: f.label || f.key, type: f.type || 'text',
        options: f.options || [], placeholder: f.placeholder || '',
        default: f.default, rawType: f.rawType || f.type || 'text'
      }));
    }
    const p = (q && q.params) ? q.params : {};
    const res = [];
    const SELECTS = { role:["*","Expert","Contributeur","Utilisateur"],
                      temporalite:["*","Présent","Passé"],
                      mode:["*","AUTO","MANU"], match:["ANY","ALL"] };
    Object.entries(p).forEach(([key,typ])=>{
      if (key in SELECTS)   { res.push({key,label:key,type:'select',options:SELECTS[key],default:SELECTS[key][0],rawType:'str'}); return; }
      if (typ==='bool')     { res.push({key,label:key,type:'checkbox',default:true,rawType:'bool'}); return; }
      if (typ==='int'||typ==='int?'){ res.push({key,label:key,type:'number',placeholder:typ,rawType:typ}); return; }
      res.push({key,label:key,type:'text',placeholder:typ,rawType:typ});
    });
    return res;
  }

  // 3.4 — rendu simple d’un tableau
  function renderTable(rows, tableId='qryTable'){
    const tbl = document.getElementById(tableId);
    const thead = tbl.querySelector('thead'); const tbody = tbl.querySelector('tbody');
    thead.innerHTML = ''; tbody.innerHTML = '';
    if (!rows || !rows.length){ tbody.innerHTML = '<tr><td style="padding:8px">Aucun résultat</td></tr>'; return; }
    const cols = Object.keys(rows[0]);
    const trh = document.createElement('tr');
    cols.forEach(c=>{ const th=document.createElement('th'); th.textContent=c; trh.appendChild(th); });
    thead.appendChild(trh);
    rows.forEach(r=>{
      const tr=document.createElement('tr');
      cols.forEach(c=>{ const td=document.createElement('td'); td.textContent = r[c] ?? ''; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
  }

  // ========== Répartition rôles / temporalité ==========
  async function loadDistribution(){
    try{
      const dist = await api("/api/stats/distribution");

      // Rôles
      const rctx = document.getElementById("chRoles")?.getContext("2d");
      if (rctx){
        const d = Array.isArray(dist?.role) ? dist.role : [];
        const chart = new Chart(rctx, {
          type:"doughnut",
          data:{ labels:d.map(x=>x.label ?? x.LABEL), datasets:[{ data:d.map(x=>x.cnt ?? x.CNT ?? 0) }] },
          options:{ ...baseOpts, cutout:"60%" }
        });
        charts.roles = chart; enableZoom(rctx.canvas, chart, "Rôles");
      }

      // Temporalité
      const tctx = document.getElementById("chTempo")?.getContext("2d");
      if (tctx){
        const d = Array.isArray(dist?.temporalite) ? dist.temporalite : [];
        const chart = new Chart(tctx, {
          type:"doughnut",
          data:{ labels:d.map(x=>x.label ?? x.LABEL), datasets:[{ data:d.map(x=>x.cnt ?? x.CNT ?? 0) }] },
          options:{ ...baseOpts, cutout:"60%" }
        });
        charts.tempo = chart; enableZoom(tctx.canvas, chart, "Temporalité");
      }
    }catch(e){ /* silencieux */ }
  }

  // ========== Autocomplete simple (un thème OBLIGATOIRE, une structure OPTIONNELLE)
  let selectedTheme  = null; // {id,label}
  let selectedStruct = null; // {id,label} | null

  function attachAutocomplete(inputId, fetchUrl, onPick, mapRow=r=>({id:r.id,label:r.label})){
    const input = document.getElementById(inputId);
    if (!input) return;
    let list=null, rows=[];

    function closeList(){ if(list){ list.remove(); list=null; } }
    function render(){
      closeList();
      list = document.createElement("div");
      list.className = "ac-list";
      document.body.appendChild(list);

      const r = input.getBoundingClientRect();

      list.style.left = `${r.left + window.scrollX}px`;
      list.style.top  = `${r.bottom + window.scrollY + 4}px`;
      list.style.width= `${Math.max(420, r.width)}px`;

      (rows||[]).forEach(row=>{
        const it = mapRow(row);
        const el = document.createElement("div");
        el.className = "ac-item";
        el.textContent = it.label;
        el.title = it.label;
        el.onclick = ()=>{ try{ onPick(it); }finally{ input.value = it.label; closeList(); } };
        list.appendChild(el);
      });
    }

    async function query(q){
      try{
        rows = await api(`${fetchUrl}?q=${encodeURIComponent(q||"")}`);
      }catch{ rows = []; }
      render();
    }
    input.addEventListener("focus", ()=>query(""));                    // pré-remplir
    input.addEventListener("input", (e)=>query(e.target.value.trim())); //affinage
    input.addEventListener("blur",  ()=>setTimeout(closeList,120));
    input.addEventListener("keydown",(e)=>{ if (e.key==="Escape") closeList(); });
  }

  attachAutocomplete(
    "acTheme",
    "/api/themes/find",
    it => { selectedTheme = it; },
    r  => ({ id:Number(r.id ?? r.ID), label:String(r.label ?? r.LABEL) })
  );

  attachAutocomplete(
    "acStruct",
    "/api/structures/find",
    it => { selectedStruct = it; },
    r  => ({ id:Number(r.id ?? r.ID), label:String(r.label ?? r.LABEL ?? r.id) })
  );


  // ========== Explorer 
  let exploreChart = null;

  function drawExplore(labels, values){
    const ctx = document.getElementById("chExplore")?.getContext("2d");
    if (!ctx) return;
    if (exploreChart) exploreChart.destroy();
    exploreChart = new Chart(ctx, {
      type:"bar",
      data:{ labels, datasets:[{ label:"Personnes (distinctes)", data:values }] },
      options:{ ...baseOpts, indexAxis:"y", scales:{ x:baseOpts.scales.y, y:baseOpts.scales.x } }
    });
    enableZoom(ctx.canvas, exploreChart, "Explorer");
  }

  async function runExplorer() {
    if (!selectedTheme?.id) { alert("Choisis un thème (autocomplétion)."); return; }

    let rows = [];
    try {
      rows = await api("/api/queries/people_by_themes", {
        method: "POST",
        body: JSON.stringify({
          theme_ids: [selectedTheme.id],
          match: "ANY",
          include_desc: true,
          role: "*",
          temporalite: "Présent",
          mode: "*",
        })
      });
    } catch (e) {
      console.error(e);
      rows = [];
    }

    // Agrège DISTINCT par structure (filtre si une structure est sélectionnée)
    const byStruct = new Map(); // 
    (rows||[]).forEach(r=>{
      const sid   = r.IDSTRUCTURE ?? r.idstructure ?? null;
      const sName = r.LIBELLESTRUCTURE ?? r.libellestructure ?? String(sid ?? "(N/A)");
      if (selectedStruct?.id && Number(sid) !== Number(selectedStruct.id)) return;
      if (!byStruct.has(sName)) byStruct.set(sName, new Set());
      byStruct.get(sName).add(r.IDPERS ?? r.idpers);
    });

    const labels = [...byStruct.keys()];
    const values = labels.map(l => byStruct.get(l).size);
    drawExplore(labels, values);
  }


  $("#btnRun")?.addEventListener("click", runExplorer);
  $("#btnReset")?.addEventListener("click", ()=>{
    selectedTheme=null; selectedStruct=null;
    $("#acTheme").value=""; $("#acStruct").value="";
    if (exploreChart){ exploreChart.destroy(); exploreChart=null; }
  });
  // --- utils souples  ---
    const pick = (r, ...names) => { for (const n of names) if (r?.[n] !== undefined) return r[n]; };

    // ===================== QUERY BUILDER =====================
    let qbRows = [];

    async function initQueryBuilder(){
      // Pickers (multi/single)
      attachPicker(document.getElementById('qbThemeInc'),  { mode:'multi',  fetcher:fetchThemesLike,  minChars:0 });
      attachPicker(document.getElementById('qbThemeExc'),  { mode:'multi',  fetcher:fetchThemesLike,  minChars:0 });
      attachPicker(document.getElementById('qbStructInc'), { mode:'multi',  fetcher:fetchStructsLike, minChars:0 });
      attachPicker(document.getElementById('qbStructExc'), { mode:'multi',  fetcher:fetchStructsLike, minChars:0 });

      document.getElementById('qbRun')?.addEventListener('click', runQB);
      document.getElementById('qbCSV')?.addEventListener('click', exportQB);
    }

    function getPickerValue(id) {
      const el = document.getElementById(id);
      if (!el) return null;
      return (typeof el._getValue === 'function') ? el._getValue() : (el.value ?? null);
    }


  async function runQB(){
    const themeInc   = getPickerValue('qbThemeInc') || [];
    const themeExc   = new Set(getPickerValue('qbThemeExc') || []);
    const structInc  = getPickerValue('qbStructInc') || [];
    const structExc  = new Set(getPickerValue('qbStructExc') || []);
    const role       = document.getElementById('qbRole')?.value || '*';
    const temp       = document.getElementById('qbTemp')?.value || '*';
    const mode       = document.getElementById('qbMode')?.value || '*';
    const match      = document.getElementById('qbMatch')?.value || 'ANY';
    const includeDesc= !!document.getElementById('qbIncludeDesc')?.checked;

    // === Body sans jokers
    const body = { include_desc: includeDesc };

    if (themeInc.length)        body.theme_ids    = themeInc;
    if (structInc.length === 1) body.structure_id = Number(structInc[0]);
    if (role !== '*')           body.role         = role;
    if (temp !== '*')           body.temporalite  = temp;
    if (mode !== '*')           body.mode         = mode;


    let rows = [];
    try {
      rows = await window.core.api('/api/people/search', {
        method: 'POST',
        body: JSON.stringify(body)
      });
    } catch { rows = []; }

    // filtres côté client (inchangés)
    if (structInc.length > 1) {
      const keep = new Set(structInc.map(Number));
      rows = rows.filter(r => keep.has(Number(pick(r,'idstructure','IDSTRUCTURE'))));
    }
    if (structExc.size) rows = rows.filter(r => !structExc.has(Number(pick(r,'idstructure','IDSTRUCTURE'))));
    if (themeExc.size)  rows = rows.filter(r => !themeExc.has(Number(pick(r,'idtheme','IDTHEME'))));

    if (match === 'ALL' && themeInc.length) {
      const need = new Set(themeInc.map(Number));
      const byPers = new Map();
      rows.forEach(r => {
        const pid = Number(pick(r,'idpers','IDPERS'));
        const tid = Number(pick(r,'idtheme','IDTHEME'));
        if (!byPers.has(pid)) byPers.set(pid, new Set());
        byPers.get(pid).add(tid);
      });
      const ok = new Set([...byPers.entries()]
        .filter(([_, set]) => [...need].every(t => set.has(t)))
        .map(([pid]) => pid));
      rows = rows.filter(r => ok.has(Number(pick(r,'idpers','IDPERS'))));
    }

    qbRows = rows;
    renderTable(qbRows, 'qbTable');
    document.getElementById('qbOut').style.display = '';
  }

      



    function exportQB(){
      if (!qbRows || !qbRows.length) return;
      const cols = Object.keys(qbRows[0]);
      const csv = [
        cols.join(';'),
        ...qbRows.map(r => cols.map(c => {
          const v = (r[c] ?? '');
          const s = String(v).replace(/"/g,'""');
          return `"${s}"`;
        }).join(';'))
      ].join('\n');

      const blob = new Blob([csv], {type:'text/csv;charset=utf-8;'});
      const url  = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'resultats.csv';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    }


  // ========== Init ==========
    function bootDashboardOnce() {
      if (bootDashboardOnce._did) return;
      bootDashboardOnce._did = true;
      loadKPIs().catch(()=>{});
      loadTopCharts().catch(()=>{});
      loadDistribution().catch(()=>{});
      initQueryBuilder();

    }

    // Au chargement: uniquement si déjà connecté
    document.addEventListener("DOMContentLoaded", () => {
      if (window.core?.state?.token) bootDashboardOnce();
    });

    // Après un login: booter le dashboard
    window.addEventListener('csr:auth', (e) => {
      if (e.detail?.authed) bootDashboardOnce();
    });

    document.addEventListener('click', (e) => {
      const id = e.target?.id;
      if (id === 'qbRun') { e.preventDefault(); try { runQB(); } catch(err) { console.error(err); } }
      if (id === 'qbCSV') { e.preventDefault(); try { exportQB(); } catch(err) { console.error(err); } }
    });

})();
