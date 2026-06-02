# Sub-agents — focused reviewers you spawn on demand

A **sub-agent** is a named, single-purpose reviewer the main agent launches (via the `Task` tool)
to do one bounded job in its own context, then report back. It is not loaded every session — it
costs nothing until invoked — so it is the right home for a deep, narrow check that would bloat a
skill or a rule if it were always present.

Agent Workbench ships them in [`.claude/agents/`](../.claude/agents/). This page is the convention;
the directory is the registry.

## The shape of an agent file

A `.claude/agents/<name>.md` file is Markdown with YAML frontmatter:

```yaml
---
name: <kebab-name>            # must match the filename
description: <when to invoke> # KEEP IT TIGHT — this loads on every Task() routing decision
model: inherit               # or a specific tier when the job needs it
color: yellow                # optional display hint
---

<the agent's instructions — its mission, process, output format, and tone>
```

Two rules earn their keep:

- **The `description` is the trigger.** It is what the main agent reads to decide whether to spawn
  this sub-agent, so make it say *when to use it* — not just what it is. Keep it short:
  [`tools/check_context_budget.py`](../tools/check_context_budget.py) flags an over-long agent
  description because it is paid on every routing decision. Put the detail in the body, not here.
- **Put detail in the body, behind the spawn.** The body only loads once the agent runs, so the
  step-by-step process, rubric, and output format live there for free.

## What ships

| Agent | Job |
|---|---|
| [`silent-failure-hunter`](../.claude/agents/silent-failure-hunter.md) | Audits a change for silent failures and weak error handling (empty/broad catch, swallowed errors, unjustified fallbacks, unhelpful messages) and reports findings by severity. Adapted from Anthropic's pr-review-toolkit (Apache-2.0). |

## When to reach for an agent vs. a skill

- A **skill** is a playbook the main agent follows *itself*, inline, in the current context.
- A **sub-agent** runs in a *separate* context and hands back a result — use it when the job is
  deep enough that you don't want its working notes in the main thread, or when you want an
  independent pass (a reviewer that didn't write the code).

Keep the set small for the same reason you keep skills small: every agent is one more thing to
maintain and to reason about. Add one when a real, recurring review is worth isolating — not before.
