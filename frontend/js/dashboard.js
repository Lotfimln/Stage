(() => {
  const { api } = window.core;

  // Chart.js: thème sombre + options communes
  Chart.defaults.color = '#e5e7eb';
  Chart.defaults.borderColor = getComputedStyle(document.documentElement)
                               .getPropertyValue('--grid-color') || 'rgba(255,255,255,.08)';
  const axle = { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(255,255,255,.08)' } };

  const charts = [];
  const addChart = (ctx, cfg) => { const c = new Chart(ctx, cfg); charts.push(c); return c; };
  const clearCharts = () => charts.splice(0).forEach(c => c.destroy());
  const nf = (n) => (n ?? 0).toLocaleString('fr-FR');

  async function loadKPIs() {
    const o = await api('/api/stats/overview');
    // o.keys -> positions_total, people_present, people_nonpos_present, themes_active_present,
    //           structures_active_present, avg_themes_per_person
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set('kpiPersPresent', nf(o.people_present));
    set('kpiNonPos', nf(o.people_nonpos_present));
    set('kpiThemes', nf(o.themes_active_present));
    set('kpiStructs', nf(o.structures_active_present));
    set('kpiAvg', (o.avg_themes_per_person ?? 0).toLocaleString('fr-FR', { maximumFractionDigits: 2 }));
  }

  async function loadCharts() {
    clearCharts();

    const [themes, structs, dist] = await Promise.all([
      api('/api/stats/top/themes?limit=8'),
      api('/api/stats/top/structures?limit=8'),
      api('/api/stats/distribution')
    ]);

    const barOpts = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ...axle, ticks: { ...axle.ticks, maxRotation: 35, minRotation: 30 } },
        y: { ...axle, beginAtZero: true }
      },
      plugins: {
        tooltip: { callbacks: { label: (c) => `${c.parsed.y.toLocaleString('fr-FR')} personnes` } },
        legend: { display: false }
      },
      datasets: { bar: { maxBarThickness: 36, categoryPercentage: .8, barPercentage: .9 } }
    };

    addChart(document.getElementById('chTopThemes').getContext('2d'), {
      type: 'bar',
      data: {
        labels: themes.map(x => x.label),
        datasets: [{ label: 'Personnes', data: themes.map(x => x.cnt) }]
      },
      options: barOpts
    });

    addChart(document.getElementById('chTopStructs').getContext('2d'), {
      type: 'bar',
      data: {
        labels: structs.map(x => x.label),
        datasets: [{ label: 'Personnes', data: structs.map(x => x.cnt) }]
      },
      options: barOpts
    });

    const doughnutOpts = {
      responsive: true, maintainAspectRatio: false, cutout: '60%',
      plugins: { legend: { position: 'top' } }
    };

    addChart(document.getElementById('chRoles').getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: dist.role.map(x => x.label),
        datasets: [{ data: dist.role.map(x => x.cnt) }]
      }, options: doughnutOpts
    });

    addChart(document.getElementById('chTempo').getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: dist.temporalite.map(x => x.label),
        datasets: [{ data: dist.temporalite.map(x => x.cnt) }]
      }, options: doughnutOpts
    });

    addChart(document.getElementById('chMode').getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: dist.mode.map(x => x.label),
        datasets: [{ data: dist.mode.map(x => x.cnt) }]
      }, options: doughnutOpts
    });
  }

  async function init() {
    await loadKPIs();
    await loadCharts();
  }
  document.addEventListener('DOMContentLoaded', init);
})();
