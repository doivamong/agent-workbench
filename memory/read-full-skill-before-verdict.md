---
name: read-full-skill-before-verdict
description: "Before a SHIP / REJECT / keep verdict on a reusable artifact (a skill, module, or doc), judge from its FULL body, not its one-line description — guessing from blurbs produced wrong rejects and undercounted good candidates by ~3x."
metadata:
  type: feedback
---

Evaluating a set of reusable artifacts for distillation, my first pass judged them from their one-line
descriptions plus my own summary. That produced **2 wrong REJECTs** and **undercounted** genuine
candidates (~2-3 guessed, ~7-8 once read in full). The user caught it by asking "what benefit did you
not see?".

**Why:** an artifact's value lives in its body — the mechanism, the hard gates, the
anti-rationalization tables, the honesty caveats — not in its trigger blurb. A "redundant"-looking
item can carry multi-perspective planning + orchestration, or a license-decision matrix that *is* a
core principle made operational. None of that is visible from the description. The creed is "verify
with evidence, don't guess" — I violated it on exactly the artifacts I was judging.

**How to apply:** before any SHIP / BLUEPRINT / RECLASSIFY / REJECT verdict on an artifact, read its
full source (skim its references); separate the generic core from the domain coupling with line-cited
evidence; check mechanism-fit (skill vs hook vs tool vs doc) and overlap with what already exists.
Delegating the full reads to per-item sub-agents (not excerpt-only readers) scales this without
re-introducing the skim error.
