# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses lightweight
[SemVer](https://semver.org/)-style tags. Because the kit is consumed by **copying files**
into a target repo (see `install.py`), a "release" is a reference point for what changed
since you copied — not a published package.

## [Unreleased]

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
