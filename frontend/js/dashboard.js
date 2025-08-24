(() => {
  const { api } = window.core || {};

  // Ne s'exécute que sur dashboard.html
  if (!document.getElementById('dashboard-page')) return;

  const charts = [];
  const addChart = (id, cfg) => {
    const ctx = document.getElementById(id).getContext('2d');
    const c = new Chart(ctx, cfg);
    charts.push(c);
    return c;
  };
  const clearCharts = () => charts.splice(0).forEach(c => c.destroy());
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = (v ?? '—').toString(); };

  async function loadOverview() {
    const o = await api('/api/stats/overview'); // {positions_total, people_total, themes_total, structures_total, non_positionnes}
    set('kpiPositions',  o.positions_total);
    set('kpiPeople',     o.people_total);
    set('kpiThemes',     o.themes_total);
    set('kpiStructs',    o.structures_total);
    set('kpiNonPos',     o.non_positionnes);
  }

  const num = x => x?.cnt ?? x?.CNT ?? x?.count ?? 0;

  async function loadCharts() {
    clearCharts();

    const [themes, structs, dist] = await Promise.all([
      api('/api/stats/top/themes?limit=8'),
      api('/api/stats/top/structures?limit=8'),
      api('/api/stats/distribution'),
    ]);

    addChart('chTopThemes', {
      type: 'bar',
      data: {
        labels: themes.map(x => x.label),
        datasets: [{ label: 'Thèmes', data: themes.map(num) }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });

    addChart('chTopStructs', {
      type: 'bar',
      data: {
        labels: structs.map(x => x.label),
        datasets: [{ label: 'Structures', data: structs.map(num) }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });

    addChart('chRoles', {
      type: 'doughnut',
      data: { labels: dist.role.map(x => x.label), datasets: [{ data: dist.role.map(num) }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '60%' }
    });

    addChart('chTemps', {
      type: 'doughnut',
      data: { labels: dist.temporalite.map(x => x.label), datasets: [{ data: dist.temporalite.map(num) }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '60%' }
    });

    addChart('chMode', {
      type: 'doughnut',
      data: { labels: dist.mode.map(x => x.label), datasets: [{ data: dist.mode.map(num) }] },
      options: { responsive: true, maintainAspectRatio: false, cutout: '60%' }
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await loadOverview();
    await loadCharts();
  });
})();
