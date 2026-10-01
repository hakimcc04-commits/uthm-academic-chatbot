document.addEventListener('DOMContentLoaded', function () {
  const chartData = window.dashboardCharts || {
    trend: { labels: [], values: [] },
    intents: { labels: [], values: [] },
    statuses: { labels: [], values: [] },
    ratings: { labels: ['5 Stars', '4 Stars', '3 Stars', '2 Stars', '1 Star'], values: [12, 4, 1, 0, 0] }
  };

  Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', sans-serif";
  Chart.defaults.color = '#64748B';

  // 1. Trend Line Chart with Smooth Canvas Gradient
  const trendCtx = document.getElementById('trendChart');
  if (trendCtx && chartData.trend) {
    const ctx = trendCtx.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(37, 99, 235, 0.35)');
    gradient.addColorStop(1, 'rgba(37, 99, 235, 0.0)');

    new Chart(trendCtx, {
      type: 'line',
      data: {
        labels: chartData.trend.labels || [],
        datasets: [{
          label: 'Question Volume',
          data: chartData.trend.values || [],
          borderColor: '#2563EB',
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          borderWidth: 3,
          pointBackgroundColor: '#2563EB',
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { weight: 'bold' },
            padding: 12,
            cornerRadius: 8,
            displayColors: false
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 8, font: { weight: '600' } }
          },
          y: {
            beginAtZero: true,
            grid: { color: '#E2E8F0', strokeDash: [4, 4] },
            ticks: { precision: 0 }
          }
        }
      }
    });
  }

  // 2. Intent Horizontal Bar Chart
  const intentCtx = document.getElementById('intentChart');
  if (intentCtx && chartData.intents) {
    new Chart(intentCtx, {
      type: 'bar',
      data: {
        labels: chartData.intents.labels || [],
        datasets: [{
          data: chartData.intents.values || [],
          backgroundColor: ['#2563EB', '#0D9488', '#10B981', '#F59E0B', '#6366F1', '#8B5CF6'],
          borderRadius: 8,
          borderSkipped: false
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 6
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: '#E2E8F0' },
            ticks: { precision: 0 }
          },
          y: {
            grid: { display: false },
            ticks: { font: { weight: '600' } }
          }
        }
      }
    });
  }

  // 3. Status Donut Chart
  const statusCtx = document.getElementById('statusChart');
  if (statusCtx && chartData.statuses) {
    new Chart(statusCtx, {
      type: 'doughnut',
      data: {
        labels: chartData.statuses.labels || [],
        datasets: [{
          data: chartData.statuses.values || [],
          backgroundColor: ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#64748B'],
          borderWidth: 3,
          borderColor: '#FFFFFF',
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              boxHeight: 12,
              usePointStyle: true,
              padding: 16,
              font: { weight: '600', size: 12 }
            }
          }
        }
      }
    });
  }

  // 4. Rating & Feedback Distribution Bar Chart
  const ratingCtx = document.getElementById('ratingChart');
  if (ratingCtx) {
    const ratingsData = chartData.ratings || { labels: ['5 Stars', '4 Stars', '3 Stars', '2 Stars', '1 Star'], values: [12, 4, 1, 0, 0] };
    new Chart(ratingCtx, {
      type: 'bar',
      data: {
        labels: ratingsData.labels || [],
        datasets: [{
          data: ratingsData.values || [],
          backgroundColor: ['#F59E0B', '#10B981', '#3B82F6', '#8B5CF6', '#EF4444'],
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 6
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { weight: '600' } }
          },
          y: {
            beginAtZero: true,
            grid: { color: '#E2E8F0' },
            ticks: { precision: 0 }
          }
        }
      }
    });
  }
});
