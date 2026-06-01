# Session Context Preservation

> **Purpose:** Keep decisions, rationale, progress, and next steps intact when switching accounts, hitting quota limits, or starting a fresh session.

---

## Overview

Working with Claude Code exposes context to loss in three common scenarios:

| Scenario | Cause | Consequence |
|:---------|:------|:------------|
| **Account switch** (quota exhausted) | Old session cannot resume under a new account | Entire conversation history lost |
| **Context window full** | Auto-compact summarises the conversation, losing nuance | Claude "forgets" prior decisions, repeats work |
| **New session** | Fresh session = blank context | Must re-explain everything from scratch |

### Three-layer system

```
┌──────────────────────────────────────────────────────┐
│  Layer 3: /catchup command (Smart Restore)           │
│  ├── quick   → git diff + log (~5 s)                 │
│  ├── restore → + HANDOVER + checkpoint (~15 s)        │
│  └── full    → + transcript parse (~30-60 s)          │
├──────────────────────────────────────────────────────┤
│  Layer 2: /session-save command (Structured Backup)  │
│  └── Creates HANDOVER.md with decisions, WHY,        │
│      next steps                                      │
├──────────────────────────────────────────────────────┤
│  Layer 1: PreCompact Hook (Safety Net — automatic)   │
│  └── Auto-backs up transcript before every compact   │
└──────────────────────────────────────────────────────┘
```

---

## Usage

### 1. Save a session (`/session-save`)

**When to use:**
- Before switching accounts (quota exhausted)
- Before ending a complex session (many decisions, many files changed)
- When Claude reminds you to save context

**How to use:**

```
/session-save                         # Save full context
/session-save refactoring pipeline    # Save with a specific note
```

**Claude will automatically:**
1. Collect git diff, log, plan files, and to-do list
2. Synthesise a HANDOVER file (12 sections)
3. Save it to `.claude/handovers/HANDOVER_{timestamp}.md`
4. Clean up old files (keep at most 5)
5. Display a summary for review

**Example output:**

```
Session saved: HANDOVER_20260405_1030.md
   - 3 decisions, 5 next steps
   - Files changed: 4
   Restore with: /catchup restore
```

### 2. Restore a session (`/catchup`)

**Three restore tiers:**

| Tier | Command | What it reads | Time | When to use |
|:-----|:--------|:--------------|:-----|:------------|
| **Quick** | `/catchup` | Git diff + log | ~5 s | Short break, same account |
| **Standard** | `/catchup restore` | + HANDOVER + checkpoint + memory | ~15 s | Account switch, new session |
| **Full** | `/catchup full` | + Parse transcript JSONL | ~30-60 s | Need maximum detail |

**Typical workflow:**

```
Old session:  /session-save → switch account
New session:  /catchup restore → Claude has context → continue work
```

**Auto-detect:** When a new session starts and a HANDOVER less than 24 hours old is found, Claude will prompt:

```
Handover found: HANDOVER_20260405_1030.md (45 minutes ago)
   — run /catchup restore to resume context
```

### 3. End a session (`/wrap-up`)

`/wrap-up` automatically calls `/session-save` before summarising — ensuring context is always saved.

### 4. Automatic safety net (PreCompact hook)

When the context window fills and Claude auto-compacts, the system **automatically**:
1. Backs up the transcript JSONL before compacting
2. Writes a signal file for post-compact recovery
3. After compact, injects a HANDOVER excerpt (Goal + Decisions + Next Steps)

**No action needed** — this is a background safety net.

---

## HANDOVER Format

A HANDOVER file contains 12 sections (each optional — skip if no data):

