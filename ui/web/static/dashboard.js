/* dashboard.js — initialise the two vendored-Chart.js charts from server data.
 *
 * Data arrives embedded in <script id="chart-data" type="application/json">, NOT fetched,
 * so the page stays fully offline. Honesty: the timeseries chart is only drawn when the
 * server says telemetry was MEASURED; otherwise the markup shows an empty state and there
 * is no canvas to draw into (no pretty zero). The tier doughnut is a static property of
 * the skill set, so it is always honest to show.
 *
 * HTMX: when the day selector / refresh swaps #dyn, the <canvas> elements and #chart-data
 * are replaced. We re-run initCharts() on `htmx:afterSwap` for that region, destroying any
 * prior Chart instance on each canvas first so we never leak or double-bind.
 */
(function () {
  "use strict";

  var COL = {
    accent: "#CC2929",
    text: "#C8C8C8",
    dim: "#9CA0A8",
    grid: "rgba(255,255,255,0.06)",
    surface: "#15161A",
  };

  function reduceMotion() {
    return window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function destroyOn(canvas) {
    // Chart.js 4: Chart.getChart returns the instance bound to a canvas, if any.
    if (canvas && typeof Chart !== "undefined" && Chart.getChart) {
      var prev = Chart.getChart(canvas);
      if (prev) prev.destroy();
    }
  }

  function initCharts() {
    var el = document.getElementById("chart-data");
    if (!el || typeof Chart === "undefined") return;

    var data;
    try {
      data = JSON.parse(el.textContent);
    } catch (e) {
      return; // malformed payload: leave the server-rendered fallbacks in place
    }

    Chart.defaults.font.family =
      '"Segoe UI", system-ui, -apple-system, "Be Vietnam Pro", "Inter", sans-serif';
    Chart.defaults.color = COL.dim;
    var anim = reduceMotion() ? false : { duration: 400 };

    // --- timeseries (skill activations per day) — only when measured -------- //
    var tsCanvas = document.getElementById("chart-timeseries");
    if (tsCanvas && data.measured && data.timeseries) {
      destroyOn(tsCanvas);
      new Chart(tsCanvas.getContext("2d"), {
        type: "line",
        data: {
          labels: data.timeseries.labels,
          datasets: [{
            label: "Lượt gọi tên/ngày",
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
          animation: anim,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: COL.grid }, ticks: { color: COL.dim } },
            y: { beginAtZero: true, grid: { color: COL.grid }, ticks: { color: COL.dim, precision: 0 } },
          },
        },
      });
    }

    // --- tier distribution (always honest — static property of the skills) -- //
    var tierCanvas = document.getElementById("chart-tiers");
    if (tierCanvas && data.tiers && data.tiers.values.length) {
      destroyOn(tierCanvas);
      // On a narrow viewport a right-side legend would crush the doughnut to a
      // sliver; the .chips list under the canvas already labels every tier, so we
      // drop the in-chart legend there and keep it only where there's room.
      var narrow = window.matchMedia &&
        window.matchMedia("(max-width: 600px)").matches;
      var tierLegend = narrow
        ? { display: false }
        : { position: "right", labels: { color: COL.text, boxWidth: 12, padding: 12 } };
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
          animation: anim,
          plugins: { legend: tierLegend },
        },
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCharts);
  } else {
    initCharts();
  }

  // Re-init only when the chart-bearing region (#dyn) was swapped — a tier-filter swap of
  // #skills-region doesn't touch the charts, so we skip it to avoid needless redraws.
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.target && evt.target.id === "dyn") initCharts();
  });
})();
