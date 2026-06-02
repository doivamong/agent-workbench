<!--
  Injected into context at the start of every session by .claude/hooks/scripts/session_start.py.
  Keep it SHORT — it is paid for in every session's context budget. Edit freely, or delete the
  file to inject nothing. Put always-true rules in CLAUDE.md instead; use this for pointers.
-->
This project ships **skills** (reusable playbooks). Before doing non-trivial work, check whether
one applies: skim [`.claude/skills/skill-registry.md`](.claude/skills/skill-registry.md) and match
the task against each skill's `USE WHEN` / `DO NOT TRIGGER` markers. Reach for a skill rather than
improvising the same workflow from scratch.
