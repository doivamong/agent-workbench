# The Memory System

A file-based, human-readable memory for a long-running Claude Code project. The goal:
let the agent carry forward hard-won facts — your preferences, decisions, gotchas — across
sessions, **without** stuffing everything into context every time.

This is a generic scaffold. The example memory files are made-up; replace them with yours.
The companion design doc is [`../docs/memory-governance.md`](../docs/memory-governance.md).

## The core idea: an index gates recall

```
memory/
├── MEMORY.md                 # the INDEX — small, always loaded into context
├── feedback_*.md             # one fact per file — loaded ON DEMAND
├── project_*.md
└── user_*.md
```

- **`MEMORY.md`** holds one short pointer line per memory. The harness auto-loads it every session
  **from the per-project path** (`~/.claude/projects/<id>/memory/`, *not* this repo's `memory/` —
  see [`../docs/memory-governance.md`](../docs/memory-governance.md)), reading the first 200 lines /
  ~25 KB, so it must stay small (a couple hundred lines at most).
- **Each fact lives in its own file.** Those are read *only when relevant* — recall is gated
  by the index. To "forget" something from active recall, you remove its line from
  `MEMORY.md`; the file can stay on disk as cold storage.

This index-gating is what keeps memory cheap: you pay for the index always, and for a fact
only when you reach for it.

## One fact per file

Each memory file is a single, self-contained fact with frontmatter:

```markdown
---
name: feedback-validate-at-boundary
description: One line — used to judge relevance during recall.
metadata:
  type: feedback        # user | feedback | project | reference
---

The fact itself. For `feedback` and `project`, follow it with:

**Why:** the reason this matters (so future-you trusts it).
**How to apply:** the concrete action to take next time.

Link related memories with [[their-name]].
```

The `[[their-name]]` links are a **convention**, not a feature — your recall step resolves them
when it pulls related memories together; nothing auto-follows them on disk.

## The four types

| Type | Holds | Example |
|------|-------|---------|
| `user` | Who the developer is — role, preferences, working style | "prefers small commits; reviews on mobile" |
| `feedback` | Guidance on *how to work* — corrections and confirmed approaches | "validate input at the boundary, not in every layer" |
| `project` | Ongoing goals/constraints not derivable from the code or git history | "migrating off the legacy queue by Q3" |
| `reference` | Pointers to external resources (URLs, dashboards, tickets) | "perf dashboard: <url>" |

## What's worth saving (and what isn't)

**Save** the non-obvious: a preference you'd otherwise re-learn, a decision and its *why*, a
trap that bit you once. **Don't save** what the repo already records — code structure, past
fixes, git history. If a fact only matters to today's conversation, it's not memory.

## Hygiene

- Before adding, check for an existing file that already covers it — update rather than
  duplicate.
- Delete memories that turn out to be wrong. A confidently-wrong memory is worse than none.
- A recalled memory reflects what was true *when written* — if it names a file or flag,
  verify it still exists before acting on it.

See [`../docs/memory-governance.md`](../docs/memory-governance.md) for the fuller model:
layering, promotion of a repeatedly-useful memory into a always-on rule, and supersession.
