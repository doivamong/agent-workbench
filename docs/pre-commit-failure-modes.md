# A pre-commit gate that learns — the failure-modes registry

Agent Workbench ships commit-time seatbelts (the [`leak_scan`](../tools/leak_scan.py) tripwire and
the [`secrets_guard`](../scripts/secrets_guard.py) pre-commit hook). A fixed gate catches the
failures you *anticipated*. This is the pattern for the ones you didn't: a small **append-only
registry** of things that have slipped through, so the gate gets smarter instead of staying static.

## The registry

One table, appended to — never trimmed — each time something reaches a commit that shouldn't have.
Each row records the *class* of failure, not the one incident:

| Failure mode | How it slipped | The check that would catch it | Tier |
|---|---|---|---|
| absolute machine path committed | not in the deny-list | `leak_scan` deny-list entry | **blocking** |
| debug `print` left in a library | no rule fired | `invariants` `no-print-in-lib` | advisory |
| a TODO with no owner | reviewer missed it | `invariants` `todo-needs-owner` | advisory |

Appending a row is the cheap, durable response to "how did *that* get in?" — it converts a one-off
mistake into a check the next person doesn't have to remember.

## Advisory vs blocking — tier every check

Not every check should stop a commit. Mixing the two trains people to ignore the gate.

- **Blocking** — correctness, security, or a leak: a committed secret, a destructive command, a
  broken invariant. These **fail the commit**. Keep the blocking set small and unambiguous so a red
  gate always means "really stop".
- **Advisory** — style, nits, soft nudges: a long function, a missing owner, a simplify hint. These
  **warn and let the commit through**. They inform; they don't gate.

A check earns the blocking tier only when a false positive is rarer and cheaper than a false
negative. When in doubt, ship it advisory and promote it later if it proves precise.

## Honest limit

A registry is a memory aid, not enforcement — a row only helps once someone wires the corresponding
check (a deny-list entry, an `invariants` rule, a hook). It records *what* keeps slipping and *how
hard* to gate it; turning that into an actual blocker is a deliberate step, and over-blocking is its
own failure mode (a gate people route around protects nothing).
