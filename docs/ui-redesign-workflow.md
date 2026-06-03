# UI redesign workflow — a gated method (admin + public)

A redesign goes wrong in expensive, *repeatable* ways: you polish a layout the user never had a
problem with, lock an archetype before learning how the page is actually used, ship the wrong brand
colour and iterate on it four times, or discover at the footer that a sticky element collides with
the nav. The fix is not talent — it is **moving the cheap checks before the expensive work**.

This is the method, distilled to its domain-free spine. It does **not** ship a brand: the palette,
token prefixes, component macros, font policy, and SEO-block layout are yours to fill (every
`‹placeholder›` below). It ships the *sequence of gates* that keeps a redesign from thrashing. The
standard is [`PHILOSOPHY.md`](../PHILOSOPHY.md) — best-fit, honest about limits. It is the design
sibling of [`design-discipline.md`](design-discipline.md) (the quality dials) and
[`awb-plan-then-code`](../.claude/skills/awb-plan-then-code/) (plan before code).

## Why the gates exist — the economics

Three numbers, observed repeatedly, justify the front-loading. Treat them as the order of magnitude,
not gospel:

| Mistake | Relative cost | The gate that prevents it |
|---|---|---|
| Pivoting the design **after** it ships | ~10× a pre-build decision | use-case interview + plan-approval gate |
| Iterating on aesthetics post-ship (wrong colour, wrong density) | ~4× | brand-confirm gate + complete-diff pass |
| Redesigning the layout when the real problem was stale **content** | a whole wasted cosmetic pass | content-gap audit |

A "hard gate" below means: **do not advance to the next phase until it is satisfied.** A gate you can
talk yourself out of is not a gate — the value is in refusing to skip it.

## Two surfaces, one spine

Most of the workflow is shared. Two surfaces diverge in their constraints — an **internal/admin**
surface (authenticated, dense, data-first) and a **public/marketing** surface (anonymous, SEO- and
content-sensitive, cached). Route to the right one first; the spine is the same, the extras differ.

| Aspect | Admin / internal | Public / marketing |
|---|---|---|
| Audience | authenticated operators, daily use | anonymous visitors, first-time |
| Base template | `‹admin-base›` | `‹public-base›` (carries the SEO/meta blocks) |
| Styling tokens | `‹admin-token-prefix›` | `‹public-token-prefix›` |
| Auth / CSRF | role-checked; CSRF required | anonymous; cached endpoints may need CSRF-exempt — verify |
| Caching | short polling, fresh data | CDN-cached pages — stale-content risk |
| Dominant risk | wrong archetype for the daily flow | **fabricated content** + SEO/structured-data regressions |
| Extra gates | brand-confirm, archetype council | global-elements audit, schema/data reality verify, no-fabrication gate, boundary verify |

---

## Phase 0 — Route, scope, and size

### 0.0 Target routing (first, always)

Classify the target by its route/template into **admin** or **public**. They use different base
templates, token sets, and constraints; picking the wrong track silently imports the wrong rules.
If the target is public, switch to the public track (the extra gates below) before continuing.

### 0.1 Preflight

```
□ Golden reference: pick an already-good page of the same shape to match
□ Target: locate the route handler, the template, and its tests
□ History: read the last few commits touching the target
□ Scale tier: SMALL (1–3 files) · MEDIUM (4–6) · LARGE (≥7) — tier sets the rigor
```

**Output:** a five-line scope memo — target, scale tier, golden reference.

### 0.2 Visual-scope confirm — HARD GATE

When the user says "redesign" without saying *what kind*, stop and confirm one of three scopes
before any work. Skipping this is the classic source of wasted commits (you rebuild the layout; they
wanted a visual refresh, or vice versa).

```
Which kind of redesign?
  □ Layout / architecture only (structure changes, visuals unchanged)
  □ Visual refresh only (typography, colour, spacing — structure unchanged)
  □ Both (full redesign)            ← default if unstated, but CONFIRM
```

The gate also requires defining an **observable** acceptance up front: a before/after difference a
reviewer can actually see (not "looks better"). If you can't name the observable, the scope isn't
settled yet.

### 0.5 Content-gap audit (form/config pages especially)

Before picking a prettier layout, check whether the real complaint is **content obsolescence** — the
UI is missing options the user now needs, forcing them to edit raw config by hand. A cosmetic
redesign over a content gap leaves the user just as frustrated, in nicer paint. Inventory what the
page *should* expose vs what it does; a large gap often re-tiers the work upward.

### 0.6 Use-case interview — HARD GATE (MEDIUM/LARGE)

Do **not** lock a layout archetype before you understand the use. A short interview, grounded in
evidence where you can get it:

