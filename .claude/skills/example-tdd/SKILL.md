---
name: example-tdd
description: >
  WHAT: drive a change test-first as red-green-refactor in VERTICAL slices — one failing test,
  the minimal code to pass it, repeat — so each test is shaped by what the last one taught you.
  USE WHEN: building a feature or fixing a bug where the behavior is non-trivial and you want
  tests to lead ("do this TDD", "test-first", "red-green-refactor", "write the test first",
  "regression test before the fix").
  DO NOT TRIGGER: a trivial change (under ~30 lines, behavior obvious); a pure config/data edit
  with no logic; a spike/exploration where you want feedback before committing to an interface;
  reviewing code already written (that is a review skill).
tier: workflow
oversight: low
---

# Example: Test-Driven Development (vertical slice)

> **Announce on activation:** "Using example-tdd — red-green-refactor in vertical slices."

## Scope

- **Does:** turn a behavior list into a sequence of `failing test → minimal implementation` cycles,
  one behavior at a time, through the public interface.
- **Does NOT:** prove correctness (a green suite only proves what its assertions check), choose
  *which* behaviors matter, or run your test infrastructure. It is a discipline, not a test runner.

## Slice vertically, not horizontally

Writing *all* the tests then *all* the code ("horizontal") breeds tests that assert the *shape* you
imagined, not the behavior a user sees — they pass when behavior breaks. Instead take one thin slice
end-to-end at a time, so each test responds to what the previous cycle taught you:

```
horizontal (wrong):  test1 test2 test3  →  impl1 impl2 impl3
vertical   (right):  test1→impl1  test2→impl2  test3→impl3
```

## Process

1. **List behaviors, not steps.** Name the observable behaviors, pick the few that matter, confirm
   them. You cannot test everything — choose.
2. **Tracer bullet.** Write ONE test for the first behavior, watch it fail for the right reason
   (RED), then write the minimal code to pass it (GREEN). This proves the path is wired end to end.
3. **HARD GATE: prove the test actually runs.** A test file the runner doesn't recognize collects
   **zero** tests and still exits **green** — it looks like a passing cycle but asserts nothing.
   After creating any test file, confirm `pytest path --collect-only` lists ≥ 1 item. Don't trust a
   "passed" you never saw turn red. (For pytest: `test_*.py` / `*_test.py`, functions `test_*`.)
4. **Incremental loop.** One test → fail → minimal code → pass, for each remaining behavior. No
   speculative features.
5. **Refactor on green only.** Clean up once the slice passes, running tests after each step. Never
   refactor while RED.

## Test behavior, not implementation

A good test exercises the **public interface** and reads like a spec ("a valid cart checks out"); it
survives an internal rename. A bad test mocks your own collaborators or reaches for private methods,
so it breaks on refactors that changed nothing a caller sees. **Mock only at real boundaries**
(network, clock, randomness) — never the thing you're testing.

## Honesty / limits

Passing tests prove only what their assertions check — never that the code is correct or complete.
TDD shapes *design* and catches *regressions*; it is not verification. The vertical-slice /
tracer-bullet framing is re-authored from the "tdd" skill in
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT) — see
[`THIRD_PARTY_NOTICES.md`](../../../THIRD_PARTY_NOTICES.md).
