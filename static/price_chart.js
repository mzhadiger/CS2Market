/* price_chart.js
 * Fetches /api/price-history/<skin_id> and renders a multi-series
 * Chart.js line chart. One line per wear category. Theme-aware.
 */
async function renderPriceChart(skinId) {
  try {
    const res  = await fetch(`/api/price-history/${skinId}`);
    const rows = await res.json();

    if (!rows.length) {
      document.getElementById('price-chart-empty').style.display = 'grid';
      return;
    }

    const byWear = {};
    for (const r of rows) {
      (byWear[r.wear] = byWear[r.wear] || []).push({ x: r.date, y: r.price });
    }

    const css    = getComputedStyle(document.documentElement);
    const text3  = css.getPropertyValue('--text-3').trim() || '#7a8494';
    const border = css.getPropertyValue('--border').trim() || '#262d38';
    const bg1    = css.getPropertyValue('--bg-elev-1').trim() || '#12171f';

    const wearColors = {
      "Factory New":    "#f2a900",
      "Minimal Wear":   "#8847ff",
      "Field-Tested":   "#4b69ff",
      "Well-Worn":      "#8b949e",
      "Battle-Scarred": "#eb4b4b",
    };

    const datasets = Object.entries(byWear).map(([wear, pts]) => ({
      label: wear,
      data: pts,
      borderColor: wearColors[wear] || text3,
      backgroundColor: (wearColors[wear] || text3) + '22',
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBackgroundColor: wearColors[wear] || text3,
      pointHoverBorderColor: bg1,
      pointHoverBorderWidth: 2,
      tension: 0.35,
      fill: false,
    }));

    const ctx = document.getElementById('price-chart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800, easing: 'easeOutCubic' },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            labels: {
              color: css.getPropertyValue('--text-1').trim() || '#f0f4f8',
              usePointStyle: true,
              padding: 16,
              font: { family: 'Inter', size: 12, weight: '500' },
            },
          },
          tooltip: {
            backgroundColor: bg1,
            titleColor: css.getPropertyValue('--text-1').trim(),
            bodyColor: css.getPropertyValue('--text-2').trim(),
            borderColor: border,
            borderWidth: 1,
            padding: 12,
            boxPadding: 6,
            cornerRadius: 8,
            titleFont: { family: 'Inter', weight: '600' },
            bodyFont: { family: 'Inter' },
            callbacks: {
              label: (c) => ` ${c.dataset.label}: $${c.parsed.y.toFixed(2)}`,
            },
          },
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
            ticks: {
              color: text3,
              font: { family: 'Inter', size: 11 },
              maxRotation: 0,
            },
            grid: { color: border, drawBorder: false },
          },
          y: {
            ticks: {
              color: text3,
              font: { family: 'Inter', size: 11 },
              callback: (v) => '$' + v,
            },
            grid: { color: border, drawBorder: false },
          },
        },
      },
    });
  } catch (e) {
    console.error('Chart render failed:', e);
    document.getElementById('price-chart-empty').style.display = 'grid';
  }
}
