---
name: awb-plan-then-code
description: >
  WHAT: a workflow for implementing a non-trivial change the disciplined way —
  plan, then code, then test, then review.
  USE WHEN: the user wants to add a feature or make a multi-file change, or says
  "implement", "build", "add", "let's do X" where X is more than a one-liner and the
  approach is already chosen (if it isn't, do awb-research first).
  DO NOT TRIGGER: a single-line fix (just do it); a bug with an unknown cause (use a
  debug skill); a pure code review (use awb-review); a question; a larger/higher-stakes
  build with checkpoints or multi-angle planning (use awb-cook); a spike to discover an
  unknown interface (build a throwaway slice first, then plan the real change).
tier: workflow
---

# Plan, then code

> **Announce on activation:** "Using awb-plan-then-code — I'll plan before writing code."

This is a template — the *shape* of a reliable implementation workflow; adapt it to your stack.

**Right-size it.** If you could describe the whole diff in one sentence (a typo, a log line, a
rename), skip the plan and just do it. Plan when the approach is uncertain, the change spans
multiple files, or the code is unfamiliar — a *legitimate* skip, not the "it's obvious"
rationalization the table fights.

## Scope

- **Does:** carry one non-trivial change through scout, one-screen plan, agree, implement,
  test, hand to review — a single plan and one approval.
- **Does NOT:** prove the plan correct (the gate catches a wrong *approach*, not a wrong
  *detail*); enforce anything (a bypassable exemplar, not a binding gate); compare approaches
  (`awb-research`, first); merge plans or dial checkpoints (`awb-cook`, the heavier sibling);
  drive code test-first (`awb-tdd`); review the finished diff (`awb-review`). It assumes the
  approach is already chosen.

## Process

1. **Scout** — read the code you'll touch and its neighbours; don't propose changes to code you
   haven't read. Stop when you can name every file the change touches and why. If you can't yet
   name the files or approach, this is a *spike*, not a plan-then-code change — build a throwaway
   slice to learn the shape, then run this skill on the real change.
2. **Plan** — what files change, what each does, and the runnable check that will prove it
   worked (a test, a build exit code, an output diff). Keep it to a screen.
3. **GATE: agree the plan before any code.** *With a user:* get an explicit yes — a real gate (a
   person lifts the hold). *Solo:* there is no self-approval in Claude Code, so this is a
   sanity-check pause, not a gate — re-read the plan cold against the Goal and the "decided NOT
   to do" scope for a contradiction. It does not prove the plan correct.
4. **Implement** — make the change; match the surrounding style; no placeholders or "TODO"
   stubs. If Implement shows the plan was wrong (an un-Scouted file, a misfit approach), STOP
   and return to step 3 — a plan that changed under you is an ungated plan.
5. **Test** — add a runnable check that would have caught this change's absence (usually a test;
   for a config/data/content change, a command output or before/after observation). Run it and
   **show the command and its output** — don't assert success. If it fails, fix the code and
   re-run, or return to step 3 if the plan was wrong; never weaken a check to go green.
6. **Review** — grade the diff against the plan (acceptance met, nothing outside the "decided
   NOT to do" scope), then hand it to [`awb-review`](../awb-review/SKILL.md) — or review it
   adversarially yourself — before committing. For a risky plan, run
   [`awb-stress-test`](../awb-stress-test/SKILL.md) before approving at step 3.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "It's obvious, I'll skip the plan" | If it's obvious, the plan takes 60 seconds and confirms it. If not, the plan just saved you. |
| "I'll add tests after it works" | "After it works" rarely arrives. Write the test that proves it works. |
| "The plan gate is bureaucracy" | The gate is the cheapest place to catch a wrong approach — before any code exists. |
| "The plan changed, I'll just keep going" | A changed plan is an ungated plan — stop and re-confirm before more code. |

## Honesty / limits

The plan gate catches a *wrong approach* cheaply; it does **not** prove the plan correct or
complete, and a green suite proves the checks ran, not that the plan was right. Solo, the gate
is a sanity-check pause, not an enforceable approval — only a human lifts a hold. This skill
enforces nothing on its own; for a real gate, some harnesses offer a read-only plan mode (in
Claude Code, plan mode) that blocks edits until you approve — the skill is the workflow, plan
mode is the enforcement, and it works with or without it.

## References

- [`references/plan-template.md`](references/plan-template.md) — a fill-in-the-blanks plan
