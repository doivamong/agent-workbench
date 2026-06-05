# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses lightweight
[SemVer](https://semver.org/)-style tags. Because the kit is consumed by **copying files**
into a target repo (see `install.py`), a "release" is a reference point for what changed
since you copied — not a published package.

## [Unreleased]

### Added
- **Hook** `post_edit_simplify.py` (`PostToolUse`, Edit/Write): after a burst of edits, injects
  a one-line nudge to do a simplification pass. Advisory only (never blocks), fail-open,
  throttled by a cooldown and a session TTL; threshold/state/on-off are env-configurable. Wired
  into the example `settings.json` and the installer snippet. The injected text carries only the
  file *count*, not paths, so a crafted filename has no route into the agent's context.

- **Canonical `PHILOSOPHY.md`** (repo root): the kit's four tenets plus a "what would betray
  this" review checklist, single-sourced. README/CLAUDE/AGENTS/CONTRIBUTING/SECURITY now quote
  one line and link to it instead of restating. Guarded by `tests/test_philosophy_anchor.py`
  (a de-duplication drift-guard — distinctive tenet sentences must live only in the canon) and
  by a philosophy check folded into the `awb-review` skill's Stage 1.

- **Memory tooling suite** (`tools/memory_*.py`, stdlib): `memory_audit` (hygiene tripwire),
  `memory_snapshot` (manual snapshot/restore of the out-of-git memory store), `memory_recall_doctor`
  (read-only check that curated memory actually reaches the agent's per-project load path),
  `memory_budget` (the single source of truth for the `MEMORY.md` ≤200-line / ~25 KB load budget,
  imported by the others), `memory_sync` (fail-closed publish of a public-safe slice), and
  `memory_eval` (a stdlib retrieval benchmark over a hand-labeled gold set — measures recall
  *quality*, recall@k / precision@k / MRR; advisory, not a gate). The reference model is
  `docs/memory-governance.md` (§7 register tracks deferred memory capabilities and their triggers).

- **Repo gates & analysis tools** (`tools/`, stdlib): `skill_lint` (registry ↔ `SKILL.md` drift),
  `sync_manifest` (file-set drift gate), `readme_metrics` (the gated count source for "At a glance"),
  `check_context_budget` (per-session load auditor), `check_requirements_diff` (new-dependency
  tripwire), and `license_scan` (license/attribution marker scan). Wired into the pre-commit / CI gate.

- **More fail-open hooks**: `context_tracker` (PostToolUse, long-session `/compact` nudge),
  `precompact_backup` (PreCompact) + `compact_restore` (SessionStart-compact) for context recovery,
  `skill_routing_inject` + `session_start` + `session_end` (SessionStart / SessionEnd orientation),
  the opt-in `skill_usage_logger` (UserPromptSubmit, not wired by default), and the maintainer-only
  `sync_guard` (PostToolUse, not wired by the installer).

- **`ops/` toolkit** (repo-operation, stdlib, *not* installed into adopter projects):
  `dashboard_ctl` (start/stop/restart/status for the opt-in dashboard), `tree_snapshot`
  (gitignore-respecting working-tree snapshot/restore, dry-run by default), `release_pack`
  (sha256-manifest verifiable release zip — integrity, not authenticity), `lan_setup`
  (default-to-LAN bind + firewall helper) and `autostart` (start-at-logon via a Windows
  Scheduled Task / POSIX systemd user service), plus Windows `ops/win/*.bat` launchers.

- **Opt-in `ui/` dashboards** (the kit's only runtime dependency, isolated from the stdlib core):
  a stdlib `ui/kit_status` offline HTML report, and a Flask `ui/web` dashboard (mobile-first,
  vendored Chart.js + htmx, no CDN) that visualizes the kit's own state over the *same* single
  data source.

- **`/admin` web action surface** on `ui/web` — **always mounted, login is the gate**. Password auth
  (pbkdf2-sha256 hash in `.ops/admin.hash`, repeated-failure lockout, CSRF token, `SameSite=Strict`
  session cookie), a redesigned login page + in-place change-password panel, and an offline
  `set_password` CLI (stdlib-only — also the forgotten-password recovery path). With no password
  configured `/admin` is inert (every action 403s on any host). The old `--admin` flag is now a
  deprecated no-op; `--debug` is refused outright.

### Changed
- **Docs overhaul.** Corrected stale counts (demos, tools, skill tiers, hook list). Added a
  "why it's public" manifesto to the README. Reframed `docs/memory-governance.md` and
  `docs/session-preservation.md` as reference **blueprints** — the governance tooling and the
  session commands they describe are designs you implement, not features shipped in this repo.
- **Skill system expanded and renamed.** The example skill set grew to cover all five tiers
  (workflow / guard / feature / audit / meta), and the `example-*` skills were renamed to the
  `awb-*` prefix (`prompt-refiner` keeps its bare name — a paired `UserPromptSubmit` hook references
  it). The README "At a glance" row is the gated source of truth for the live skill count.

## [0.1.0] — 2026-06-02

First tagged reference point. The reusable core is stdlib-only; `pytest` is the only
dependency, and only for the tests/examples.

### Added
- **Agent configuration**: drop-in `CLAUDE.md` / `AGENTS.md` templates.
- **Skill system**: registry, tiers, and four runnable example skills
  (`example-plan-then-code`, `example-review`, `example-debug`, `prompt-refiner`) plus a
  `SKILL_TEMPLATE.md`.
- **Memory scaffold**: file-based, index-gated cross-session memory under `memory/`.
- **Guardrail hooks**: `block_dangerous.py` (PreToolUse) and `prompt-refiner-inject.py`
  (UserPromptSubmit), wrapped fail-open by `hook_logger`.
- **Tools**: `invariants.py`, `affected_tests.py`, `leak_scan.py`, and `secrets_guard.py`.
- **Installer** (`install.py`): copies the kit into a target project (`--dry-run`,
  `--force`, `--with-git-hook`).
- **CI** (matrix Python 3.10/3.11/3.12), pre-commit config, runnable demos, and docs
  (`docs/getting-started.md`, `docs/SECURITY.md`, `docs/memory-governance.md`,
  `docs/session-preservation.md`, `docs/SANITIZATION.md`).

### Security / hardening
- `block_dangerous.py`: whitespace/flag-order/case-tolerant matching; covers `rm -rf`
  variants, `find -delete`, `dd`, `mkfs`, recursive `chmod 777`, fork bombs, force-push,
  `git reset --hard`, file truncation (`truncate -s 0`, content-less `> file`) and SQL
  `DROP`/`TRUNCATE`/`DELETE`-without-`WHERE`. **Fails closed** on an unparseable payload.
- `leak_scan.py`: opt-in `--entropy` sweep (wired into every committed gate); inline
  `# leak-scan: ignore` can no longer silence high-confidence secrets (AWS / private key /
  Slack / Telegram) without a **named** opt-out.
- `secrets_guard.py`: encrypt-then-MAC with constant-time verification, unique per-encryption
  salt/nonce, PBKDF2-200k; a self-identifying, authenticated `magic + version` format header
  for clean future migration; `SECRETS_GUARD_PASSWORD` env var and an explicit `--password`
  shell-history/process-list caveat. Documented as a custom stdlib construction, **not an
  audited crypto library** — see `docs/SECURITY.md`.
- `affected_tests.py`: import resolution works on flat (`sys.path`-injection) layouts;
  content-hashed cache key (no same-second staleness).

[Unreleased]: https://github.com/doivamong/agent-workbench/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/doivamong/agent-workbench/releases/tag/v0.1.0