```markdown
# Session Handover — YYYY-MM-DD HH:MM

## Goal
Main objective of the session

## Completed
- Work finished, with specific file paths

## In Progress
- Work underway, current state

## Key Decisions (with WHY)
- Decision: Specific reason

## Failed Approaches (DO NOT retry)
- Approach tried: Why it failed (so the next session does NOT repeat it)

## Active Plan
Plan file name or plan summary

## Active Tasks
Current to-do list

## Open Questions
- Unresolved questions

## Next Steps (priority order)
1. Most concrete next step (next session starts here)
2. Step 2

## Files Changed (uncommitted)
git diff --stat output

## Context for Next Session
Plan file paths, config changes, branch state, test status...
```

---

## Comparison

### `/session-save` vs `/checkpoint`

| Criterion | `/session-save` | `/checkpoint` |
|:----------|:----------------|:--------------|
| **Purpose** | Handover to a different account/session | Quick state snapshot |
| **Content** | 12 sections: decisions, WHY, failed approaches, next steps | 5 sections: completed, state, questions, next steps |
| **Stored at** | `.claude/handovers/HANDOVER_*.md` | `.claude/checkpoints/*.md` |
| **Auto-detect** | New session prompts `/catchup restore` | Manual read only |
| **Post-compact inject** | Excerpt injected automatically | No |
| **When to use** | Account switch, end of complex session | Mid-session, before risky operations |

**Recommendation:** Use `/session-save` when switching accounts. Use `/checkpoint` for quick mid-session snapshots.

### Three restore tiers

| Criterion | Quick | Standard | Full |
|:----------|:------|:---------|:-----|
| **Context accuracy** | ~30% | ~85% | ~95% |
| **Speed** | ~5 s | ~15 s | 30-60 s |
| **Needs HANDOVER** | No | Yes | Yes |
| **Needs transcript** | No | No | Yes (backup) |
| **When to use** | Short break | Account switch | Debugging old session |

---

## Benefits

1. **Preserves WHY, not just WHAT** — decisions carry rationale; the next session understands the reasoning
2. **Failed approaches recorded** — the next session avoids repeating mistakes, saving time
3. **Automatic safety net** — the PreCompact hook runs silently; nothing to remember
4. **Tiered restore** — choose the appropriate depth; no need to read everything every time
5. **Auto-detect** — new sessions are reminded to restore if a recent HANDOVER exists
6. **Integrated with `/wrap-up`** — no need to call separately
7. **Zero external dependencies** — Python stdlib only
8. **Context tracker nudges** — prompts you to save at 150 tool calls, before it is too late

## Limitations

1. **Requires the user to remember `/session-save`** — if quota runs out unexpectedly without saving, only the PreCompact safety net (transcript backup, not structured) is available
2. **HANDOVER quality depends on context quality** — if context was already heavily compacted, Claude produces a less accurate HANDOVER. Save early while context is still clear (< 65% used)
3. **150-line cap** — very complex sessions may have details trimmed
4. **Local only** — HANDOVERs are stored on the local machine and do not sync automatically. If working across machines, commit or copy the HANDOVER file manually
5. **Transcript parse (Full tier) takes time** — large JSONL files take 30-60 s
6. **Cannot replace the full conversation** — a handover is a summary, not a replay; some fine-grained nuance may be lost

## Risk Register

| Risk | Likelihood | Severity | Mitigation |
|:-----|:-----------|:---------|:-----------|
| Forgot to save before account switch | Medium | Medium | Context tracker nudges at 150 tools + PreCompact safety net |
| HANDOVER contains sensitive information | Low | Low | Gitignored; skill definition prohibits including secrets |
| Concurrent sessions overwrite HANDOVER | Low | Low | Filenames include timestamp — no collision |
| Hook crash | Very low | Low | Graceful degradation — session continues normally |
| Encoding error on Windows | Low | Low | All hooks use `encoding='utf-8'` |
| HANDOVER too old (> 24 h) | Medium | Low | Auto-detect warns; falls back to git diff |

---

## Technical Architecture

### File layout

