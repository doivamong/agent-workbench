# The Skill System

A **skill** is a folder of instructions Claude Code loads *on demand* when a task
matches it. Think of it as a reusable, model-invoked playbook: instead of re-typing
"plan before you code, then test, then review" every session, you encode it once as a
skill and let the agent trigger it by intent.

This folder is a **generic, domain-free template** of the skill system one solo developer
evolved over months. The skills here are re-authored from first principles — copy
their *shape*, not their content, and fill in your own.

## Why skills beat ad-hoc prompting

- **Consistency** — the same task always runs the same way, even months apart.
- **Progressive disclosure** — `SKILL.md` stays short; heavy detail lives in `references/`
  and is only read when needed, so you don't pay the context cost up front.
- **Intent-triggered** — you describe *when* a skill applies; the agent matches it
  automatically. No need to remember a command name.
- **Composable** — a high-level "workflow" skill can orchestrate smaller "guard" skills.

## Anatomy of a skill

```
.claude/skills/
└── my-skill/
    ├── SKILL.md            # the playbook (keep it tight — the agent always reads this)
    └── references/         # optional deep-dive files, read only when the skill needs them
        └── checklist.md
```

### `SKILL.md` frontmatter

```yaml
---
name: my-skill
description: >
  One paragraph that does double duty. State WHAT the skill does, then:
  USE WHEN: the concrete triggers (phrases, task types) that should fire it.
  DO NOT TRIGGER: the near-misses that should NOT fire it (this is what stops
  skills from stepping on each other).
---
```

The `description` is the **single most important field** — it's what the agent matches
against. A vague description means the skill never fires (or fires at the wrong time). Be
specific about both the triggers and the anti-triggers.

#### Writing a description that triggers right

- **Anchor on the OBJECT, not the verb.** Verbs ("help", "improve", "check") are shared by every
  skill and disambiguate nothing; the *thing* the user is acting on ("a failing test", "a PR diff",
  "the memory index") is what tells skills apart. Lead with the object.
- **Keep it tight.** Aim for roughly 30–80 words. If you need far more just to list triggers, the
  skill is probably doing several jobs — split it. An over-long description also costs context on
  every match ([`tools/check_context_budget.py`](../../tools/check_context_budget.py) flags it).

| ❌ Vague (won't fire, or fires everywhere) | ✅ Specific (fires at the right time) |
|---|---|
| `Helps with code review.` | `Review a code change / PR / diff in passes. USE WHEN the user says "review my changes / this PR". DO NOT TRIGGER for a broad whole-repo audit.` |
| `Improves the codebase.` | `Cut duplication and dead code in files just edited. USE WHEN asked to clean up / simplify a change. DO NOT TRIGGER to hunt for bugs (that's a review skill).` |

### Body conventions that work

- Lead with a one-line **announce** the agent says when it activates ("Using my-skill to …").
- If the skill is a process, make it a **numbered, checkable** list so the agent can track it.
- Mark any non-negotiable step as a **HARD GATE** (a step that must pass before continuing).
- Push examples and long checklists into `references/` — keep `SKILL.md` scannable.

## Organizing many skills: tiers

Once you have more than a handful, group them by role so conflicts resolve predictably.
One workable hierarchy (highest priority first):

| Tier | Role | Example |
|------|------|---------|
| **Workflow** | Full multi-step processes that orchestrate other skills | `awb-plan-then-code` |
| **Guard** | Mandatory, narrow checks that must not be bypassed | a config-access guard |
| **Feature** | Context-specific helpers | a UI-style guide |
| **Audit** | On-request deep inspections | a dead-code audit |

Conflict rule that scales: **Workflow > Guard > Feature > Audit**, and a domain-specific
rule beats a general workflow rule when they disagree. Write the rule down once (see
[`skill-registry.md`](skill-registry.md)) so future-you isn't guessing.

## Skills vs. commands

Both are markdown the agent can load. The practical split:

- **Command** (`.claude/commands/x.md`) — short, usually *you* invoke it by typing `/x`.
- **Skill** (`.claude/skills/x/SKILL.md`) — richer, the *model* invokes it by matching intent,
  and it can split across multiple files.

When a command grows past ~80 lines or needs sub-files, migrate it to a skill.

## What's here

| File | Purpose |
|------|---------|
| [`SKILL_TEMPLATE.md`](SKILL_TEMPLATE.md) | Blank, annotated skill to copy |
| [`skill-registry.md`](skill-registry.md) | A machine-greppable index of all skills (single source of truth for triggers) |
| [`awb-plan-then-code/SKILL.md`](awb-plan-then-code/SKILL.md) | A **workflow** skill: plan → implement → test → review |
| [`awb-research/SKILL.md`](awb-research/SKILL.md) | A **workflow** skill: understand → compare ≥2 approaches → recommend, before building |
| [`prompt-refiner/SKILL.md`](prompt-refiner/SKILL.md) | A **workflow** skill: sharpen a vague request before work starts (wired to the prompt hook) |
| [`awb-review/SKILL.md`](awb-review/SKILL.md) | A **guard** skill: three-pass review with progressive disclosure |
| [`awb-debug/SKILL.md`](awb-debug/SKILL.md) | A **guard** skill: reproduce → find root cause → fix → prove |
| [`awb-stress-test/SKILL.md`](awb-stress-test/SKILL.md) | A **workflow** skill: pressure-test a change through fixed lenses before building — design verdict + edge-case list |
| [`awb-output-guard/SKILL.md`](awb-output-guard/SKILL.md) | A **guard** skill: keep long/whole-file generation complete — no truncation or placeholders |
| [`awb-using-skills/SKILL.md`](awb-using-skills/SKILL.md) | A **meta** skill: the routing protocol — pick the right skill when several match (auto-injected each session by [`skill_routing_inject.py`](../hooks/scripts/skill_routing_inject.py)) |
| [`awb-handover/SKILL.md`](awb-handover/SKILL.md) | A **workflow** skill: package settled work into a handover a cold reader can execute |
| [`awb-tdd/SKILL.md`](awb-tdd/SKILL.md) | A **workflow** skill: red-green-refactor in vertical slices — one failing test → minimal code → repeat |
| [`awb-cook/SKILL.md`](awb-cook/SKILL.md) | A **workflow** skill: advanced build — graduated oversight + multi-perspective planning, orchestrating the guards |
| [`awb-external-ref/SKILL.md`](awb-external-ref/SKILL.md) | A **workflow** skill: reuse outside code responsibly — license decision + injection / supply-chain checks |
| [`awb-lessons-capture/SKILL.md`](awb-lessons-capture/SKILL.md) | A **workflow** skill: mine a finished session for durable lessons, write only the approved ones to live memory |
| [`awb-config-guard/SKILL.md`](awb-config-guard/SKILL.md) | A **guard** skill: catch the two silent config-access traps (wrong context; nested key → silent `None`) |
| [`awb-optimize/SKILL.md`](awb-optimize/SKILL.md) | A **feature** skill: baseline → measure → fix the top bottleneck → re-measure → before/after table |
| [`awb-dead-code-audit/SKILL.md`](awb-dead-code-audit/SKILL.md) | An **audit** skill: find genuinely dead code behind a false-positive gate — never auto-deletes |
