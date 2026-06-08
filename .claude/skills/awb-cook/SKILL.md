---
name: awb-cook
description: >
  WHAT: an advanced build workflow that adds three things to a plain plan-then-code flow —
  graduated oversight modes (how often it stops to ask you), multi-perspective planning (several
  independent plans, merged), and explicit orchestration of the guard skills at the right steps.
  USE WHEN: a larger / higher-stakes / multi-module change where a single plan would hide blind
  spots, or you want to dial the human-checkpoint frequency and plan from several independent
  angles ("cook this", "run the full workflow").
  DO NOT TRIGGER: a routine single-file change (use awb-plan-then-code); a one-line fix; a pure
  question; work where you do not want sub-agent fan-out. It enforces nothing — it is a bypassable
  exemplar, not a gate.
tier: workflow
oversight: high
---

# Cook (advanced orchestration workflow)

> **Announce on activation:** "Using awb-cook — pick an oversight mode, plan from several angles,
> then build through the guard skills."

For an ordinary change, [`awb-plan-then-code`](../awb-plan-then-code/SKILL.md) is the right,
lighter tool — cook is its heavier sibling for larger/riskier work, not a replacement.

## Scope

- **Does:** orchestrate plan → implement → verify → review while letting you set the checkpoint
  frequency and synthesizing multiple independent plans.
- **Does NOT:** enforce anything (every gate here is advisory — only a human or a real hook makes a
  gate binding), replace the guard skills it calls, or guarantee the merged plan is correct.

## Oversight modes (pick one at the start)

| Mode | Stops to ask you at | Use when |
|---|---|---|
| **interactive** (default) | the plan, and before commit | normal work |
| **fast** | only at an ambiguity or a destructive step | you trust the scope and want flow |
| **auto** | nothing (reports at the end) | a well-specified, low-risk, reversible task |

Looser oversight trades safety for speed; reserve **auto** for reversible, fully-specified tasks.

## Process

1. **Frame the task** — restate goal + acceptance criteria. If vague, refine first (`prompt-refiner`).
2. **Multi-perspective plan.** Produce several independent plans from different angles (MVP-first,
   risk-first, reuse-first) — ideally as parallel sub-agents so they don't anchor on each other (see
   [`docs/orchestration.md`](../../../docs/orchestration.md)). Then **merge**: keep what they
   *converge* on, surface where they *diverge* (a real decision), fold in any *unique* insight. A
   single plan hides its own blind spots — the merge is the point.
3. **HARD GATE (interactive/fast): approve the merged plan** before code.
4. **Implement** in small steps; hand non-trivial logic to [`awb-tdd`](../awb-tdd/SKILL.md).
5. **Run the guards at their step** (don't reinvent them): long generation →
   [`awb-output-guard`](../awb-output-guard/SKILL.md); config access →
   [`awb-config-guard`](../awb-config-guard/SKILL.md); before commit →
   [`awb-review`](../awb-review/SKILL.md).
6. **Verify with evidence** — run the tests/demo and read the output; never report done on a guess.
7. **HARD GATE (interactive): confirm before commit.** In fast/auto, commit per the mode and report.

## Honesty / limits

Cook enforces nothing — it *orchestrates* other skills; only a human or a real hook makes a gate
binding. The multi-perspective merge improves a plan, it does not prove it correct. The
graduated-oversight and multi-perspective-planning patterns are re-authored from
[`github/spec-kit`](https://github.com/github/spec-kit) (MIT) and
[`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official) (MIT) —
see [`THIRD_PARTY_NOTICES.md`](../../../THIRD_PARTY_NOTICES.md).
