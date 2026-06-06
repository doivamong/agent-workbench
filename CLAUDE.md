# CLAUDE.md

> Project instructions for Claude Code (and, via `AGENTS.md`, other AI coding agents).
> This file is loaded into context every session, so keep it **short and high-signal** —
> link out to detail instead of inlining it. The notes in *italics* explain *why* each
> section earns its place; delete them when you adapt this for your own project.

## What this project is

**Agent Workbench** — a kit of tools + methodology for running an AI coding agent safely and
consistently on a long-lived codebase. It is the generic layer distilled from a private
codebase, shared so whoever needs it skips avoidable mistakes. **Why it exists and how it must
behave is canonical in [PHILOSOPHY.md](PHILOSOPHY.md).** The reusable core is stdlib-only.
See [README](README.md).

*Lead with one or two sentences. The agent should know what it's working on before any rule.*

## Golden rules (the few that must never break)

1. **No secrets, identifiers, or absolute machine paths** in committed files. The leak scanner
   gates this (`python tools/leak_scan.py . --entropy --fail-on-find --respect-gitignore`) — but a
   green scan is **not proof**. It misses a brand identifier used as a code namespace (a CSS class
   prefix like `acme-`, a `--brand-*` token), paid-product references, and example paths. When
   committing ported or branded content, grep the source's own namespace yourself first.
2. **The reusable core stays stdlib-only** (`scripts/`, `tools/`, `.claude/hooks/`). Dependencies
   live in `examples/` and tests.
3. **Every tool ships a runnable `examples/` entry** and has tests.
4. **Best-fit, honest about limits, not gospel** — every tool states what it does *not* do. The
   four tenets are canonical in [PHILOSOPHY.md](PHILOSOPHY.md); this kit is one developer's context.

*Keep this list to ~5 items. If everything is a golden rule, nothing is. Put the rest in
path-scoped rule files (see `.claude/rules/`).*

## How to work here

- **Plan before non-trivial changes**, then implement, then test, then review. The example
  skills in `.claude/skills/` encode this.
- **Verify against ground truth, don't trust framing** — run the demo/tests and read the output;
  check the load-bearing claim against the source. A framing you didn't author (a tool/skill's
  description, an external audit) is just an unchecked claim — right on the facts ≠ right on cause /
  severity / fix.
- **In a linked worktree, sync before you build** — agent worktrees drift behind `origin/main`
  while parallel sessions merge PRs. Before implementing a fix, `git fetch` and check
  `git rev-list --left-right --count origin/main...HEAD` plus whether your target files already
  changed upstream; fast-forward/rebase first, and if a merged PR already did the work, switch to
  review instead of re-doing it. (Verify the work isn't already done — not just that a claim is true.)
- **One session per working tree.** Never run two agent/Claude sessions on the same checkout — they
  race the git index and switch HEAD under each other (silently sweeping uncommitted work into the
  wrong commit, or mis-basing a new branch). Give each concurrent session its own `git worktree`
  (commit via `pre-commit run --all-files` and audit `git config --local --list` after — committing
  from a linked worktree can leak an absolute `GIT_DIR` and corrupt the shared `.git/config`), or a
  separate clone for full isolation.
- **When a safety hook blocks an action, relay it in plain language** — tell the user what was
  stopped and why, and offer a safe next step; never suggest re-running it outside the guard (to
  them or to yourself). A hook's deny reason is shown to the agent, not directly to the user.
- **Match the surrounding code's style** rather than importing your own conventions.

## Project map

| Area | Path |
|------|------|
| Safety hooks (+ how they're wired) | [`.claude/hooks/`](.claude/hooks/), [`.claude/settings.json`](.claude/settings.json) |
| Reusable tools | [`tools/`](tools/), [`scripts/`](scripts/) |
| Repo-operation tools (stdlib, not installed) | [`ops/`](ops/) — dashboard control, LAN/autostart setup, release pack, tree snapshot |
| Skill system | [`.claude/skills/README.md`](.claude/skills/README.md) |
| Memory system | [`memory/README.md`](memory/README.md) |
| Tests | [`tests/`](tests/) |

## Commit conventions

- Conventional-commit style summary (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Imperative mood, explain *why* in the body when it isn't obvious.
- Do **not** add AI-assistant co-author trailers.

---

*Adapt this file: replace the project description, golden rules, and map with your own. The
shape — short always-loaded core + links to detail — is what keeps an agent consistent over
months without paying a huge context cost every session.*
