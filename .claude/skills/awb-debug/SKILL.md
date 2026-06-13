---
name: awb-debug
description: >
  WHAT: debug a bug methodically — reproduce it, find the ROOT cause, then fix,
  then prove the fix.
  USE WHEN: the user reports something broken / wrong / crashing and the cause is
  not yet known ("it errors", "wrong output", "doesn't work", "500", "flaky").
  DO NOT TRIGGER: implementing a new feature (use a plan-then-code skill); a pure
  code review; when the cause is already known and it's a one-line edit.
tier: guard
---

# Debug, root cause first

> **Announce on activation:** "Using awb-debug — I'll find the root cause before fixing."

The expensive mistake in debugging is fixing a *symptom*. This skill forces the order:
understand, then change.

## Process

1. **Reproduce — build a fast pass/fail loop.** Get a reliable, minimal, *fast* way to trigger
   the bug — ideally a one-command signal you can re-run after every change. If you can't
   reproduce it on demand, you can't know you fixed it. Capture the exact input, environment, and
   actual vs expected behaviour.
2. **Locate.** Read the code on the path from trigger to symptom. Add a probe (log/print/test)
   that confirms *where* reality diverges from expectation — don't guess.
3. **HARD GATE: root cause identified.** State the cause in one sentence ("X is null because Y
   never sets it when Z"). Do **not** write a fix until you can. A fix without a named cause is
   a guess.
4. **Fix the cause, not the symptom.** Make the smallest change that addresses the root cause.
   Note if you find sibling bugs — don't silently expand scope.
5. **Prove it.** Add a test that **fails before** the fix and **passes after** — and confirm it
   actually runs (a mis-named test file passes by collecting nothing;
   [`awb-tdd`](../awb-tdd/SKILL.md) guards this trap). Re-run the reproduction. A fix
   without a regression test invites the bug back.
6. **Prevent the class — when it's cheap.** Ask whether the *whole class* of this bug can be
   made to fail loudly instead of silently: a guard or assertion at the boundary where the bad
   value first appears, a type that makes the invalid state unrepresentable, validation at the
   trust edge. Do this only where it's cheap and targeted — don't bolt defensive checks onto
   every layer (that just hides the next bug). If prevention isn't cheap here, say so and move on.

## When it won't reproduce on demand

Step 1 needs a reliable trigger. When the bug won't reproduce, classify *why* before guessing — each
class has its own probe:

- **Timing / concurrency** — order- or race-dependent. Probe the suspected window (logging or a
  forced delay), stress-loop the path, look for shared state touched without a lock.
- **Environment** — passes here, fails in CI/prod (or the reverse). Diff the environments (versions,
  env vars, OS, cwd, clock, locale) and reproduce *in* the failing one, not a proxy — AWB's
  cold-vs-warm and CI-only-failure traps live here.
- **State / data** — only fires with specific accumulated state or input. Capture the exact
  state/input, bisect the data, reset to a known point and replay.
- **Genuinely intermittent** — none of the above isolates it. Don't fix blind: add always-on logging
  at the divergence boundary and wait for the next occurrence *with evidence*.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I'm pretty sure it's this line" | "Pretty sure" is a hypothesis. Confirm it with a probe before changing code. |
| "I'll add a null-check and move on" | A null-check on a value that should never be null hides the real cause. Ask why it's null. |
| "I'll harden every layer so this never happens again" | Over-hardening hides the next bug behind redundant checks. One guard at the right boundary beats five scattered ones. |

## When you're stuck

- **Bisect, don't guess.** If the symptom is far from the cause, check the value at the boundary,
  then halfway, narrowing to the divergence point — logarithmic, not linear.
- **Three failed fixes = wrong model.** If the bug survives three attempts, stop changing code: the
  assumption you're *most* sure of is the likely culprit. Re-derive from scratch or hand off — don't
  spend a fourth guess.

## Honest limit

This is a *method*, not a debugger: it does **not** locate the bug for you or guarantee the named
root cause is the right one — it forces you to name and prove it before changing code. A green
regression test proves the one symptom is gone, not that a sibling bug doesn't remain.
