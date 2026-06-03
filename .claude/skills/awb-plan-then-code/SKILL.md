---
name: awb-plan-then-code
description: >
  WHAT: a workflow for implementing a non-trivial change the disciplined way —
  plan first, then code, then test, then review.
  USE WHEN: the user wants to add a feature or make a multi-file change, or says
  "implement", "build", "add", "let's do X" where X is more than a one-liner.
  DO NOT TRIGGER: a single-line fix (just do it); a bug with an unknown cause
  (use a debug skill); a pure code review (use awb-review); a question.
tier: workflow
---

# Plan, then code

> **Announce on activation:** "Using awb-plan-then-code — I'll plan before writing code."

This is a template. It shows the *shape* of a reliable implementation workflow; adapt the
steps to your stack.

## Process

1. **Scout** — read the code you're about to touch and its neighbours. Don't propose changes
   to code you haven't read.
2. **Plan** — write a short plan: what files change, what each change does, how you'll know
   it worked. Keep it to a screen.
3. **HARD GATE: plan approved.** Do not write implementation code until the plan is agreed.
   If working solo, re-read your own plan and sanity-check it; if with a user, get a yes.
   This is the gate that prevents 80% of wasted work.
4. **Implement** — make the change. Match the surrounding code's style. No placeholders, no
   "TODO: finish this" left behind.
5. **Test** — add/extend tests. A change without a test that would have caught its absence is
   not done. Run the suite; it must pass.
6. **Review** — hand the diff to `awb-review` (or review it yourself adversarially) before
   committing.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "It's obvious, I'll skip the plan" | If it's obvious, the plan takes 60 seconds and confirms it. If it's not, the plan just saved you. |
| "I'll add tests after it works" | "After it works" rarely arrives. Write the test that proves it works. |
| "The plan gate is bureaucracy" | The gate is the cheapest place to catch a wrong approach — before any code exists. |

## References

- [`references/plan-template.md`](references/plan-template.md) — a fill-in-the-blanks plan
