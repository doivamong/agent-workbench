---
name: awb-using-skills
description: >
  WHAT: the meta-routing protocol — how to choose the right skill (and notice when one
  applies at all) so the agent routes consistently instead of guessing.
  USE WHEN: auto-injected every session by the skill_routing_inject.py SessionStart hook;
  also read it directly whenever two or more skills could match a request, or you are
  unsure whether any skill applies.
  DO NOT TRIGGER: as a destination — it never does the work itself, it only routes TO
  other skills. To change what fires, edit skill-registry.md, not this file.
tier: meta
oversight: high
---

# Using skills — the routing protocol

> **Announce on activation:** "Using awb-using-skills to route this to the right skill."

This is the one always-on skill. It does not implement anything; it decides **which** skill
should run. The actual trigger → skill map is **not** here — it lives in
[`skill-registry.md`](../skill-registry.md), the single source of truth, and the SessionStart hook
injects a compact copy at the top of every session. This file is the *method* for reading it.

## The mandate

**If there is even a ~1% chance a skill applies, invoke it.** Routing is cheap; a missed guard
is not. A one-second skill invocation is more reliable than your memory of what the skill says.

After invoking: announce `"Using <skill> to <purpose>."` If the skill is a checklist, track each
item (e.g. a TODO per step) and finish them in order.

## Priority — who wins when guidance conflicts

```
1. The user's direct instruction (this chat, CLAUDE.md / AGENTS.md)   ← highest
2. A matching skill (the registry + this protocol)
3. Claude Code default behavior                                       ← lowest
```

## When several skills match — resolve in this order

1. **Tier precedence: Workflow > Guard > Feature > Audit.** A workflow skill orchestrates
   guards *inside* it, so if the user wants the full process, the workflow wins — and it may run
   a guard within itself (both active is normal, not a conflict).
2. **Match on the OBJECT, not the verb.** Verbs ("fix", "optimize", "review", "check") are shared
   by every skill and disambiguate nothing. The *thing* being acted on decides:
   - object = the UI / a screen → the UI skill (even if the verb is "fix" or "optimize")
   - object = a code change / dead code → the audit skill (even if the verb is "review")
   - object = an approach / a plan → the research skill (even if the verb is "design")
3. **A domain-specific rule beats a general one** when the two disagree.
4. **Still ambiguous? Ask** — a one-line question beats guessing wrong (e.g. lightweight save vs.
   an executable handover bundle are different skills with different output shapes).

## Anti-rationalization — none of these excuses a skipped skill

| You'll think | Reality |
|---|---|
| "Simple task, probably doesn't need it" | The recurring violations come *from* the tasks that felt simple. |
| "I already remember the rules" | Remembering ≠ applying them correctly right now. One second to invoke is surer. |
| "It's only a one-line change" | A single import can cross an architectural boundary. Size doesn't gate the check. |
| "Tests pass, so it's fine" | Tests don't cover the silent failure the guard exists to catch. |
| "The skill's DO NOT TRIGGER says skip" | That's a hint, not a guarantee — this protocol is the final arbiter for edge cases. |

## Honest limit

This is a **routing nudge, not a router** — a model-invoked, bypassable skill (see
[`docs/guard-mechanisms.md`](../../../docs/guard-mechanisms.md)). It does **not** guarantee the
agent picks correctly, and it does **not** itself enforce, lint, or run anything. The injected map
is only as good as `skill-registry.md`: if a row is missing or stale, the route is wrong — fix the
registry, which the `skill_lint.py` gate keeps in sync with the skill folders.

**Deferred (recorded, not built).** A per-prompt skill-recommend `UserPromptSubmit` hook — a
"recommend a skill to the user every turn" mechanism — was weighed and deferred: a hook only
injects text, so it cannot *force* a model-driven route; it stacks noise on the
`prompt-refiner-inject.py` nudge; and before Scout it cannot know a change's blast radius. Revisit
**only on a recorded incident** — a real session where a clearly-applicable skill failed to
*auto*-fire, traced to weak description signal (never surfaced as a candidate, not "invoked but
mis-chosen", which a nudge cannot fix). `skill_usage_logger.py` **cannot** back this trigger: it
reads only the user's prompt, never the model's auto-route; the only real instrument would be a
`PostToolUse` hook on the `Skill` tool, deliberately not added. A before/after **routing eval** is
deferred for the same reason — a stdlib-only version scores token overlap, not the model's semantic
routing, and would *mis*-score a retune that moved descriptions toward natural language — so a
description edit ships as a stated, unfalsifiable-by-current-tooling hypothesis (the description is
the primary model-driven trigger).
