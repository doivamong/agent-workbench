---
name: optin-dep-tests-skipif-not-importorskip
description: "Opt-in-dependency tests gated by a collected-test count must use skipif (stays collected), not importorskip (drops the module), or the advertised count drifts dev-vs-CI."
metadata: 
  type: feedback
---

When a test module depends on an **opt-in** dependency NOT installed in CI (e.g. a web layer's
Flask), how you skip it interacts with any gate that counts tests via `pytest --co` (collected tests).

- `pytest.importorskip("flask")` at module top → the whole module is **dropped from collection** when
  the dep is absent. The dev machine (dep present) collects N; CI (dep absent) collects 0 → a
  count-based gate advertises N more than CI sees → the count check FAILS in CI while passing locally.
  (Verified empirically: `--co` lists skipif items, drops importorskip ones.)
- Fix: import the dep **guardedly** so the module always imports cleanly, then
  `pytestmark = pytest.mark.skipif(not _HAS_DEP, ...)`. skipif items **stay collected** (count stable
  everywhere) but are skipped at run time, so the core suite still passes with zero third-party deps.
  Defer any `import app`-style line that needs the dep into the guarded block (else collection ERRORS
  without the dep).
- Companion fix: omit the opt-in code from coverage config (`source = .`) — CI never installs the dep,
  so counting it would gate coverage on code CI deliberately never runs.

**Why:** local "green" ≠ CI green when the env differs; a count gate makes the env difference fail
loud ([[verify-load-bearing-before-asserting]]).
**How to apply:** for any opt-in-dep test, ask "does a count/coverage gate see this file in an env
without the dep?" Use skipif + guarded import + coverage-omit.
