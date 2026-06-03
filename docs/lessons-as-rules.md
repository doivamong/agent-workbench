# Lessons as rules — turning a mistake into a guardrail

A lesson you learn the hard way is worth as much as a tool — but only if it's captured somewhere the
agent actually reads at the moment it matters. This is the shape Agent Workbench uses for that, and
the discipline that keeps the set from rotting into noise.

(Why lessons rank equal to tools is one of the four tenets — see [`PHILOSOPHY.md`](../PHILOSOPHY.md);
this page is the *how*, not the *why*.)

## Where a lesson lives

| Form | Lives in | Loads | Good for |
|---|---|---|---|
| **Memory fact** | `memory/` (one file) | via the `MEMORY.md` index, on recall | a one-off insight, not yet proven to recur |
| **Path-scoped rule** | `.claude/rules/*.md` | automatically when you edit a file its `paths:` glob matches | a recurring trap tied to a specific kind of file |
| **Core rule** | `CLAUDE.md` / `AGENTS.md` | every session | the handful that must never break |

A lesson should sit at the **narrowest scope that still fires when needed** — pushing everything into
the always-loaded core is how `CLAUDE.md` bloats. The shipped
[`command-writing-style.md`](../.claude/rules/command-writing-style.md) and
[`measurement-honesty.md`](../.claude/rules/measurement-honesty.md) are working examples of
path-scoped rules.

## The shape of a rule

Keep each rule short and operational — it should change what the agent *does*, not lecture. A useful
shape:

- **Pattern** — the trap, named in one line (so it's greppable).
- **Why** — the cost of getting it wrong (the reason the rule exists).
- **Unsafe vs safe** — a tiny contrast: the wrong way next to the right way.
- **Self-check** — the one question to ask before you commit code in this area.
- **Bypass** — when it's legitimately OK to ignore the rule, and the requirement to *say so* when you do.

## Promotion: from memory to rule

A lesson earns promotion when it stops being a one-off. Don't restate the thresholds here — the
promotion model (how many recurrences, over how many sessions) is defined once in
[`memory-governance.md` §4](memory-governance.md). Promotion is a deliberate human call, not an
automatic one (see the honest lessons in that same doc for why auto-promotion was abandoned).

## Before you capture a lesson — dare to report zero

The cull pass below trims rules that already exist. There's a matching discipline at the *other*
end — when you mine a just-finished session for what's worth keeping:

- **Default to zero.** Most sessions produce no durable lesson, and "none this time" is an honest,
  correct answer. A retro that always finds "three key learnings" is manufacturing them to look
  productive — and that noise is exactly what buries the rare lesson that mattered.
- **Capture only what clears the same gate** (non-obvious · reusable · not-a-cliché). If a candidate
  fails it, it isn't a lesson — let it go.
- **Severity rescue.** One exception to "reusable": a trap that's borderline on recurrence but
  **catastrophic when it does recur** (data loss, a security hole, a silent corruption) is worth a
  rule on a single sighting — the cost of meeting it twice dwarfs the cost of one rule. Score on
  value *and* severity, not value alone.

The [`awb-lessons-capture`](../.claude/skills/awb-lessons-capture/SKILL.md) skill is the
organ that runs this capture discipline end to end — the report-zero gate, the value score, the
dedup pass against the existing corpus, and a hard write-gate before anything reaches memory.

## Keeping the set honest (the anti-bloat pass)

A rules folder accretes. Periodically — not every session — review it and score each rule on three
questions:

- **Non-obvious?** Would a competent engineer plausibly get this wrong without the rule? (If it's
  obvious, it's noise.)
- **Reusable?** Does it apply beyond the one incident that spawned it?
- **Not a cliché?** Is it specific to how *this* code fails, not generic advice?

Keep the ones that pass; **cull** the obvious/one-off ones; **merge** rules that overlap. A rule that
no longer earns its load cost should be deleted without ceremony — the same gate that governs adding
one governs keeping it.

## Honest limit

This is a convention, not an enforcer: nothing here checks that a rule's `paths:` glob is correct or
that the agent actually applied it. It organizes lessons so they load at the right moment — it can't
make a badly-written lesson useful, and it can't catch a trap nobody wrote a rule for yet.