```
.claude/
├── handovers/                           # Gitignored
│   ├── .gitkeep
│   ├── HANDOVER_20260405_1030.md        # Structured handover
│   ├── transcript_auto_20260405.jsonl   # Transcript backup
│   └── .last_compact                    # Signal file (JSON)
├── hooks/
│   ├── pre-compact-backup.py            # PreCompact hook
│   ├── compact-restore.py              # SessionStart[compact] hook
│   └── lib/
│       └── handover_utils.py           # Shared utilities
├── skills/
│   └── session-save/
│       └── SKILL.md                    # Session-save skill definition
├── commands/
│   ├── session-save.md                 # /session-save command
│   └── catchup.md                      # /catchup command
└── settings.json                        # Hook registrations
```

### Hook pipeline

```
Working normally
    │
    ├── [PostToolUse] context-tracker.py
    │   └── 150 tools → prompt "/session-save"
    │
    ├── [User] /session-save
    │   └── Claude creates HANDOVER_*.md
    │
    ├── [Auto] context fills → PreCompact fires
    │   └── pre-compact-backup.py
    │       ├── Copy transcript JSONL
    │       └── Write .last_compact signal
    │
    ├── [Auto] compact done → SessionStart[compact] fires
    │   └── compact-restore.py
    │       └── Inject HANDOVER excerpt (~50 lines)
    │
    └── [User] New session → SessionStart fires
        └── session_start.py
            └── Detect HANDOVER → prompt "/catchup restore"
```

### Hooks registered in `settings.json`

| Hook | Matcher | Script | Timeout |
|:-----|:--------|:-------|:--------|
| PreCompact | (none) | `pre-compact-backup.py` | 15 s |
| SessionStart | (none) | `session-start.py` | 10 s |
| SessionStart | `compact` | `compact-restore.py` | 10 s |
| PostToolUse | `Bash\|Edit\|Write\|...` | `context-tracker.py` | 10 s |

---

## Best Practices

### Daily workflow

```
1. Start of day  → new session → /catchup restore (if HANDOVER exists)
2. Work normally
3. Context tracker nudges at 150 tools → /session-save (if nearing quota)
4. Switch account → new session → /catchup restore
5. End of day → /wrap-up (calls /session-save automatically)
```

### When context is healthy (< 50% used)

- Saving is not urgent — but if you know quota is running low, save early
- HANDOVER quality is best when context is still clear

### When context is high (> 65% used)

- **Save immediately** if there are important uncommitted decisions
- After 65%, quality begins to degrade (Stanford "Lost in the Middle" research)
- PreCompact fires around ~80% — treat it as a safety net, not a primary solution

### When you forgot to save

- The PreCompact hook already backed up the transcript automatically
- Use `/catchup full` to parse the transcript backup
- Quality is lower than `/session-save` but better than starting from scratch

---

## FAQ

**Q: Does `/session-save` run automatically?**
A: No. You must call it manually. However, `/wrap-up` calls it automatically, and the context tracker nudges at 150 tool calls.

**Q: Are HANDOVER files tracked in git?**
A: No. They are added to `.gitignore`. Transcript backups are also gitignored.

**Q: Can I use this on another machine?**
A: HANDOVERs are stored locally. To use on another machine, copy `.claude/handovers/HANDOVER_*.md` manually or commit it temporarily.

**Q: What if the PreCompact hook crashes?**
A: The session continues normally. A hook crash causes graceful degradation — it does not affect the workflow.

**Q: How does this differ from long-term memory (MEMORY.md)?**
A: Long-term memory stores durable insights across sessions. A HANDOVER stores session-specific state (short-lived). The two systems complement each other; neither replaces the other.

**Q: How long are HANDOVERs kept?**
A: Auto-cleanup retains the 5 most recent files. `/catchup restore` only reads HANDOVERs less than 24 hours old.

---

*Design references: VNX Context Rotation pattern, Two-File System pattern, Session Lifecycle Hooks pattern, Claude Code official hooks documentation.*
