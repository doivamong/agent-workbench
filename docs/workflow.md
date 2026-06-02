# Workflow — which skills to chain for which task

The [skills README](../.claude/skills/README.md) says *what each skill is* and how they're tiered.
This page is the other half: given a **kind of task**, what to run and in what order — and what the
hooks fire on their own without you asking. It's a routing map, not a rulebook; the tier and
precedence rules are defined once in that README and are linked, not repeated, below.

## What fires on its own

These run automatically — you don't invoke them. They're the ambient layer the chains assume:

| Event | Hook | What it does |
|---|---|---|
| At session start (not after a compaction) | [`session_start.py`](../.claude/hooks/scripts/session_start.py) | Injects the project primer (`.claude/session-primer.md`) so the skill system is in context from turn one |
| You submit a vague prompt | [`prompt-refiner-inject.py`](../.claude/hooks/prompt-refiner-inject.py) | Nudges you to sharpen the request first (see the `prompt-refiner` skill) |
| Before a `Bash` command | [`block_dangerous.py`](../.claude/hooks/scripts/block_dangerous.py) | Blocks obviously destructive shell commands (a seatbelt, not a security boundary) |
| After a burst of `Edit`/`Write` | [`post_edit_simplify.py`](../.claude/hooks/scripts/post_edit_simplify.py) | Reminds you to run a simplify pass |
| After each `Edit`/`Write` | [`context_tracker.py`](../.claude/hooks/scripts/context_tracker.py) | Nudges when the session context is getting heavy |
| Before a context compaction | [`precompact_backup.py`](../.claude/hooks/scripts/precompact_backup.py) | Backs up the transcript |
| After a compaction | [`compact_restore.py`](../.claude/hooks/scripts/compact_restore.py) | Re-injects the latest handover excerpt so work resumes |

All hooks are fail-open (a crash logs and exits clean — a guardrail must never halt the agent).

## Chains by task type

| When the task is… | Run, in order | Notes |
|---|---|---|
| **A non-trivial change** (feature, multi-file edit) | (`prompt-refiner` if the ask is vague) → [`example-research`](../.claude/skills/example-research/SKILL.md) *if the approach isn't obvious* → [`example-plan-then-code`](../.claude/skills/example-plan-then-code/SKILL.md) → [`example-review`](../.claude/skills/example-review/SKILL.md) before committing | The plan skill already folds in plan → implement → test → review |
| **A bug with an unknown cause** | [`example-debug`](../.claude/skills/example-debug/SKILL.md) (reproduce → root cause → fix → prove) | Don't skip to the fix; the gate below is "root cause first" |
| **Reviewing a change already written** | [`example-review`](../.claude/skills/example-review/SKILL.md) (spec → quality → adversarial) | Use before committing anything non-trivial |
| **Choosing between approaches** | [`example-research`](../.claude/skills/example-research/SKILL.md) → write the decision + why | Feeds the plan skill if you then build it |
| **A one-line fix with a known cause** | Just make it | No skill needed — but the gates and the auto-firing guards still apply |

## Blocking gates (don't skip)

These are enforced inside the skills above; collected here so the whole-flow view is in one place:

1. **Plan before implementation** — agree the approach before writing the change.
2. **Root cause before fix** — diagnose, don't guess-patch (see [`development-rules.md`](development-rules.md): *verify with evidence*).
3. **Tests green, with evidence** — run them and read the output; a claim isn't a result.
4. **Leak / dangerous-command guards** — clear the [leak scanner](../tools/leak_scan.py) and the command guard before a commit lands.

## When several skills could fire

Precedence (**Workflow > Guard > Feature > Audit**) and "a domain-specific rule beats a general
workflow rule" are defined once in the [skills README](../.claude/skills/README.md#organizing-many-skills-tiers)
and [`development-rules.md`](development-rules.md). This page defers to them — it routes tasks, it
doesn't re-rank skills.

For work you hand to a sub-agent rather than do inline, see [`orchestration.md`](orchestration.md).

## Honest limit

Skills are intent-triggered *nudges*, not rails — nothing forces a chain to run, and a skill fires
only if its description matches what you asked. The hooks are fail-open seatbelts, not guarantees.
This map shows the path that usually pays off; picking it on a given task is still a judgement call.
