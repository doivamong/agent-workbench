---
name: example-review
description: >
  WHAT: review a code change in three passes — does it meet the spec, is it well
  built, and can an adversary break it.
  USE WHEN: the user says "review my changes / this PR / what I just wrote", or
  before committing a non-trivial change.
  DO NOT TRIGGER: a broad "audit the whole codebase" request; research/compare
  questions; when no code has been written yet.
tier: guard
---

# Three-stage review

> **Announce on activation:** "Using example-review — three passes: spec, quality, adversarial."

A checklist review catches typos. A *staged* review catches the things checklists miss:
wrong assumptions, security holes, and race conditions. Run the passes in order; stop early
only if a blocking issue makes later passes moot.

## Stage 1 — Spec compliance

Does the change actually do what was asked? Compare the diff against the stated goal.
Flag anything implemented that wasn't asked for (scope creep) and anything asked for that's
missing.

## Stage 2 — Quality

Walk the diff against a quality bar. Keep your real bar in a reference file so this stays
short:

- Correctness, error handling, resource cleanup.
- Readability over cleverness; naming; dead code.
- Tests exist for the new behaviour.

See [`references/quality-checklist.md`](references/quality-checklist.md) for the full list.

## Stage 3 — Adversarial (the pass that earns its keep)

Stop reviewing as the author; start attacking as an adversary. Ask:

- What input breaks this? Empty, huge, malformed, concurrent, malicious?
- What does this assume that isn't guaranteed?
- If this is security- or money-adjacent, how would I exploit it?

**Scope gate:** you can skip Stage 3 for tiny, non-sensitive changes (say, ≤2 files and a
few dozen lines that don't touch auth, payments, or data integrity). Everything else gets it.

## Output

Report findings ranked by severity (blocking / important / nit), each with a `file:line`
and a concrete fix. Don't soften a real problem to be polite — technical rigor over comfort.

## References

- [`references/quality-checklist.md`](references/quality-checklist.md) — the Stage 2 bar
