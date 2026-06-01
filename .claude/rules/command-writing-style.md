# Command Writing Style

Path-scoped rule for files in `.claude/commands/*.md`. Auto-loads when Claude edits a slash command. Pattern adopted from Anthropic claude-plugins-official `plugins/plugin-dev/skills/command-development` (MIT).

**Scope note:** Sections **C1 + C7 are MUST-FOLLOW** (highest ROI). Sections **C2-C6, C8 are optional guidance** — defer until the project scales or you do a large command refactor. Document core rules here to prevent drift; archive advanced patterns to `command-writing-style-advanced.md` only when needed.

---

## C1 — Commands are instructions FOR Claude, not messages TO the user

**The most common mistake when writing a slash command:**

```markdown
{# WRONG — describes the command to the user, does not drive Claude action #}
This command reviews your code for security issues.
You'll receive a report with vulnerability details.

{# CORRECT — directive that Claude executes #}
Review changed files (git diff) for:
- SQL injection patterns (user-controlled input in queries)
- Unescaped template output (XSS)
- Missing CSRF protection on state-changing POST endpoints
- Hardcoded secrets (api_key, token, password)

Output: severity-ranked table, file:line specific.
```

**Self-check:** Read the command as Claude reads it — it must be a **prompt Claude acts on**, not a description for the user.

---

## C2 — Use positional args `$1/$2/$3` for multi-argument commands

Default pattern: `$ARGUMENTS` (all args as a single string). Prefer positional args when the command takes multiple distinct inputs.

**Pattern:**

```markdown
---
description: Debug a file for a specific error pattern
argument-hint: [file-path] [error-keyword]
allowed-tools: [Read, Grep, Bash]
---

Debug errors in @$1.

Search for pattern `$2` in log files:
- App logs: `logs/app.log`
- Background worker logs: `logs/worker.log`

Trace the root cause using the project's debug decision tree.
Spawn a sub-agent if a deep trace is needed.
```

**Usage:**
```
/debug services/payment_service.py NullPointerException
```

**Rules:**
- `$1`, `$2`, `$3`, … for explicit positional arguments
- `$ARGUMENTS` captures the remaining args (e.g. trailing flags like `--force`)
- Document `argument-hint` for autocomplete support

---

## C3 — Inline bash execution `` !`cmd` `` to pre-load context

Instead of letting Claude run `git status` / `git diff` / `find` as tool calls, **pre-load** them in the command body. Speed increases and Claude has richer context before reasoning begins.

**Pattern:**

```markdown
---
description: Review the current working tree
allowed-tools: [Read, Bash(git:*)]
---

## Context

- Current branch: !`git branch --show-current`
- Files changed: !`git diff --name-only HEAD`
- Diff stat: !`git diff --stat HEAD`
- Recent commits: !`git log --oneline -5`

## Task

Review every changed file against the project's review checklist
(see `.claude/skills/review/SKILL.md`).

Output: severity-ranked findings with file:line references.
```

**Rules:**
- `` !`cmd` `` belongs in a context section at the top of the command, NOT inside task descriptions
- `allowed-tools: [Bash(git:*)]` is REQUIRED when using inline bash
- Avoid `` !`long-running-cmd` `` (delays command invocation)
- Avoid `` !`destructive-cmd` `` (e.g. `rm`, `git push`, `DROP TABLE`) — confirm with the user first

---

## C4 — File reference `@path` to auto-include file content

Instead of letting Claude call `Read` as a tool call, **auto-load** file content into the prompt.

**Pattern:**

```markdown
---
description: Review a specific file against the project checklist
argument-hint: [file-path]
allowed-tools: [Read]
---

Review @$1 against the checklist in @.claude/skills/review/SKILL.md.

Output severity-ranked findings filtered to confidence ≥80.
```

**Rules:**
- `@path` resolves relative to the project root
- `@$1` interpolation from a positional arg is supported
- Use multiple `@path1` `@path2` references to compare files
- Use static references (e.g. `@docs/architecture.md`) for commands that always need a reference doc

---

## C5 — `allowed-tools` pre-approval to reduce permission prompts

