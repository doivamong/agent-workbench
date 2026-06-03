---
description: When you defer a capability or touch a memory tool — gate the defer, and reuse don't re-derive. Loaded when editing the memory governance doc, a memory tool, or a skill.
paths:
  - "docs/memory-governance.md"
  - "tools/memory_*.py"
  - ".claude/skills/**"
---

# Defer discipline — a defer needs a trigger, a tool needs to reuse

Two silent failure modes this rule guards. A capability "deferred" with no falsifiable trigger is just
a capability *forgotten* — the condition fires (or never does) in private and nobody acts. And a new
memory tool that re-declares the load budget, re-writes the frontmatter parser, or re-derives the
per-project path drifts from its siblings the first time one side changes (the budget constant already
drifted `24576` -> `25600` once, before it was centralised). The fix for both is mechanical, below.
(The *why* is the kit's honesty + DRY tenets — see [`PHILOSOPHY.md`](../../PHILOSOPHY.md) and the §7
register in [`docs/memory-governance.md`](../../docs/memory-governance.md).)

## Deferring a capability? Run the 4-question gate

1. **Defer or reject?** Can you name a *concrete, falsifiable* condition under which you would build
   it? If not, it is a **reject** (write down why), not a defer — "maybe someday" is not a trigger.
2. **Measurable or incident trigger?** *Measurable* = a read-only check can detect it (index over
   budget, near-duplicate facts, ≥ 5 memory tools). *Incident* = you only notice it in the moment (a
   recall-miss, a new third-party mutator). The kind decides how it self-surfaces.
3. **Recorded in the right home?** Add a row to the **§7 register** in `docs/memory-governance.md` —
   committed and greppable, *never* only in a handover or your memory (a defer that lives only in a
   handover silently dies). One row: Capability / Why (+ alternative) / Trigger / Self-surface / Date.
4. **Self-surface wired?** A *measurable* trigger must point at a read-only WARN that names the remedy
   and §7 (e.g. the audit byte-gate and near-duplicate WARNs). An *incident* trigger self-surfaces
   through the register (and this rule) — it is recorded, not detected. Never auto-*act* on a trigger:
   surfacing is read-only; building the capability is a human call (governance §5/§6).

## Adding or editing a memory tool? Reuse, don't re-derive

There is one source for each shared concern — import it, never re-declare it:

- **The load budget** (`INDEX_MAX_BYTES` / `INDEX_MAX_LINES`) -> `from memory_budget import ...`.
- **The frontmatter parser** -> `memory_audit.parse_frontmatter` (the kit's no-YAML parser).
- **The live per-project dir** (the cwd-mangling) -> `memory_recall_doctor.resolve_live_dir` /
  `mangle_cwd` — never hand-roll the `~/.claude/projects/<id>/memory` path.

Duplicating a constant, a parser, or the path-mangling is the drift this rule exists to stop. And
before you add the tool: a 5th `tools/memory_*.py` is itself the trigger to revisit the `tools/memory/`
package row in §7 — surface that, do not silently grow the flat directory.

## Honest limit

This is a convention, not an enforcer. Nothing here blocks a trigger-less defer or a re-declared
constant; it only sets the question to ask at the moment you edit these files. The committed §7
register and the audit WARNs are the parts that actually persist — this rule points you at them.
