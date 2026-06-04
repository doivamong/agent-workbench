---
name: recommend-user-benefit-first
description: "When recommending between options, rank by real user benefit / output quality FIRST; minimalism (DRY, \"smallest mechanism\", YAGNI) is only a tiebreaker among options that all fully deliver — never a reason to under-deliver function. Calibrate confidence to how deeply the deciding axis was evaluated."
metadata:
  type: feedback
---

Choosing between two designs for a feature, I picked the lean "point-to-a-doc" option over the fuller
"inline-procedure" option and called it "genuinely better, not marginal." It took the user pushing
twice to surface that the fuller option yields **higher-quality output** — an inline rubric / hard gate
is executed far more faithfully than the same steps left in a referenced doc — and that my "it
duplicates the doc" objection was wrong.

The bias: I scored **maintainer-ease** (DRY, small surface, low maintenance) and dressed it in
principled language ("smallest mechanism", YAGNI), while the **user-facing axis** (execution fidelity,
output quality) was absent from my scoring until prompted. I also overclaimed confidence on an
under-evaluated call.

**Why:** the goal is best-fit FOR THE USER, not easiest to build or maintain. "Smallest mechanism that
*truly closes the gap*" — optimizing "smallest" while dropping "truly closes the gap" inverts it.

**How to apply:** (1) lead every recommendation with "what does the user actually get?" and rank by
that. (2) Bring minimalism in only to break ties among options that ALL fully deliver the benefit.
(3) State confidence proportional to how deeply the deciding axis was actually evaluated — no
"genuinely better" before weighing the axis that matters.