Every command should specify the tools it needs. Avoid wildcards except in unusual cases.

**Pattern:**

```markdown
---
allowed-tools: [Read, Grep, Glob, Bash(git:*), Bash(pytest:*)]
---
```

**Rules:**
- Name specific tools: `[Read, Write, Edit]`
- Scope bash: `Bash(git:*)`, `Bash(pytest:*)`, `Bash(npm test:*)` — NOT `Bash(*)`
- Do NOT use `["*"]` unless the command genuinely needs every tool
- Avoid `Bash(rm:*)` or `Bash(curl:*)` unless explicitly required

---

## C6 — `disable-model-invocation: true` for user-only commands

Some commands have **side effects** that Claude should not trigger automatically:
- Commit code (`/commit`)
- Push a branch (`/push`)
- Send an external notification
- Run a destructive operation (`/clean`)

**Pattern:**

```markdown
---
description: Create a commit and push
allowed-tools: [Bash(git:*)]
disable-model-invocation: true
---
```

Effect: The slash tool cannot be invoked programmatically by Claude. Only a user typing `/commit` can invoke it.

---

## C7 — Migration path: `commands/*.md` → `skills/<name>/SKILL.md`

Anthropic's guidance: `commands/*.md` is the **legacy format**; prefer `skills/<name>/SKILL.md`. Both load identically; only the layout differs.

**When to migrate:**
- Command has grown to ≥80 lines — migrate to allow splitting body + references/
- Command has multiple stages — migrate to support Mermaid flowcharts + gate blocks
- Command shares knowledge with a model-invoked skill — unify under `skills/`

**When to keep `commands/`:**
- Command is very short (≤30 lines) — migration overhead not justified
- Command is pure user-invoke (no model-invoke) — `commands/` is more concise
- Command has frontmatter `disable-model-invocation: true` — semantically fits `commands/`

**Practical heuristic:** Prioritize migration when a command grows beyond 80 lines.

---

## C8 — Validation patterns

Commands should validate inputs and resources before processing.

**Argument validation:**
```markdown
---
description: Deploy to a target environment
argument-hint: [environment]
allowed-tools: [Bash(echo:*)]
---

Validate env: !`echo "$1" | grep -E "^(dev|staging|prod)$" || echo "INVALID"`

If `$1` is valid: proceed with deployment to $1.
Otherwise: explain valid environments (dev/staging/prod) and show usage.
```

**File existence:**
```markdown
Check file: !`test -f $1 && echo "EXISTS" || echo "MISSING"`

If exists: process @$1.
Otherwise: explain the expected location and format.
```

**Generic resource checks:**
```markdown
- Config file: !`test -f "<project-root>/config.json" && echo "OK" || echo "MISSING"`
- State file:  !`test -f "<project-root>/data/state.json" && echo "OK" || echo "MISSING"`
- Database:    !`test -f "<project-root>/db/app.db"      && echo "OK" || echo "MISSING"`
```

Replace `<project-root>` with your project's actual root path or a parameter.

---

## Self-check checklist (before committing a new command)

- [ ] **C1** Command is written as instructions for Claude, not a message to the user
- [ ] **C2** Multi-argument commands use `$1/$2`, not everything jammed into `$ARGUMENTS`
- [ ] **C3** Inline bash `` !`cmd` `` used for context pre-loading (where appropriate)
- [ ] **C4** `@path` file references used instead of letting Claude call Read manually
- [ ] **C5** `allowed-tools` is specific — no wildcard `*`
- [ ] **C6** `disable-model-invocation: true` set for commands with side effects
- [ ] **C7** Consider migrating to `skills/` format if the command is ≥80 lines
- [ ] **C8** Input and resource validation in place before processing

---

## References

- Anthropic command-development skill: `plugins/plugin-dev/skills/command-development/SKILL.md` in [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) (MIT)
- Agent writing guidance: `.claude/agents/*.md` ("When to invoke" structure per `agent-development` guidance)
- Skill writing: `.claude/skills/*/SKILL.md` (prefer `skills/` over `commands/` for new workflows)
