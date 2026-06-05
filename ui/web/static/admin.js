/* ui/web/static/admin.js — minimal, OFFLINE helper for the /admin surface.
 *
 * One job: after a Restart action, the dashboard process this page is served by drops and a
 * fresh one comes up on the same port. When the restart result lands (carrying data-restart),
 * poll GET /health and reload the page once it answers healthy again. No external fetch, no
 * dependency — htmx (vendored) does the POSTs; this only handles the reconnect.
 *
 * Confirm dialogs for destructive actions are handled declaratively by htmx's hx-confirm in
 * the templates (no custom dialog code here).
 */
(function () {
  "use strict";

  function reloadWhenHealthy(attemptsLeft) {
    if (attemptsLeft <= 0) {
      return; // give up quietly; the user can refresh manually
    }
    fetch("/health", { cache: "no-store" })
      .then(function (resp) {
        if (resp.ok) {
          window.location.reload();
        } else {
          window.setTimeout(function () { reloadWhenHealthy(attemptsLeft - 1); }, 700);
        }
      })
      .catch(function () {
        // The old process is still going down (connection refused) — keep waiting.
        window.setTimeout(function () { reloadWhenHealthy(attemptsLeft - 1); }, 700);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.body.addEventListener("htmx:afterSwap", function () {
      if (document.querySelector("[data-restart='1']")) {
        // Wait briefly for the detached restarter to take the old process down, then poll.
        window.setTimeout(function () { reloadWhenHealthy(40); }, 1200);
      }
    });
  });
})();
