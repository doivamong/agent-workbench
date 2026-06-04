/* dashboard.js — initialise the two vendored-Chart.js charts from server data.
 *
 * Data arrives embedded in <script id="chart-data" type="application/json">, NOT fetched,
 * so the page stays fully offline. Honesty: the timeseries chart is only drawn when the
 * server says telemetry was MEASURED; otherwise the markup shows an empty state and there
 * is no canvas to draw into (no pretty zero). The tier doughnut is a static property of
 * the skill set, so it is always honest to show.
 */
(function () {
  "use strict";

  var el = document.getElementById("chart-data");
  if (!el || typeof Chart === "undefined") return;

  var data;
  try {
    data = JSON.parse(el.textContent);
  } catch (e) {
    return; // malformed payload: leave the server-rendered fallbacks in place
  }

  // Respect the user's motion preference — disable chart entry animation when reduced.
  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var COL = {
    accent: "#CC2929",
    text: "#C8C8C8",
    dim: "#9CA0A8",
    grid: "rgba(255,255,255,0.06)",
    surface: "#15161A",
  };

  Chart.defaults.font.family =
    '"Segoe UI", system-ui, -apple-system, "Be Vietnam Pro", "Inter", sans-serif';
  Chart.defaults.color = COL.dim;

  // --- timeseries (skill activations per day) — only when measured -------- //
  var tsCanvas = document.getElementById("chart-timeseries");
  if (tsCanvas && data.measured && data.timeseries) {
    new Chart(tsCanvas.getContext("2d"), {
      type: "line",
      data: {
        labels: data.timeseries.labels,
        datasets: [{
          label: "Lần kích hoạt/ngày",
          data: data.timeseries.values,
          borderColor: COL.accent,
          backgroundColor: "rgba(204,41,41,0.12)",
          fill: true,
          tension: 0.3,
          pointBackgroundColor: COL.accent,
          pointRadius: 3,
          pointHoverRadius: 5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reduceMotion ? false : { duration: 400 },
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: COL.grid }, ticks: { color: COL.dim } },
          y: {
            beginAtZero: true,
            grid: { color: COL.grid },
            ticks: { color: COL.dim, precision: 0 },
          },
        },
      },
    });
  }

  // --- tier distribution (always honest — static property of the skills) -- //
  var tierCanvas = document.getElementById("chart-tiers");
  if (tierCanvas && data.tiers && data.tiers.values.length) {
    new Chart(tierCanvas.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: data.tiers.labels,
        datasets: [{
          data: data.tiers.values,
          backgroundColor: data.tiers.colors,
          borderColor: COL.surface,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        animation: reduceMotion ? false : { duration: 400 },
        plugins: {
          legend: { position: "right", labels: { color: COL.text, boxWidth: 12, padding: 12 } },
        },
      },
    });
  }
})();
