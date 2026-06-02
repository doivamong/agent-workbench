# Getting Started

A 10-minute walkthrough: see the tools work, then wire them into your own project.

## 0. Prerequisites

- Python 3.10+ (the reusable core is stdlib-only; `pytest` is only for the test suite).
- Git. Optional: [Claude Code](https://claude.com/claude-code) (or another agent) to use the
  hooks and skills.

```bash
git clone https://github.com/doivamong/agent-workbench
cd agent-workbench
python -m pip install -r requirements.txt
```

## 1. See it work (each runs in seconds)

```bash
python examples/secrets_demo.py     # encrypt/decrypt round-trip + tamper detection
python examples/hook_block_demo.py  # classifies safe vs dangerous shell commands
python examples/invariant_demo.py   # the invariant gate catching rule violations
```

Then confirm the tools are actually trustworthy:

```bash
python -m pytest -q                 # the test suite
python tools/leak_scan.py . --fail-on-find   # this repo scans itself: 0 findings
```

## 2. Install into your project

```bash
python install.py /path/to/your/project --with-git-hook
# --dry-run to preview; --force to overwrite existing files
```

This copies the hooks, skills, rules, tools, `secrets_guard`, and the memory scaffold into
your project, optionally installs a git pre-commit leak gate, and prints the `settings.json`
snippet you need. Merge that snippet into `your-project/.claude/settings.json`.

## 3. What you now have

Open your project in Claude Code (or your agent). Immediately:

- **Dangerous `Bash` commands are blocked** (force-push, `rm -rf /`, `DROP TABLE`, …) by a
  `PreToolUse` hook.
- **Vague prompts get flagged** to be refined first, by a `UserPromptSubmit` hook.
- **Commits that leak a secret are refused** (if you used `--with-git-hook`).
- **Skills** under `.claude/skills/` and a working **memory** folder under `memory/`.

## 4. Make it yours

- **Skills:** copy `.claude/skills/SKILL_TEMPLATE.md` and write playbooks for your workflow;
  keep `.claude/skills/skill-registry.md` in sync. See
  [`.claude/skills/README.md`](../.claude/skills/README.md).
- **Invariants:** replace `SAMPLE_INVARIANTS` in `tools/invariants.py` with your project's real
  "must never break" rules. Enable the invariants hook in `.pre-commit-config.yaml`.
- **Leak scanner:** keep a private deny-list (gitignored) of your project's identifiers and run
  `python tools/leak_scan.py . --denylist your-denylist.txt` to verify exports.
- **Memory:** start adding facts under `memory/` and indexing them in `memory/MEMORY.md`. See
  [`memory/README.md`](../memory/README.md) and [`memory-governance.md`](memory-governance.md).
- **Project rules:** adapt [`../CLAUDE.md`](../CLAUDE.md) / [`../AGENTS.md`](../AGENTS.md) to your
  project's golden rules.

## 5. CI

The included [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs the leak scan,
invariants, and tests on every push/PR — the kit gates itself with its own tools. Reuse the
same pattern in your project.