1. **Frequency** — how often is this page used? (Check usage/audit logs if available, don't guess.)
2. **Audience size & role** — personal / team / many? (Check the permission model.)
3. **Mental model** — five questions: what is the user here to *do*, in what order, what do they look
   at first, what is the anchor action?

**Output:** an archetype-fit verdict + a one-line "design read" that feeds the layout pick. The
person who uses the page daily gets a **veto** over an archetype that fights their flow — an
aesthetic argument cannot override a daily-flow veto.

### Public-only gates (run alongside Phase 0)

- **Global-elements audit — HARD GATE.** A public surface usually renders shared fixed/sticky
  elements (nav, cookie/contact banner, back-to-top, chat button) that claim screen regions with no
  central registry. Before adding a new fixed element, catalog the existing ones and document a
  z-index hierarchy and region-claim matrix, or you ship a collision you'll only see at one viewport.
- **Schema / data reality verify — HARD GATE.** Before building, verify the page's assumptions
  against the *real* data: do the tables/columns/rows the spec assumes actually exist and have data?
  Record every gap explicitly as **"spec assumed X, reality is Y, decision Z"** in the plan.

---

## Phase 1 — Baseline survey

Write a NOTES file capturing what's actually there before you change it: template/block structure,
styling tokens in use, JS modules, the backend route/service that renders it, auth model, caching,
and your open questions. The point is to **catch your assumptions before code** — a token you assumed
was page-local may be shared by other pages and break them when you touch it. (Skip for SMALL.)

## Phase 2 — Gap analysis

Enumerate what the old page does so nothing is silently dropped in the new one:

```
□ Every button / action
□ Every config toggle (checkbox / radio / select)
□ Every status/badge variant
□ Cross-check against the plan: which feature got dropped?
□ Localization audit: any hard-coded display strings that bypass i18n?
```

## Phase 3 — Layout pick + brand audit

### 3.1 Brand audit — HARD GATE (admin), before the layout pick

Audit the existing brand tokens (`‹brand-token-prefix›`) and decide the palette **with the user
before implementing** — do not default to the framework's stock colour. Shipping the framework
default and discovering it violates the brand costs a round of polish iterations. If you introduce a
new palette, justify it in the plan and get approval.

### 3.2 Layout archetype

Pick a layout archetype that fits the use-case read from 0.6, not the prettiest one. Maintain a small
catalog of archetypes (`‹your-archetype-catalog›` — e.g. dashboard, list-and-inspector, wizard,
catalog-grid, editorial, help-center) each with a "use when". Cross-check the archetype-fit verdict
against the catalog and recommend one *with a rationale*, comparing it on a fixed set of criteria.

## Phase 4 — Council debate (LARGE; skip low-risk SMALL)

Pressure-test the design from independent viewpoints before building — the same idea as
[`awb-stress-test`](../.claude/skills/awb-stress-test/), applied to a UI. Use a fixed set of
personas so blind spots surface on paper. For **public** surfaces, prioritize a structured-data/SEO
lens, a content-accuracy ("does every claim have a source?") lens, a mobile-UX lens, and an
accessibility lens.

## Phase 5 — Plan artifact — HARD GATE

Write the plan to a file and **get approval before implementing**: objectives, files affected,
key decisions, phase breakdown, acceptance criteria, a risk register, and a rollback note. For
public surfaces, add the SEO goals (target structured-data types, a performance budget), the
caching/CSRF decision, and the content-source plan.

**5.5 Reference/prototype validation.** If the user supplied a mockup or reference, validate it on
**one real page first** (apply minimal changes, compare side-by-side, inspect computed styles) before
propagating. If the plan was written more than a day ago, re-review it against current reality — a
stale plan sends you fixing the wrong things.

## Phase 6 — Implement

Commit granularity follows the scale tier (SMALL ≈ one commit; LARGE ≈ one per phase).

### 6.1 Complete-diff pass — when matching a reference

Do **not** trickle one element per commit toward a reference — that turns into four-to-six retroactive
correction cycles. Instead: scan top-to-bottom comparing target vs reference, record **all** deltas
at once, then fix them in one pass (or a few logical groups, not a dozen). Match the reference
exactly; a deliberate deviation gets justified in the commit message.

## Phase 7 — Verify

Run the tests, then an adversarial checklist. A core set applies to both surfaces; public adds more:

| Check | Admin | Public |
|---|---|---|
| Feature parity (nothing dropped vs old page) | ✓ | ✓ |
| Injection / output-escaping in templated content | ✓ | ✓ |
| Empty / error / loading states present | ✓ | ✓ |
| Localization of all display strings | ✓ | ✓ |
| CSS classes referenced by the template actually exist | ✓ | ✓ |
| **No fabricated content** — every factual/legal claim traces to a real data or config source | — | ✓ |
| Structured-data / SEO blocks render and validate | — | ✓ |
| Caching + CSRF-exempt behaviour correct on cached endpoints | — | ✓ |

The **no-fabrication gate** is the public surface's load-bearing check: an anonymous marketing page
states claims to the world, so each must be verifiable against the real source — never invented to
fill a layout.

## Phase 8 — Boundary verification + retrospective

**Boundary verify (public especially).** Bugs cluster at boundaries. Verify *every* boundary —
top / middle / bottom of the page × desktop / mobile / tablet — not just the hero. The footer
collision you skip is the one that ships.

**Retrospective (LARGE).** Re-read the shipped files grounded in `file:line`, ideally from more than
one reviewer viewpoint, and triage what you missed. A pre-ship re-read routinely catches issues the
build missed.

## Phase 9 — Finalize + post-pivot cleanup

Run your finalize sequence in a fixed order (lint → format → docs-sync → secret check → stage →
commit) so a reorder doesn't undo a step. If you **pivoted mid-session**, do a function-level cleanup
pass for orphaned code and drifted docs, in a *separate* commit — a pivot leaves debris that a
file-level glance misses.

---

## Honest limits

- **This is a method, not a generator.** It sequences the decisions; it does not make them. It cannot
  tell you which archetype fits or which colour is right — it tells you to settle those *before* code,
  with the user, on evidence.
- **The brand is deliberately absent.** Palette, token prefixes, component macros, font policy, and
  SEO-block layout are domain-locked and ship as placeholders. The reusable part is the gate sequence;
  filling the brand is an [ADOPTER-FILLS](../SKILL_CATALOG.md) job (the reserved `_your-ui-guide_`
  slot).
- **The economics are observations, not laws.** The ~10× / ~4× figures are the order of magnitude from
  one team's experience; your multipliers will differ. The *direction* — cheap checks before expensive
  work — is the durable part.
- **Gates reduce thrash; they don't guarantee a good design.** A disciplined process can still ship a
  mediocre page. Pair it with [`design-discipline.md`](design-discipline.md) for the quality bar and a
  real reviewer for taste.
