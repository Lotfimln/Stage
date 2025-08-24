(() => {
  const { api } = window.core;
  if (!document.getElementById('dashboard')) return;

  const charts = [];
  const addChart = (ctx, cfg) => { const c = new Chart(ctx, cfg); charts.push(c); return c; };
  const clearCharts = () => charts.splice(0).forEach(c => c.destroy());

  // util pour lire une clé peu importe la casse/le nom
  const pick = (obj, ...keys) => {
    for (const k of keys) if (obj[k] != null) return obj[k];
    return 0;
  };

  async function loadOverview() {
    // BACK: /api/stats/overview  -> { positions_total, people_total, themes_total, structures_total, non_positionnes }
    const o = await api('/api/stats/overview');

    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v ?? '—'; };
    set('kpiPositions',   pick(o, 'positions_total', 'POSITIONS_TOTAL'));
    set('kpiPeople',      pick(o, 'people_total', 'PEOPLE_TOTAL'));
    set('kpiThemes',      pick(o, 'themes_total', 'THEMES_TOTAL'));
    set('kpiStructs',     pick(o, 'structures_total', 'STRUCTURES_TOTAL'));
    set('kpiNonPos',      pick(o, 'non_positionnes', 'NON_POSITIONNES'));
  }

  async function loadCharts() {
    clearCharts();

    // BACK:
    // /api/stats/top/themes        -> [{id,label,cnt}]
    // /api/stats/top/structures    -> [{id,label,cnt}]
    // /api/stats/distribution      -> { role:[{label,cnt}], temporalite:[{label,cnt}], mode:[{label,cnt}] }
    const [themes, structs, dist] = await Promise.all([
      api('/api/stats/top/themes?limit=8'),
      api('/api/stats/top/structures?limit=8'),
      api('/api/stats/distribution'),
    ]);

    const ctxTopThemes  = document.getElementById('chTopThemes').getContext('2d');
    const ctxTopStructs = document.getElementById('chTopStructs').getContext('2d');
    const ctxRoles      = document.getElementById('chRoles').getContext('2d');
    const ctxMode       = document.getElementById('chMode').getContext('2d');

    addChart(ctxTopThemes, {
      type: 'bar',
      data: {
        labels: themes.map(x => x.label),
        datasets: [{ label: 'Thématiques', data: themes.map(x => pick(x, 'cnt', 'CNT')) }]
      },
      options: { responsive:true, maintainAspectRatio:false }
    });

    addChart(ctxTopStructs, {
      type: 'bar',
      data: {
        labels: structs.map(x => x.label),
        datasets: [{ label: 'Structures', data: structs.map(x => pick(x, 'cnt', 'CNT')) }]
      },
      options: { responsive:true, maintainAspectRatio:false }
    });

    const roles = (dist.role || dist.roles || []).map(x => pick(x, 'cnt', 'CNT'));
    addChart(ctxRoles, {
      type: 'doughnut',
      data: {
        labels: (dist.role || dist.roles || []).map(x => x.label),
        datasets: [{ data: roles }]
      },
      options: { responsive:true, maintainAspectRatio:false, cutout:'60%' }
    });

    const modes = (dist.mode || []).map(x => pick(x, 'cnt', 'CNT'));
    addChart(ctxMode, {
      type: 'doughnut',
      data: {
        labels: (dist.mode || []).map(x => x.label),
        datasets: [{ data: modes }]
      },
      options: { responsive:true, maintainAspectRatio:false, cutout:'60%' }
    });
  }

  async function init() {
    await loadOverview();
    await loadCharts();
    window.addEventListener('resize', () => charts.forEach(c => c.resize()));
  }

  document.addEventListener('DOMContentLoaded', init);
})();
