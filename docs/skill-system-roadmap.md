# Skill System Roadmap — proposed expansion

> **Status: PROPOSAL, not shipped.** Everything below is a plan produced by a multi-expert
> review, not a description of what currently ships. The repo ships **5 example skills today**;
> this document argues for growing to **13 live skills + supporting docs/hooks**, in waves, and
> records *why* each item earns (or fails to earn) a place. Per
> [`PHILOSOPHY.md`](../PHILOSOPHY.md), the standard is **"best-fit, honest about limits, not
> gospel"** — challenge any verdict here.

## Why this exists

The reusable kit ships a deliberately minimal skill set (3 workflow + 2 guard exemplars) whose
README intent is "copy their *shape*, not their content." It was distilled from a larger private
production codebase whose skill library is much richer. The question this roadmap answers:

> *Which proven capabilities from that private library are generic enough to distill into the
> kit — and how do we add them without betraying the anti-bloat tenet ("don't add features to
> look bigger… but do grow by genuine need")?*

The anti-bloat constraint is treated as a **hard gate**: a capability ships only if it closes a
real recurring stumble, is fully domain-free, and is the *correct mechanism* (a skill, not a
hook/tool/doc wearing a skill's clothes).

## How this was decided

A council of five independent reviewers (skill-system architect, distillation/DX strategist,
anti-bloat steward, safety/guard engineer, maintainability economist) each analyzed the kit and
the private library against the philosophy, then debated. **Every candidate skill was read in
full** before a verdict — an earlier pass that judged from one-line descriptions produced two
wrong rejects and undercounted genuine candidates roughly threefold. The lesson is baked into
the rubric below: *read the body, cite the evidence, separate generic core from domain coupling.*

## The three-layer model of "comprehensive"

"Comprehensive" is split so breadth doesn't become bloat:

1. **System layer** — make the skill *system* self-enforcing (routing, lint-gating, lifecycle,
   a context-budget cap). Highest consensus; *reduces* long-term cost.
2. **Map layer** — capture the full capability taxonomy as **docs** (`SKILL_CATALOG.md` +
   blueprints). Near-zero context cost; this is where most breadth lives.
3. **Exemplar layer** — ship a *few* new runnable skills, one per tier-shape, gated tightly.

## Decision table

Verdicts: **SHIP** (new live example skill) · **HARVEST** (port a nugget into an existing skill/doc,
don't ship whole) · **RECLASSIFY** (belongs in a hook/tool, not a skill) · **BLUEPRINT** (ship as a
doc) · **REJECT** (domain-locked, redundant, or no original method).

### A. SHIP — 8 new live example skills

| Proposed skill | Tier | Generic core | Mandatory "does NOT do" caveat |
|---|---|---|---|
| `example-cook` | workflow (advanced) | Graduated oversight modes (interactive/fast/auto) + a workflow that *orchestrates* guard skills + multi-perspective planning (3 parallel planner sub-agents, then merge convergent/divergent/unique) | Does not enforce anything; it is a bypassable exemplar, not a gate |
| `example-external-ref` | workflow | Responsible external-code reuse: a 2-axis license decision matrix (port-code vs salvage-concept), the idea/expression boundary, an injection guard for fetched content, and supply-chain red-flag signals | A license-classification seatbelt, **not legal advice**; avoiding copyright ≠ avoiding patents |
| `example-premortem` | feature/analysis | Multi-persona pre-mortem (independent analysis → debate → GO/CAUTION/STOP) **plus** a 12-dimension edge-case checklist (as a `references/` file) | Reasons about a *proposal* from descriptions; does not validate code; verdicts are opinion, not proof |
| `example-tdd` | workflow | Red-green-refactor as **vertical slices** (one failing test → minimal impl → repeat), with the silent-skip trap (a mis-named test file collects 0 tests yet exits green) | Passing tests prove only what they assert; adapted from upstream MIT work |
| `example-optimize` | feature | Measure → top-3 bottlenecks → fix → verify, with a **mandatory before/after table** and a banned-behaviors list (no fix without a baseline) | Ships no profiler engine; thresholds are heuristics to calibrate per app |
| `example-output-guard` | guard | Semantic-completeness discipline for long generation: no truncation, placeholders, `...`, or "for brevity"; a clean-breakpoint continuation protocol | Guarantees completeness, not correctness/compilation; literal-token greps miss semantically incomplete code |
| `example-using-skills` (+ a `SessionStart` routing-inject hook) | meta | An always-on routing map: tier-ordered trigger→skill table, conflict resolution (**match on the object, not the verb**), and a "if a skill might apply, invoke it" mandate | A routing nudge; does not guarantee the agent picks correctly |
| `example-dead-code-audit` | audit | On-request cleanup sweep whose value is a **hard gate against false-positive dead-code claims**: a candidate is "dead" only when multiple independent cross-checks all come back empty | Static finders over-report on template-driven / dynamically-dispatched code; never auto-delete |

**Tier coverage after these land:** Workflow, Guard, Feature, Audit, and the Meta routing layer
all have at least one runnable exemplar (Feature and Audit are currently empty).

### B. HARVEST — port the nugget into an existing skill/doc

| Source capability | Nugget worth keeping | Lands in |
|---|---|---|
| `review` (private 3-stage) | A 0–100 confidence-scoring rubric + a scope gate that filters adversarial false positives | `example-review` |
| `debug` (private) | A "build a fast deterministic pass/fail loop first" step, the test-collection trap, and a 3-failure escalation template | `example-debug` |
| `session-handover` (private) | The **Cold Reader Test** (a fresh agent reads your handover cold; ship only if it needs ≤1 clarification) + a severity-graded integrity gate | `docs/session-preservation.md` |
| `session-save` (private) | An "anchored-iterative" handover template + a merge-don't-regenerate rule | `docs/session-preservation.md` |
| `lessons-audit` (private) | A lesson-value scoring frame (gates → score → severity-rescue) + a "dare to report zero lessons" honesty gate | `docs/lessons-as-rules.md` |
| `prompt-refiner` (private, richer) | A "grill mode" (iterative one-question interview that greps the codebase to verify user claims) + a 4-tier clarity scale | `prompt-refiner` |
| `pre-commit-check` (private) | An append-only failure-modes registry + an advisory-vs-blocking tiering note | A doc beside the existing commit gate |
| `architecture-guard` (private) | A domain-free architectural-quality vocabulary (deep module / seam / deletion test) — itself an upstream MIT import | A small standalone doc |

### C. RECLASSIFY — the correct mechanism is a hook/tool, not a skill

| Source | Correct mechanism | Why |
|---|---|---|
| `sync-guard` (private) | A `PostToolUse` hook + a manifest/drift tool | The trigger is a deterministic file create/delete/rename event. A bypassable, keyword-matched skill would silently skip the sync when no keyword matches — that downgrades the guarantee |
| `config-guard` (private) | Fill the reserved `_your-config-guard_` registry placeholder + a lint/CI rule | Its value is *determinism* (a silent wrong-context config read must always be caught), which a bypassable skill cannot provide |

> **Governance artifact this surfaces:** a short `docs/guard-mechanisms.md` stating the rule —
> *a hook is a deterministic seatbelt that always fires; a tool/CI gate enforces with history; a
> skill is model-invoked and bypassable; a sub-agent is an isolated independent pass.* When a
> guard's value is "always fires," it is not a skill. The deterministic mechanism is
> authoritative; any same-named guard skill is only the advisory layer.

### D. BLUEPRINT — ship as documentation (breadth at near-zero context cost)

| Source | Proposed doc |
|---|---|
| The two UI-redesign workflows (private, admin + public) | **One** `docs/ui-redesign-workflow.md` with an admin/public toggle: target-routing → visual-scope gate → content-gap audit → use-case interview → plan-before-code → a no-fabrication / spec-vs-reality content gate → boundary verification → retrospective. The brand content (palette, token prefixes, component macros, SEO-block layout) is **not** shippable and stays a per-project placeholder |
| A UI standards reference (private) | A "design discipline" note: numeric design dials, a scan→diagnose→fix audit loop, and anti-AI-slop rules (several already upstream MIT) |
| `architecture-guard` (private) | The "path-scoped rule-card" pattern |
| A code-graph usage protocol (private) | The durable lesson — *benchmark an external tool's accuracy, ban its 0%-accurate queries, degrade gracefully to grep* — folded into the honesty/limits docs |
| All of the above + the catalog | `SKILL_CATALOG.md`: the full phased capability taxonomy, each entry tagged LIVE / BLUEPRINT / ADOPTER-FILLS / REJECTED. This is the "comprehensive map" delivered at doc cost |

### E. REJECT — not as a ship item

| Source | Reason |
|---|---|
| A code-graph assist skill | Ships **no engine** — it only calls an external graph server. Shipping the skill without the engine would oversell (a blueprint masquerading as shipped) |
| A "zoom out one layer" skill | Its generic core is an unmodified third-party MIT skill; after stripping domain vocabulary nothing original remains — link upstream instead |
| An ETL-pipeline guard | Almost entirely the private app's pipeline internals; the one transferable idea (navigate to the right section; beware *silent* data corruption) is too thin to ship alone |
| A research-workflow skill | Duplicates the existing `example-research`; salvage only its banned-behaviors list + mandatory-comparison-table |
| Architecture / config / ETL guards *as skills* | Their value is determinism → they belong in the invariant tool / lint / hooks, not in bypassable skills |
| Brand UI skills *as ship items* | Domain-locked (a specific brand palette, token prefixes, component catalog). Keep the README's reserved `_your-ui-guide_` placeholder; ship the method (section D), not the brand |

## Roadmap (waves)

Every new skill/tool must follow the golden rules: **stdlib-only core**, **a runnable `examples/`
entry + tests**, a registry row, a domain-free body, and an honesty caveat. Each wave is
independently shippable; read each result before starting the next.

**Wave 0 — Harden the system (do first; this *lowers* ongoing cost).**
- Gate `skill_lint.py` and `check_context_budget.py` in `.pre-commit-config.yaml` + CI (today
  they only run via their own unit tests, so real drift can ship green).
- Add an enforced budget cap to `check_context_budget.py`, mirroring how the README test-count
  metric is already drift-guarded. **Shipped (corrected) as a live-skill COUNT cap (`--max-skills`)
  plus the automatic per-skill body-critical (a `SKILL.md` > 800 lines → exit 1), NOT a total
  skill-body-token cap.** Why the change: per Claude Code's progressive disclosure only a skill's
  *description* is always loaded — the body loads on-demand when the skill is invoked — so a
  total-body cap mis-measures session-start (~5× over, measured) and creates false pressure to trim
  valuable bodies. The honest session-start guards are the description-length lint + the count cap;
  `--max-skill-tokens` remains an opt-in *maintenance* budget only.
- Extend `skill_lint.py`: recognize an `archived: <date>` frontmatter field; flag a skill that
  references another skill with no registry row; **warn when a guard-tier skill lacks a "does NOT
  do" line** (makes the honesty contract greppable).

**Wave 1 — The meta gap + correct-mechanism guards.**
- `example-using-skills` + the `SessionStart` routing-inject hook.
- `example-output-guard`.
- Reclassify: the file-CRUD sync guard → `PostToolUse` hook + manifest/drift tool; fill the
  `_your-config-guard_` placeholder.
- `docs/guard-mechanisms.md`.

**Wave 2 — The capability skills (gap-fillers).**
- `example-tdd`, `example-optimize`, `example-premortem`, `example-dead-code-audit`,
  `example-cook`, `example-external-ref` (+ its `references/` license-matrix and salvage-path).

**Wave 3 — Harvest nuggets** (section B) into the existing skills and docs.

**Wave 4 — Blueprints** (section D), including `SKILL_CATALOG.md`.

**Cross-cutting:** the README "5 example skills" figure and the At-a-glance table are
drift-guarded by a metrics test — every wave that adds a skill must update those numbers in the
same change.

## Cost governance

A dozen-plus live skills is past the point where a solo maintainer can eyeball the context budget.
The Wave-0 budget cap is what keeps growth honest — but it guards what *actually* costs session-start
context: the live-skill **count** cap (`--max-skills`) bounds the always-loaded routing-map/description
surface, and the per-skill body-critical stops any single skill becoming a monster. (Skill *bodies*
load on-demand, so there is deliberately no total-body session-start cap — that would mis-measure the
cost; see the Wave-0 note.) Breadth beyond the exemplars lives in `SKILL_CATALOG.md` and blueprints,
which cost zero routing context.

## Honesty notes / open limits

- This is a **proposal**; nothing here ships until its wave is built, tested, and its honesty
  caveat written. Until then, every row above is a BLUEPRINT, not a SHIPPED capability.
- The 13-skill target is a deliberate choice to favor coverage; a smaller set is defensible and
  the Wave-0 cap exists precisely so the decision stays reversible.
- Several harvested nuggets and one vocabulary doc are upstream MIT imports — attribution must
  travel with them (see [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)).
- Routing maps, guard skills, and budget heuristics are seatbelts, not boundaries. They reduce
  footguns; they do not guarantee the agent routes, reviews, or measures correctly.
