# Distilling an ops-script layer into the kit — survey & verdict

> A worked example of the kit's *honest distillation* discipline: how we decided what (if
> anything) to lift from a large private operational-script layer, and why the honest answer was
> "almost nothing new — the lessons were already here." The full, source-referencing analysis is
> kept private (it names internal identifiers); this is the sanitized, generic record.

## The question

A private codebase had a big **operational layer** — dozens of Python ops scripts plus a folder of
Windows `.bat`/`.ps1` launchers (benchmarks, scheduled-job runners, a DR drill, backup/restore,
server launchers, deploy/release gates, schema migrations). Earlier distillation waves had only
surveyed the *agent* layer (hooks, tools, skills, docs, memory). **Was there anything generic and
reusable in the ops layer worth distilling into this kit?**

## The approach

A fan-out survey (one reader per script bucket) classified every candidate, then an **adversarial
verify pass** checked each against the kit as it already exists — *is this already covered? does the
generic core separate cleanly from the domain? is it safe to share?* Two guards were set up front to
avoid a known failure mode (a survey that uniformly rejects under an anti-bloat framing): weigh
**reusability first**, and separate the **generic core** from the **domain coupling** for every
candidate.

## The verdict

**33 candidate patterns → almost nothing new to ship:**

| Verdict | Count | Meaning |
|---|---|---|
| `ALREADY-COVERED` | 18 | The lesson/methodology is already distilled here (a memory fact, a doc, or a tool) |
| `LOW-VALUE` | 10 | Separable but a ~20-line stdlib idiom / low fire-rate → shipping it is bloat |
| `DOMAIN-LOCKED` | 2 | The generic core does not separate cleanly from domain logic |
| `DO_NOT_SHARE` | 2 | The file carries internal task names / paths / orchestration |
| **`SHIP-CANDIDATE`** | **1** | atomic config write (`tempfile` + `os.replace`) — a borderline doc-section, not a tool |

**One-line conclusion:** the operational layer was *already* distilled — not by porting scripts, but
because its durable lessons had been captured earlier as memory facts and patterns. Examples the
verify pass cited as already-present: measure-cold-not-warm benchmarking, the headless-stdout guard,
WAL-safe read-only SQLite, kill-by-port restart hygiene, the optimization-loop methodology. The only
genuinely-absent generic was the write-side of config safety (atomic replace), and even that the
verifier flagged as having *no consumer on this kit's own surface* — a dev-tool kit, not a
long-lived service mutating config under crash pressure.

## What we built instead (the owner-facing outcome)

The survey answered "what's generic for *peers*". Separately, the owner wanted **operational tooling
for working on this repo itself**, modelled on that private ops layer. That became the
[`ops/`](../ops/) toolkit (now on `main`), built first-principles as clean stdlib kit tools:

| Operational need (generic) | → kit tool |
|---|---|
| Restart the local dashboard server (kill port → relaunch → healthcheck) | `ops/dashboard_ctl.py` + `ops/win/restart_all.bat` |
| Package a verifiable release of the installable kit | `ops/release_pack.py` |
| Snapshot / restore the working tree as a dev safety net | `ops/tree_snapshot.py` |

## The takeaway (methodology)

- A green automated leak/scan is **not** proof a body of text is shareable: the full survey passed
  the leak scanner yet still named internal identifiers a manual grep caught. Grep the source's own
  namespace yourself before publishing ported/derived analysis.
- "Survey the ops layer" felt like new ground, but most of its value had already been captured as
  *lessons*, not code — which is the point of a memory discipline: you distil the lesson once and
  stop re-porting the script that taught it.
