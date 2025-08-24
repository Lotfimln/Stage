(() => {
  const { api } = window.core;
  if (!document.getElementById('chTopThemes')) return;

  const charts = [];
  const addChart = (ctx, cfg) => { const c = new Chart(ctx, cfg); charts.push(c); return c; };
  const clearCharts = () => charts.splice(0).forEach(c => c.destroy());

  async function loadOverview() {
    const o = await api('/api/stats/overview');
    const set = (id,v) => { const el = document.getElementById(id); if (el) el.textContent = v ?? '—'; };

    set('kpiPeoplePos', o.people_pos);
    set('kpiPeopleNonPos', o.people_non_pos);
    set('kpiThemesActifs', o.themes_actifs);
    set('kpiStructsActives', o.structures_actives);
    set('kpiAvgThemesPerPerson', o.avg_themes_per_person);
  }

  async function loadCharts() {
    clearCharts();
    const [themes, structs, dist] = await Promise.all([
      api('/api/stats/top/themes?limit=8'),
      api('/api/stats/top/structures?limit=8'),
      api('/api/stats/distribution'),
    ]);

    // Top thématiques
    addChart(document.getElementById('chTopThemes'), {
      type: 'bar',
      data: {
        labels: themes.map(x => x.label),
        datasets: [{ label: 'Personnes', data: themes.map(x => x.cnt) }]
      },
      options: { responsive:true, maintainAspectRatio:false }
    });

    // Top structures
    addChart(document.getElementById('chTopStructs'), {
      type: 'bar',
      data: {
        labels: structs.map(x => x.label),
        datasets: [{ label: 'Personnes', data: structs.map(x => x.cnt) }]
      },
      options: { responsive:true, maintainAspectRatio:false }
    });

    // Rôles (Présent)
    addChart(document.getElementById('chRoles'), {
      type: 'doughnut',
      data: {
        labels: dist.role.map(x => x.label),
        datasets: [{ data: dist.role.map(x => x.cnt) }]
      },
      options: { responsive:true, maintainAspectRatio:false, cutout:'60%' }
    });

    // Temporalité
    addChart(document.getElementById('chTempo'), {
      type: 'doughnut',
      data: {
        labels: dist.temporalite.map(x => x.label),
        datasets: [{ data: dist.temporalite.map(x => x.cnt) }]
      },
      options: { responsive:true, maintainAspectRatio:false, cutout:'60%' }
    });

    // Mode
    addChart(document.getElementById('chMode'), {
      type: 'doughnut',
      data: {
        labels: dist.mode.map(x => x.label),
        datasets: [{ data: dist.mode.map(x => x.cnt) }]
      },
      options: { responsive:true, maintainAspectRatio:false, cutout:'60%' }
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await loadOverview();
    await loadCharts();
  });
})();
