---
name: place-rule-where-it-fires
description: "Place a promoted rule where it ACTUALLY fires, not where a governance scope-table says. A path-scoped `.claude/rules/*.md` loads only on a matching file EDIT, so a fileless reasoning lesson can only live in always-loaded CLAUDE.md."
metadata:
  type: feedback
---

Deciding where to promote a "verify against ground truth, don't trust framing" lesson, a review split
on placement. A governance scope-table routed a "whole-project" lesson to a CLAUDE.md section but also
said "prefer path-scoped rules over growing CLAUDE.md" — so the first instinct was to fold it into an
existing path-scoped rule. That was WRONG on the mechanics: a `.claude/rules/*.md` carries a `paths:`
glob and loads only when you EDIT a file matching it. This lesson's trigger is a *fileless* moment —
about to assert, recommend, review, or judge — touching no file — so no `paths:` glob fires then.
Folding it into a path-scoped rule looks taxonomically correct but is silent exactly when the lesson is
needed. Only CLAUDE.md (loaded every session, unconditionally) fires at a fileless reasoning moment.

**Why:** scope ("what does it apply to") and firing ("when does it load") are different axes; reasoning
only about scope mis-places a metacognitive lesson into a rule that never fires at the right moment — a
silent loss. The home that "fits the taxonomy" can be the one that never loads when it matters.

**How to apply:** before placing a promoted lesson, ask WHEN it must fire and confirm the candidate home
actually loads then. A path-scoped rule fires only on an edit matching its `paths:`; if the lesson's
trigger is a reasoning / review posture (no file touched), it cannot be a path-scoped rule — it must go
in the always-loaded core (CLAUDE.md), accepting the always-on cost, or stay as recalled memory.
Reserve `.claude/rules/*.md` for lessons genuinely tied to editing a kind of file.
