---
name: example-stress-test
description: >
  WHAT: pressure-test a non-trivial change before you build it — run it past a fixed set
  of independent lenses so blind spots surface on paper, not in production. Two modes:
  design stress-test (expert viewpoints judge whether the approach is sound, returning a
  GO / CAUTION / STOP verdict) and edge-case decomposition (failure-axis lenses enumerate
  what could break, producing a severity-ranked list that feeds tests).
  USE WHEN: about to implement or test something non-trivial and you want the risks and
  edge cases first ("stress test this", "what could go wrong", "edge cases", "is this
  design sound", "second opinion before I build", "poke holes in this plan").
  DO NOT TRIGGER: a one-line / low-risk change; choosing between approaches (that is a
  research skill); reviewing code already written (that is a review skill); a known bug
  with a clear cause (that is a debug skill).
tier: workflow
oversight: high
---

# Stress-test a change before you build it

> **Announce on activation:** "Using example-stress-test — I'll run this past fixed lenses to surface risks and edge cases before any code."

The cheap-to-fix mistakes are the ones a single pass over your own plan never sees: you read
the design the way you intended it, so the blind spot stays blind. This skill imposes a *fixed
set of independent lenses* — the same checklist every time — so the same gaps get caught every
time, on paper, before they cost a rebuild or a production incident. It runs **before** code
exists; it does not review code already written.

## Scope

- **Does:** pressure-test a *proposed* change through fixed lenses — either to judge whether
  the design is sound (mode A) or to enumerate how it could break (mode B) — and synthesize the
  result into a decision or a test list.
- **Does NOT:** compare alternative approaches (that is a research skill — this assumes the
  approach is already chosen), review or refactor written code (that is a review skill), or
  diagnose a bug that already happened (that is a debug skill). It surfaces candidates; it does
  not prove them — evidence does that (see *Honest limit*).

## Pick the mode

| Mode | Question | Lenses | Output |
|---|---|---|---|
| **A — Design stress-test** | "Is this approach sound enough to build?" | expert viewpoints | a GO / CAUTION / STOP verdict + the conflicts behind it |
| **B — Edge-case decomposition** | "What could break once it's built?" | failure axes | a severity-ranked scenario list that feeds tests |

They share one spine and you can run both: A decides *whether* to build, B decides *what to
test*. A "CAUTION" from A is a natural cue to run B on the risky part.

## The shared spine (both modes)

1. **Pick the lenses that apply — don't force all of them.** Mark which lenses are relevant to
   *this* change; **skip the rest with a one-line reason**. A lens applied to something it can't
   touch is noise; a lens skipped silently is a hidden gap.
2. **Run each lens independently first.** Analyse through one lens without letting the others'
   conclusions anchor it. Independence is the whole point — it's what makes a *second* viewpoint
   worth more than re-reading your own.
3. **Then synthesize** — agreements, conflicts, and what the evidence still has to settle.
4. **Be explicit about coverage.** State which lenses you ran and which you skipped and why, so
   the reader knows the shape of what was and wasn't examined.

---

## Mode A — Design stress-test (viewpoint lenses)

Each lens is an independent expert asking its own core question. Adapt the set to your stack;
this is a generic starting point, not a fixed law.

| Lens | Core question |
|---|---|
| **Architecture** | Does it fit the existing structure? New coupling or a wrong-way dependency? Will it hold at the expected growth? Can it be undone? |
| **Security & safety** | Where's the trust boundary? What's the untrusted input? Is authorization checked at the right edge? Could it expose data or mishandle a secret? |
| **Performance & resources** | What's the hot path? Any N+1 / quadratic blow-up, unbounded memory, or chatty I/O? Is any caching or concurrency *correct*, not just present? |
| **Operability & UX** | When it fails, is the failure visible and recoverable? Are error states clear? Can an operator observe it? Is the interface understandable? |
| **Skeptic (devil's advocate)** | What load-bearing assumption could be false? Is there a markedly simpler way? Is this even needed yet (YAGNI)? |

**Process:** run the five lenses independently → list the points most lenses **agree** on →
list the **conflicts** (lenses that pull opposite ways) and the trade-off each forces → reach a
verdict.

| Verdict | Meaning | Action |
|---|---|---|
| **GO** | Lenses aligned, no critical unmitigated risk | Proceed to plan/implement |
| **CAUTION** | Real concerns, but each has an identified mitigation | Proceed carefully, following the mitigations; consider mode B on the risky part |
| **STOP** | A critical issue with no workaround in the current design | Stop and rework or escalate to the user |

**Any one of these forces STOP:** an unmitigated security hole; a design incompatibility that
needs a rework no local change fixes; a load-bearing assumption shown to be false. A STOP is a
*save*, not a failure — it's the rebuild you didn't pay for.

---

## Mode B — Edge-case decomposition (failure-axis lenses)

Decompose the feature across orthogonal failure axes. Not every axis applies — filter first,
and **skip with a reason**. For each relevant axis, generate a few *concrete* scenarios (not
"handle bad input" but "input is empty / 10× the max size / wrong encoding").

| Axis | What to probe |
|---|---|
| **Inputs** | empty / null, maximum size, malformed, unexpected encoding, injection, boundary values |
| **Identity & permission** | anonymous vs authenticated, expired or insufficient permission, privilege boundaries |
| **Timing & concurrency** | simultaneous operations, races, stale reads, retries, timeouts, ordering |
| **Scale & volume** | growth over time, large payloads, pagination edges, resource limits |
| **State & lifecycle** | transitions, partial or aborted operations, idempotency, resume after failure |
| **Failure & recovery** | a dependency is down or slow, partial failure mid-operation, resource exhaustion, rollback |
| **Environment** | other platforms / locales, offline, caching layers, configuration differences |
| **Integrity** | duplicates, orphans, normalization, double-counting, invariants that must always hold |

**Process:** filter axes → for each kept axis generate 3–5 concrete scenarios → classify each
by severity → emit the table → feed the **Critical / High** rows straight into tests.

| Severity | Meaning |
|---|---|
| **Critical** | data loss, security or authorization bypass, silent corruption |
| **High** | broken for a subset of users, real data inconsistency |
| **Medium** | poor UX, a recoverable error shown badly, stale data |
| **Low** | cosmetic, non-blocking, wrong format but right data |

```
## Edge-case report: [target]
Axes analysed: [...]    Axes skipped: [... + reason]

| # | Axis | Scenario | Severity | Expected behaviour |
|---|------|----------|----------|--------------------|

Summary: Critical N · High N · Medium N · Low N
```

---

## Honest limit

A fixed lens-set is a **checklist against *known* blind spots — not a proof of completeness.**
An unknown-unknown appears on no list, and the lenses produce *hypotheses*, not verdicts: a
performance worry is settled by a measurement, an edge case by a test, a design doubt by a small
prototype — not by the analysis itself. Treat the lens-sets here as a starting point you extend
for your own system, and never let a clean stress-test substitute for running the code.

## Banned behaviours

- Letting the first lens's conclusion colour the rest — analyse each independently, then merge.
- "All five lenses checked" with no skipped-with-reason line — silent full coverage is rarely honest.
- Vague scenarios ("handle errors") instead of concrete, testable ones.
- A GO verdict that never names a single conflict or risk — that's a rubber stamp, not a stress-test.
- Treating the output as proof rather than a list of things to *go verify*.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I designed it, I already know the risks" | You know the risks you designed *around*. The fixed lenses exist to catch the ones you designed *past*. |
| "Running every lens is overkill here" | Then filter and say which you skipped and why — that's the skill working, not a reason to skip it. |
| "It passed the stress-test, so it's safe" | It surfaced no *known* blind spot. Safety is what the tests and measurements show after, not the analysis before. |
| "Edge cases can wait until something breaks" | The Critical rows are the breakages — enumerating them now is cheaper than triaging them in production. |
