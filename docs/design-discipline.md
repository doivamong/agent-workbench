# Design discipline — make UI quality explicit, not a vibe

"Make it look better" is unfalsifiable, so an agent (or a person) drifts: every choice becomes an
ad-hoc judgement, the result is inconsistent, and nobody can say whether a change helped. This note
turns UI quality into **explicit, checkable decisions** — the same move
[`docs/patterns/optimization-loop.md`](patterns/optimization-loop.md) makes for performance. It is
the quality companion to [`ui-redesign-workflow.md`](ui-redesign-workflow.md) (the *process*); this
is the *bar*.

It ships the **discipline**, not a brand. The specific scales, rule sets, and anti-pattern catalogs
are well-trodden ground in front-end engineering — fill them from your team's standards or an
established checklist. The standard is [`PHILOSOPHY.md`](../PHILOSOPHY.md): best-fit, honest about
limits.

## 1. Numeric design dials — name the knobs, give them numbers

Subjective choices ("clean", "premium", "dense") become consistent and overridable when you encode
them as a few **named numeric dials** with a fixed scale. Then a vibe word maps to dial values
instead of to a fresh guess each time, and a reviewer can check the page against the numbers.

Pick a small set of dials that matter for *your* product and define each on a 1–N scale, e.g.:

```
‹LAYOUT_VARIANCE›   # 1 = plain table/list … N = rich card dashboard
‹DENSITY›           # 1 = spacious … N = compact
‹MOTION›            # 1 = static … N = heavy animation
```

Three rules keep dials honest:

- **A default per context.** A data-dense admin view and a marketing landing page want different
  defaults — write them down so "unspecified" doesn't mean "whatever the model felt like."
- **Hard caps.** Cap the dials that cause regressions when maxed (e.g. cap MOTION on a tool used all
  day — high motion fatigues daily users; cap visual-variance below experimental-art territory for a
  business app). A cap is a refusal, not a suggestion.
- **User override wins.** "Make it more compact" should move a dial, not trigger a redesign debate.

The value is not the specific numbers — it is that the choice is now **stated**, so it's consistent
across pages and a diff can be reviewed against it.

## 2. The scan → diagnose → fix audit loop

When asked to "improve" an existing screen, don't free-associate edits. Run a fixed loop:

1. **Scan** — read the file first. What does it extend? Which blocks/partials does it use? Which
   route renders it, with what data? You can't improve what you haven't mapped.
2. **Diagnose** — walk a fixed checklist of quality regions and ask a specific question of each,
   rather than eyeballing. A workable region set:

   | Region | The question |
   |---|---|
   | Typography | Is the heading hierarchy correct? Are numbers aligned/monospaced where they should be? |
   | Colour | Do badges/buttons use **semantic** status colour, not one default everywhere? |
   | Layout | Table vs cards — does the choice fit the amount and shape of data? |
   | States | Are empty / loading / error states present and meaningful? |
   | Density | Tables compact and scannable; right-aligned numerics; sticky headers when long? |
   | Interaction | Are async/partial updates indicated; do partials handle the empty case? |

3. **Fix — within constraints.** Add or override; don't fork the design system. Keep custom styles in
   the stylesheet (not inline), don't pull in a new CSS/JS dependency for a tweak, and don't break the
   base template's block structure or the partial-response contract.

Naming the regions is what stops the audit from being "I looked and it seemed fine."

## 3. Anti-AI-slop — avoid the machine-generated tells

LLM-generated UI has fingerprints. They're not *wrong* so much as *generic* — the giveaways of a
template nobody decided on. Codify your own anti-pattern list; common offenders:

- **One primary button for every action.** Use semantic intent — a destructive action is not styled
  like a confirm. A page where every button is the same colour made no decisions.
- **The empty info-box as an empty state.** Replace a blank placeholder with a real empty state:
  an icon, a meaningful message, and the action that resolves it.
- **Decorative icons with no label.** An icon that conveys meaning needs an accessible label and clear
  context, not a generic glyph.
- **A centered hero on a data screen.** A dashboard is data-first; a landing-page hero is the wrong
  archetype for it.
- **Stock framework colours left as-is.** Override the default palette deliberately; the default blue
  is a tell that no brand decision happened.

The test for each rule: *would a thoughtful designer have done this on purpose?* If it only happens
because it's the path of least resistance, it's slop.

## 4. Accessibility & performance as hard rules, not aspirations

A few a11y/perf rules are cheap to honour while building and expensive to retrofit, so treat the
critical ones as **hard rules** scanned on every redesign — not a "nice to have" at the end. The
specifics below are industry standards (WCAG, platform HIGs, browser-compositor behaviour), not this
kit's invention; encode the set you commit to:

- **Respect reduced-motion.** Every transition/animation guarded by a `prefers-reduced-motion`
  fallback. (Standard accessibility behaviour, and a motion-sensitivity safeguard.)
- **Touch targets.** Interactive elements meet the minimum hit size on touch (a widely-used floor is
  ~44×44px).
- **Animate cheap properties only.** Prefer `transform`/`opacity` (GPU-composited) over animating
  layout properties like width/height/top/left, which force reflow.
- **Disciplined stacking.** Z-index from named tokens, not arbitrary large numbers — `‹--z-modal›`,
  not `z-index: 9999`.

Keep the full list in a reference the redesign workflow's verify phase scans (`‹your-a11y-perf-rules›`),
and gate the mechanical ones (token usage, hard-coded colours) with a linter where you can — a rule
you can grep is a rule that holds.

---

## Honest limits

- **A discipline, not a design tool.** This makes quality *checkable*; it does not make a page
  *beautiful*. Dials and checklists catch the generic and the broken — taste and product fit still
  need a human reviewer.
- **The specifics are yours.** The dial scales, the region checklist, the anti-pattern list, and the
  a11y/perf rule set are placeholders here on purpose — they depend on your stack and brand. The
  reusable part is the *shape*: numeric dials, a fixed audit loop, a named anti-slop list, hard a11y
  rules. (Filling the brand is the reserved `_your-ui-guide_` [ADOPTER-FILLS](../SKILL_CATALOG.md)
  slot.)
- **A green linter is not a good design.** Mechanical gates (token usage, contrast, motion guards)
  prove the floor was met, not that the result is good — see
  [`measurement-honesty`](../.claude/rules/measurement-honesty.md). Don't read a passing check as
  "the design is fine."
