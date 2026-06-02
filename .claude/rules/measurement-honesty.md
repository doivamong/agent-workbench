---
description: Don't trust a measurement until you've checked what it actually covered. Loaded when editing a checker / measurement tool.
paths:
  - "tools/**"
---

# Measurement honesty — a green check is not a gate

A passing test, a "0 results" grep, a "98% coverage" — each is a *claim produced by a measurement*,
and a measurement is only as good as what it actually looked at. The expensive mistakes here are not
wrong code; they are **false confidence**: a number or a green tick everyone trusts and nobody
verified. This rule names the four ways it recurs. (The *why* is the kit's honesty tenet — see
[`PHILOSOPHY.md`](../../PHILOSOPHY.md); this is the operational *how*. It is one instance of the
[lessons-as-rules](../../docs/lessons-as-rules.md) discipline.)

## The four false-confidence traps

**1. n=1 false-zero — concluding "none" from one sample.**
"No other callers" after a single grep; "0 drift" from checking one record. Absence in a *narrow*
look is not absence. Measure broadly (several diverse samples, the whole set when you can); if you
genuinely cannot, write **"not measured"** — never round an un-measured thing down to "0" or "low".

**2. Coverage blindness — a green checker that scanned the wrong things.**
A guard exits 0 because it *ran*, not because it *covered the case you care about*. A linter green on
the files it sees says nothing about the file it skipped. Before trusting a green check, verify its
**coverage** — which inputs / files / branches it actually exercised, and what it silently skipped. A
check that cannot fail is decoration; make it go red once on purpose to prove it bites.

**3. Selection-biased percentage — a stat measured on a rigged sample.**
"80% of X do Y", computed over items chosen *because* they do Y, is circular. Before quoting or
propagating a "%", check the **denominator**: was the sample drawn independently of the property being
measured, or selected by it? Re-measure on a representative set, or don't quote the number.

**4. Manual run ≠ the real gate.**
`python tool.py somefile` exiting 0 does not prove the pre-commit hook or CI will pass — the gate
often runs with different inputs (staged vs working-tree, the whole repo vs one file) and different
args. To claim "the hook passes", run the **actual gate** (`pre-commit run`, the CI command, a real
commit), not a bare invocation you reason about.

The thread through all four: **distinguish "I measured and didn't find it" from "it isn't there."**
Only the first is earned by a measurement; the second usually is not.

## Self-check (before you write a number, or a "clean" / "none" claim)

- Is a "0 / none / low" backed by a broad measurement, or one sample? (one sample → write "not measured")
- Trusting a green checker → did you verify what it covers, and watch it fail at least once?
- Quoting a "%" → did you check the denominator and whether the sample is biased toward the property?
- Claiming "the hook / CI passes" → did you run the real gate, not a bare script?
- New detector you just wrote → did you sanity-check its first output against an independent read?

## Bypass

A full measurement sometimes costs more than the decision is worth (spinning up an environment, a
whole-repo scan). When you skip it, *say so*: state the scope you measured and the scope you deferred,
and give the conclusion a confidence (high / medium / low) instead of a bare "0%". Don't let the
bypass become the default — an undocumented shortcut reads exactly like an un-checked claim.

## Honest limit

This is a convention, not an enforcer. Nothing here checks that you measured broadly or ran the real
gate; it sets the default question to ask so you catch the false-confidence trap yourself — it is not
a tool that catches it for you.
