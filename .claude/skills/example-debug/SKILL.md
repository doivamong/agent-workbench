---
name: example-debug
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

> **Announce on activation:** "Using example-debug — I'll find the root cause before fixing."

The expensive mistake in debugging is fixing a *symptom*. This skill forces the order:
understand, then change.

## Process

1. **Reproduce.** Get a reliable, minimal way to trigger the bug. If you can't reproduce it,
   you can't know you fixed it. Capture the exact input, environment, and the actual vs
   expected behaviour.
2. **Locate.** Read the code on the path from trigger to symptom. Add a probe (log/print/test)
   that confirms *where* reality diverges from expectation — don't guess.
3. **HARD GATE: root cause identified.** State the cause in one sentence ("X is null because Y
   never sets it when Z"). Do **not** write a fix until you can. A fix without a named cause is
   a guess.
4. **Fix the cause, not the symptom.** Make the smallest change that addresses the root cause.
   Note if you find sibling bugs — don't silently expand scope.
5. **Prove it.** Add a test that **fails before** the fix and **passes after**. Re-run the
   reproduction. A bug fix without a regression test invites the bug back.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I'm pretty sure it's this line" | "Pretty sure" is a hypothesis. Confirm it with a probe before changing code. |
| "I'll add a null-check and move on" | A null-check on a value that should never be null hides the real cause. Ask why it's null. |
| "It's fixed, it works now" | Works *once*? Re-run the reproduction, and write the test that proves it. |
| "No time for a test" | The test is how you (and CI) know it stays fixed. It's the cheapest insurance you'll buy. |

## Tip

If the symptom is far from the cause (a wrong value surfacing three layers up), bisect: confirm
the value is correct at the boundary, then halfway, narrowing until the divergence point is
found. Guessing scales linearly; bisecting scales logarithmically.
