---
name: my-skill
description: >
  WHAT: one sentence on what this skill does.
  USE WHEN: list the concrete triggers — task types, phrases the user might say,
  file patterns. Be generous; this is what makes the skill fire.
  DO NOT TRIGGER: list the near-misses that belong to a *different* skill, so this
  one doesn't steal their work. This half is what keeps a skill library sane.
# Optional fields you may add and grep on later:
# tier: workflow | guard | feature | audit
# oversight: how much human confirmation the skill demands (low | high)
---

# My Skill

> **Announce on activation:** "Using my-skill to <purpose>."

## When this applies

A sentence or two restating the trigger in your own words, so the agent re-confirms
it picked the right skill before doing anything.

## Scope

State plainly what this skill **does** — and, just as explicitly, what it does **not**
do and hands off to. (This is different from the `DO NOT TRIGGER` line above: that one
keeps the skill from *firing* on the wrong request; this one stops it from *over-reaching*
once it's already running.) A named boundary is what stops a skill from quietly growing
into a do-everything blob.

- **Does:** the one job, stated concretely.
- **Does NOT:** the adjacent things it must refuse or delegate (and to what).

## Process

1. **Step one** — what to do, what "done" looks like.
2. **Step two** — …
3. **HARD GATE: <name>** — a step that MUST pass before continuing. Say what blocks
   and what unblocks it.
4. **Final step** — …

## Anti-rationalization (optional but powerful)

A short table of "the excuse you'll tell yourself" vs "why it's wrong", for the steps
people skip under time pressure. This is what makes a skill survive contact with a
deadline.

| You'll think | Reality |
|---|---|
| "This case is too small to plan" | Planning a small change costs 30s; mis-implementing it costs 30min. |

## References (progressive disclosure)

Link heavy detail here instead of inlining it:

- [`references/checklist.md`](references/checklist.md) — the full checklist
- [`references/examples.md`](references/examples.md) — worked examples
