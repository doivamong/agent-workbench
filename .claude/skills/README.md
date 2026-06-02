# The Skill System

A **skill** is a folder of instructions Claude Code loads *on demand* when a task
matches it. Think of it as a reusable, model-invoked playbook: instead of re-typing
"plan before you code, then test, then review" every session, you encode it once as a
skill and let the agent trigger it by intent.

This folder is a **generic, domain-free template** of the skill system one solo developer
evolved over months. The example skills here are re-authored from first principles — copy
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
| **Workflow** | Full multi-step processes that orchestrate other skills | `example-plan-then-code` |
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
| [`example-plan-then-code/SKILL.md`](example-plan-then-code/SKILL.md) | A **workflow** skill: plan → implement → test → review |
| [`prompt-refiner/SKILL.md`](prompt-refiner/SKILL.md) | A **workflow** skill: sharpen a vague request before work starts (wired to the prompt hook) |
| [`example-review/SKILL.md`](example-review/SKILL.md) | A **guard** skill: three-pass review with progressive disclosure |
| [`example-debug/SKILL.md`](example-debug/SKILL.md) | A **guard** skill: reproduce → find root cause → fix → prove |
