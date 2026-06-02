---
name: example-dead-code-audit
description: >
  WHAT: find genuinely unused code with a false-positive gate — a symbol is reported "dead" only
  when several INDEPENDENT cross-checks all come back empty, never on one finder's say-so.
  USE WHEN: an on-request cleanup sweep ("find dead / unused code", "what can we delete", a
  post-refactor or pre-release prune, "is this function called anywhere?").
  DO NOT TRIGGER: "this function is too long / too complex" (a structural-size concern, not
  deadness); hunting for bugs (a review/debug skill); deleting code the user already named as dead.
tier: audit
oversight: high
---

# Example: Dead-code audit (false-positive gated)

> **Announce on activation:** "Using example-dead-code-audit — cross-checking before calling anything dead."

Finding candidates is easy; the hard part is not being **wrong**, because a confidently-wrong "this
is dead" deletes something reached dynamically and breaks production.

## Scope

- **Does:** propose deletion candidates, try hard to *disprove* each one's deadness, and present
  only the survivors — with evidence — for a human to delete.
- **Does NOT:** auto-delete anything (ever), judge code quality/length, or claim certainty. Static
  reachability is undecidable under dynamic dispatch; this is a high-confidence filter, not a proof.

## Why one finder isn't enough

A symbol can be reached with no literal call site: dynamic dispatch (`getattr`, a handler registry,
plugin discovery), string/declarative references (templates, config, serialization, route/ORM
decorators, CLI entry points), an external/public-API surface, or framework hooks (fixtures, signal
handlers). A grep that finds zero call sites found zero *literal* ones — not zero *uses*.

## Process

1. **Gather candidates** from the language's unused-symbol finder (or grep). This is the input, not
   the answer.
2. **HARD GATE: a candidate is "dead" only when ALL of these are empty** —
   - the symbol name across the whole repo (incl. tests, scripts, docs);
   - the name as a **string** (dynamic dispatch / templates / config / serialization);
   - **entry points & registries** (CLI, routes, plugins, decorators, `__all__`, settings);
   - the **external surface** (exported? part of a public API or webhook?).
   If any check is non-empty, it is **not** dead — drop it and say why.
3. **Report, don't delete.** Present survivors with the four empty checks as evidence; the human
   decides. Deletion is a separate, reviewed step.
4. **Delete in small, reversible batches** (if asked) — one logical group per commit, suite green
   after each, so a wrong call is easy to bisect and revert.

## Honesty / limits

Reachability under dynamic dispatch is undecidable in general — this **reduces** false positives, it
does not eliminate them, and it never deletes. Absence of evidence (no grep hits) is not evidence of
absence (no uses); a linter sees literal references only, so templates, `getattr`, registries, and
external callers are invisible to it.
