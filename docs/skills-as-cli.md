# Blueprint: running skills outside Claude Code

> **Status: BLUEPRINT, not a shipped framework.** This page is a pattern plus one
> ~30-line reference example ([`examples/skill_as_cli_demo.py`](../examples/skill_as_cli_demo.py)).
> It is deliberately *not* a multi-tool runner — building that for your stack is the
> exercise. See [`PHILOSOPHY.md`](../PHILOSOPHY.md): the *Liberation* tenet wants the
> methodology portable, but not bloated into a feature nobody asked for.

## Why

A skill (`.claude/skills/<name>/SKILL.md`) is just **frontmatter + a Markdown playbook**.
Nothing about the playbook is Claude-Code-specific — the value is the encoded decision
("plan before a multi-file change", "review in three passes"). So the same methodology can
run in Cursor, Copilot, Continue, or a raw API call: hand the model the playbook as context.

This breaks the implicit vendor lock-in: your hard-won skills are not trapped in one tool.

## The seam

There are exactly two steps, and the example shows both:

1. **Strip the frontmatter** — everything between the leading `---` fences is routing
   metadata (name, description, tier) for the host agent's trigger logic; the body below is
   the actual instructions.
2. **Emit the body as context** — print it, pipe it, or send it as a system/developer
   message to whatever agent you're driving.

```bash
# print one skill's playbook
python examples/skill_as_cli_demo.py example-review

# pipe it into another CLI agent as a system prompt (illustrative)
python examples/skill_as_cli_demo.py example-debug | your-agent --system -
```

## What you'd add for your stack (left as the exercise)

- **Trigger parity:** the host hook decides *when* a skill fires; outside Claude Code you
  pick the skill yourself (by name) or port the trigger logic from `skill-registry.md`.
- **Reference resolution:** a skill may link `references/*.md`; a real runner would inline
  them. The demo does not — it prints one file.
- **Tooling:** Claude Code skills assume tools like Read/Edit/Bash. Another agent needs its
  own equivalents wired up.

## What this does NOT do

It does **not** make skills run identically everywhere, and it is **not** a supported
cross-tool runtime. It shows the one transferable thing — the playbook — and where the seam
is. The trigger logic, reference inlining, and tool bindings are host-specific and yours to
build. Keep [`skill_lint.py`](../tools/skill_lint.py) honest about the registry either way.
