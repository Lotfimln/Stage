(() => {
  const { api } = window.core;

  const bindDashboard = () => {
    const btn   = document.getElementById('openDashboard');
    const panel = document.getElementById('dashboard');
    if (!btn || !panel) return;

    let charts = {};
    let loadedOnce = false;

    async function ensureMarkup() {
      if (panel.childElementCount) return;
      try {
        const res = await fetch('dashboard.html', { cache: 'no-store' });
        if (res.ok) panel.innerHTML = await res.text();
      } catch {}
    }

    btn.onclick = async () => {
      const show = panel.style.display === 'none' || panel.style.display === '';
      if (show) {
        await ensureMarkup();
        panel.style.display = '';
        if (!loadedOnce) {
          loadedOnce = true;
          await loadDashboard();
        }
      } else {
        panel.style.display = 'none';
      }
    };

    async function loadDashboard(){
    try {
      // KPIs
      const o = await api('/api/stats/overview');
      setKPI('kpi-positions', o.positions_total ?? o.POSITIONS_TOTAL ?? '–');
      setKPI('kpi-people',    o.people_total    ?? o.PEOPLE_TOTAL    ?? '–');
      setKPI('kpi-themes',    o.themes_total    ?? o.THEMES_TOTAL    ?? '–');
      setKPI('kpi-structures',o.structures_total?? o.STRUCTURES_TOTAL?? '–');
      setKPI('kpi-nonpos',    o.non_positionnes ?? o.NON_POSITIONNES ?? '–');

      // Top
      const [topThemes, topStructs] = await Promise.all([
        api('/api/stats/top/themes?limit=8'),
        api('/api/stats/top/structures?limit=8')
      ]);

      // Distributions
      const dist = await api('/api/stats/distribution');

      drawBar('chTopThemes',   'Top thématiques', pairs(topThemes));
      drawBar('chTopStructs',  'Top structures',  pairs(topStructs));
      drawPie('chRole',        'Rôles',           pairs(dist.role || []));
      drawPie('chTemp',        'Temporalité',     pairs(dist.temporalite || []));
      drawPie('chMode',        'Mode',            pairs(dist.mode || []));

    } catch(e){
      console.error(e);
      if (window.setStatus) setStatus('❌ Dashboard: ' + (e?.message || e), 'err');
    }
  }

  function setKPI(id, v){ const el = document.getElementById(id); if (el) el.textContent = v; }
  function pairs(rows){
    const L=[], D=[];
    (rows||[]).forEach(r=>{
      const lab = r.label ?? r.LABEL ?? r.theme ?? r.THEME ?? r.id ?? r.ID ?? '';
      const cnt = Number(r.cnt ?? r.CNT ?? 0);
      L.push(String(lab)); D.push(cnt);
    });
    return { labels:L, data:D };
  }

  function ctx(id){ const el = document.getElementById(id); return el ? el.getContext('2d') : null; }
  function destroy(id){ if (charts[id]) { charts[id].destroy(); charts[id] = null; } }

  function drawBar(id, title, serie){
    const c = ctx(id); if (!c || typeof Chart==='undefined') return;
    destroy(id);
    charts[id] = new Chart(c, {
      type: 'bar',
      data: { labels: serie.labels, datasets: [{ label:title, data: serie.data }] },
      options: {
        responsive:true,
        plugins:{ legend:{ display:false }, title:{ display:true, text:title } },
        scales:{ x:{ ticks:{ autoSkip:false, maxRotation:40, minRotation:0 } } }
      }
    });
  }

  function drawPie(id, title, serie){
    const c = ctx(id); if (!c || typeof Chart==='undefined') return;
    destroy(id);
    charts[id] = new Chart(c, {
      type: 'doughnut',
      data: { labels: serie.labels, datasets:[{ data: serie.data }] },
      options: { responsive:true, plugins:{ title:{ display:true, text:title } } }
    });
  }
}


  window.bindDashboard = bindDashboard;
})();
