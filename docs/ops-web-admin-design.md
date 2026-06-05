# Opt-in `/admin` web layer — design & decisions

> The design of record for the ops toolkit's optional web admin surface (Phase 2), distilled from
> the research + stress-test that preceded it. The engine it drives — `ops/dashboard_ctl.py`,
> `ops/release_pack.py`, `ops/tree_snapshot.py` — ships separately and is stdlib-only; this layer is
> the **opt-in** Flask veneer on top, so one implementation backs both the terminal and the buttons.

## What it is

An opt-in `/admin` surface added to the `ui/web` dashboard (flag `--admin`, default **OFF**) with
full action buttons — restart, snapshot, pack, verify, and a **guarded tree-restore** — that call
the ops engine. The read-only dashboard at `/` keeps its promise; `/admin` is a separate surface.

## The five binding decisions (with rationale)

- **D1 — opt-in `--admin`, default OFF.** The default dashboard keeps its read-only/no-mutation
  promise; admin routes are not even registered without the flag. Rejected: always-on admin
  (permanent attack surface).
- **D2 — tree-restore is a real web button, not "copy the CLI command".** Don't offload manual CLI
  work onto users; the *most dangerous* op benefits *most* from a guided UI (diff preview +
  auto-backup + explicit confirm), which is safer for a non-expert than a raw CLI `--yes`.
- **D3 — the guards below are mandatory, not optional.** The design stress-test returned **CAUTION,
  not GO** — it is GO *only with* these guards; without the selection-allowlist + no-shell + CSRF it
  is a STOP-level injection/CSRF hole.
- **D4 — engine reuse; destructive ops run via subprocess.** Calling `python ops/<tool>.py ...`
  isolates destructive logic from the Flask process, reuses exact CLI dry-run/confirm semantics, and
  is kill-able. Read-only status may import the API directly.
- **D5 — `/admin` is a separate Flask blueprint; `/` stays read-only.** Identity separation.

## The nine mandatory guards

1. **Opt-in:** blueprint registered only under `--admin`; otherwise `/admin*` is 404.
2. **CSRF:** per-process `secrets.token_urlsafe` token; mutating routes are POST-only; check with
   `hmac.compare_digest` **before any side effect**; GETs never mutate.
3. **Host/Origin allowlist:** reject any request whose `Host` isn't `127.0.0.1:<port>` /
   `localhost:<port>` (store the bound port in `app.config` so the check knows it); reject cross `Origin` on POST.
4. **Bind + mode:** enforce `127.0.0.1`; refuse `--host 0.0.0.0` and `--debug` together with `--admin`.
5. **Selection allowlist + no shell:** the snapshot/release a destructive action targets is chosen by
   **id from a server-enumerated list**, never a client path; subprocess uses arg lists, never `shell=True`.
6. **Guarded restore:** dry-run preview → render create/modify counts + a `plan_hash` → the apply POST
   must carry that hash → `apply_restore` re-validates (TOCTOU, aborts `aborted-stale` on drift) →
   auto-backup first → refuse if the tree is dirty unless an explicit `allow_dirty` field is set.
7. **Self-restart:** spawn a **detached** restart; return "restarting…"; the page polls `/health`;
   handle restart-failure (timeout, don't spin).
8. **Audit log:** append every admin action to `.ops/ops.log` (timestamp · action · result).
9. **Error surfacing:** show subprocess exit code + stderr tail in the UI; never swallow.

## Acceptance — the four Critical guards (must have tests)

| # | Scenario | Expected |
|---|---|---|
| 1 | A destructive action targets a name containing `../` or `;`/`\|` | Rejected — only server-enumerated ids accepted; arg list, never `shell=True` |
| 2 | A mutating POST with a missing/invalid CSRF token, or an action via GET | 403 / no-op — token checked before any side effect |
| 3 | A `Host` header that isn't `127.0.0.1:<port>` / `localhost:<port>` | Rejected (defeats DNS-rebind) |
| 4 | The tree/zip changes between the restore dry-run and the confirm | Apply aborts `aborted-stale` (TOCTOU) |

## The honest limit (load-bearing — document in code + `ui/web/README.md` + the admin page)

Admin mode **trusts every local process/user that can reach `127.0.0.1:<port>`** — anything that can
load the page can read the CSRF token. The token defeats *cross-origin browser* CSRF, **not a local
attacker**. So: opt-in, default-off, and **do not run `--admin` on a shared/multi-user machine.**
This is an inherent limit of a no-auth localhost server, not a bug.

## Build notes / traps

- CI Linux is the real cross-platform gate; a local Windows pass proves nothing about a
  process/subprocess test (zombie-reap precedent in `ops/dashboard_ctl._reap`).
- New Flask tests use a guarded import + `skipif`, **never `importorskip`** (keeps the `pytest --co`
  count stable dev-vs-CI so the README-metrics gate doesn't drift).
- After adding tests/a demo, run `python tools/readme_metrics.py --write` then `--check`.
- Match the `ui/web` UI bar (Vietnamese text, shared design tokens, reduced-motion, AA-contrast, ≥44px).
