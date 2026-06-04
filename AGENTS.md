# AGENTS.md

> Tool-agnostic instructions for AI coding agents (Cursor, Copilot, Codex, Aider, …).
> `AGENTS.md` is an emerging cross-tool convention; Claude Code users also have
> [`CLAUDE.md`](CLAUDE.md), which carries the same rules. Keep the two in sync — or make one
> a thin pointer to the other so you don't maintain rules twice.

## TL;DR for an agent landing here

This repository is **Agent Workbench** — tools + methodology for driving an AI coding agent
safely on a long-lived codebase. Before you change anything:

1. Read [`CLAUDE.md`](CLAUDE.md) — the golden rules and project map live there.
2. Run the checks below to confirm a green baseline.
3. Don't commit secrets, identifiers, or absolute machine paths (the leak scanner enforces this).

## Checks an agent should run

```bash
python -m pytest -q                          # tests must pass
python tools/leak_scan.py . --entropy --fail-on-find --respect-gitignore   # zero leaks (+ high-entropy sweep; skips git-ignored files, as CI does)
python tools/invariants.py .                 # zero new errors
```

## Conventions

- **Reusable core (`scripts/`, `tools/`, `.claude/hooks/`) is stdlib-only.** Put dependencies in
  `examples/` and tests.
- **Every tool needs a runnable example and tests.** "Readable but unrunnable" is the failure
  mode this kit fights.
- **Plan → implement → test → review** for non-trivial changes.
- **Best-fit, honest about limits, not gospel.** Every tool states what it does *not* do. The
  kit's four tenets are canonical in [PHILOSOPHY.md](PHILOSOPHY.md) — read it before changing a
  tool's behavior or the project's voice; it is the kit's reason for existing, not a style note.
- **No AI co-author trailers** in commits.

## Why have both AGENTS.md and CLAUDE.md?

Different tools look for different files. Rather than pick a side, this repo keeps a single
source of rules in `CLAUDE.md` and uses this file as the tool-agnostic entry point that points
to it. When you adapt this for your own project, decide which file is canonical and make the
other defer to it.
