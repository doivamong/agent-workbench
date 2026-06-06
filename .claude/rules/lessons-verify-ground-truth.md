---
description: Before a verdict/assertion on a skill, audit, doc, or tool — verify the load-bearing claim against the source itself, not its framing. Loaded when editing a skill, doc, or tool.
paths:
  - ".claude/skills/**"
  - "docs/**"
  - "tools/**"
---

# Verify against ground truth before you assert

The always-on kernel is in `CLAUDE.md` ("verify against ground truth, don't trust framing … right on
the facts ≠ right on cause / severity / fix"). This rule is the **operational self-check** that fires
when you are editing the artifacts where confident-but-unverified verdicts cost the most: skills you
are judging or writing, docs you are reviewing or recommending in, and tools whose behavior you are
asserting. It is the promotion of a lesson that recurred across **three distinct sessions** — see
Provenance at the end. (The *why* is the kit's honesty tenet — [`PHILOSOPHY.md`](../../PHILOSOPHY.md);
this is the *how*, one instance of the [lessons-as-rules](../../docs/lessons-as-rules.md) discipline.)

## Pattern — the three faces of one trap

A conclusion is handed downstream (to the user, an adversarial pass, a CI/leak gate) as its **first**
verification. The facts may be right while the *inference* — cause, severity, fix, value — is wrong.

- **Judge from the body, not the blurb.** Judging a skill / file / library from its one-line
  description (not the full source) produces wrong rejects and undercounts value — the mechanism,
  gates, and honesty caveats live in the body, never the trigger line.
- **Verify the load-bearing assumption + the deciding axis.** Before "X auto-loads" / "Y is better" /
  "this is done", check the one assumption the conclusion rests on against the running system or the
  source — and actually evaluate the axis that decides it, not a cheap proxy (DRY, effort, file-count).
- **Correct an audit, don't confirm it.** An external audit/review handed to you is just another
  unchecked claim. "Matches the reference / the dogfooded config" ≠ "is correct". Trace whether a
  dependency chain actually reaches the target before calling a gap a bug; watch one root cause
  double-counted as several findings; sanity-check each recommended *fix* — a plausible remedy can be
  the bug.

## Unsafe vs safe

- **Unsafe:** "rejected `itf-cook` as redundant" (read only the description); "repo `./memory/`
  auto-loads" (assumed, never run); "the audit is right, ship its fixes" (confirmed, not traced).
- **Safe:** read the full SKILL.md and cite lines; run `memory_recall_doctor` and read the output;
  trace `sync_guard`'s dependency chain before agreeing the installer should wire it.

## Self-check (before you state a verdict in these areas)

1. Did I read the **full source**, or just its framing / one-line description?
2. What is the **load-bearing assumption**, and did I verify it against the running system / source —
   not the docs' *claim* about it?
3. What is the **deciding axis**, and did I evaluate *it* (not a proxy)? Is every number measured, not
   guessed?
4. For an audit/review: am I conflating "matches the reference" with "is correct"? Did I trace the
   chain and recompute severity myself?

State confidence proportional to what you actually checked.

## Bypass

A throwaway/low-stakes read does not need the full ceremony — but *say so*: state the scope you
checked and give the conclusion a confidence (high/medium/low) rather than asserting it flat.

## Honest limit

A convention, not an enforcer: nothing here checks that you read the source or traced the chain. It
loads the self-check at the moment you edit a skill, doc, or tool — it cannot make you run it.

## Provenance (recurrence that earned the promotion — governance §4)

Promoted 2026-06-07 from three L3 memory facts that shared `metadata.group: verify-against-ground-truth`
and recurred across **3 distinct sessions** (origin session ids differ; incidents genuinely separate):
`read-full-skill-before-verdict` (ITF skill distillation), `verify-load-bearing-before-asserting`
(memory-overhaul), `audit-can-be-right-yet-misreason` (external-audit re-review, PR #22). The family
kernel already lived in `CLAUDE.md`; what was deferred until the 3rd sighting was this operational
self-check (governance §4: ≥3 recurrences across ≥2 sessions).
