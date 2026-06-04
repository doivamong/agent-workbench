# `ui/` — the kit's presentation layer

> A first-class home for the workbench's **self-observation surface**: UI that renders
> the kit's *own* state (skills, hooks, memory, gates, telemetry), not a generic app UI.
> It lives here — not scattered in `tools/` — because UI is an integral concern of the
> codebase, not a bolt-on. The compute stays **stdlib-only**; the line is drawn below.

## What's here

| Path | What | Stack |
|------|------|-------|
| [`kit_status/`](kit_status/) | The kit-status report: `generator.py` renders `template.html` into a self-contained, offline HTML snapshot of the kit's state | **stdlib only** (`string.Template`, inline CSS/SVG, no CDN) |
| [`web/`](web/) | Opt-in web dashboard: a Flask app that visualizes the same state with interactive (vendored, offline) Chart.js — reusing `generator.gather()` as its only data source | **opt-in deps** (`flask`, `jinja2`; Chart.js vendored) |

Run it (script-style, like every other kit tool):

```sh
python ui/kit_status/generator.py --output kit-status.html --run-gates
```

It reads real data and is **honest when it can't measure**: with telemetry unwired or
its log empty, skills are shown *"chưa đo"* (not measured) — never *"dead"*; gates show
*"chưa chạy"* unless `--run-gates` runs the read-only gates or `--gates-json` supplies
results. See [`kit_status/generator.py`](kit_status/generator.py) for flags.

## The stdlib boundary

Everything under `ui/kit_status/` is **0-dependency** (stdlib Python + inline HTML/CSS/SVG).
This is the kit's identity — droppable, runs offline. The **web** dashboard
(Flask/Jinja/Chart.js) is a different stack, so it lives in its own opt-in home
([`ui/web/`](web/), not shipped by default, not a manifest root) and reuses
`generator.gather()`'s data — so the stdlib **core never grows a dependency**. The line is
drawn at `ui/web/`: the core (`tools/`, `scripts/`, `.claude/hooks/`, `ui/kit_status/`)
imports zero third-party packages; Flask/Jinja live under `ui/web/` only.

## How this relates to the rest

- **Method, not brand:** the *discipline* of building UI well — guards, caps, a11y, design
  tokens, anti-fingerprint — is documented in [`../docs/design-discipline.md`](../docs/design-discipline.md)
  and [`../docs/ui-redesign-workflow.md`](../docs/ui-redesign-workflow.md). Those ship; a brand
  does not.
- **Adopter brand:** the reserved `_your-ui-guide_` slot in
  [`../.claude/skills/skill-registry.md`](../.claude/skills/skill-registry.md) is where an
  adopter fills in *their* palette/tokens/macros. That is the adopter's product UI — distinct
  from this `ui/`, which is the kit looking at itself.

## What this does NOT do

- It is **not** installed by default. `ui/` is opt-in: `install.py`'s `COPY_MAP` does not
  copy it, so adopting the kit does not force the report on you (it is, however, a manifest
  root, so the kit tracks its own `ui/` for drift).
- It is **not** a live dashboard — the report is a point-in-time snapshot; re-run to refresh.
- It does **not** run the heavy gates (pytest) for you; `--run-gates` runs only the fast
  read-only ones.
