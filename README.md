# Claude Code Methodology Kit

> A battle-tested set of **skills, rules, hooks, and tooling** distilled from running
> Claude Code as a **solo developer** on a real production codebase for months.
> Steal what's useful. Open an issue if you have a better way.

🇻🇳 *Bộ công cụ + phương pháp luận làm việc với Claude Code, rút ra từ một codebase production thật do một dev solo vận hành. Lấy thứ bạn cần. Góp ý nếu bạn có cách tốt hơn.*

---

## Why this exists

Most Claude Code tips are toy examples. This kit is the opposite: it's the **generic,
reusable layer** extracted from a real single-developer project — the parts that have
nothing to do with the original business domain and everything to do with **making an
AI coding agent reliable, safe, and consistent over a long-lived codebase.**

It is deliberately **domain-stripped**. Every business identifier, secret, path, and
piece of customer data has been removed (see [`docs/SANITIZATION.md`](docs/SANITIZATION.md)).
What remains is methodology.

## Who it's for

Solo developers (or tiny teams) who:

- use Claude Code as their primary pair-programmer,
- maintain a codebase long enough that **consistency** and **guardrails** matter more than speed,
- want concrete, copy-pasteable patterns instead of abstract advice.

## What's inside

| Area | What it gives you | Path |
|------|-------------------|------|
| **Skill system** | How to encode reusable, intent-triggered playbooks for the agent — anatomy, tiers, a registry, and two runnable example skills | [`.claude/skills/`](.claude/skills/) |
| **Memory system** | A file-based, index-gated memory the agent carries across sessions — scaffold + example facts | [`memory/`](memory/) |
| **Safety hooks** | Block dangerous shell commands; auto-refine vague prompts; a fail-open hook wrapper | [`.claude/hooks/`](.claude/hooks/) |
| **Secrets at rest** | A dependency-free (stdlib-only) file encryptor — HMAC-CTR stream cipher + PBKDF2 — to keep `config`/`db` encrypted in a private backup repo | [`scripts/secrets_guard.py`](scripts/secrets_guard.py) |
| **Invariant checker** | A tiny framework for codifying "rules that must never break" as fast, greppable checks (a pre-commit/CI gate) | [`tools/invariants.py`](tools/invariants.py) |
| **Test selection** | AST-based "which tests does this change affect?" selector — faster CI than running everything | [`tools/affected_tests.py`](tools/affected_tests.py) |
| **Leak scanner** | A secret/identifier scanner with a private deny-list, used to verify this very export | [`tools/leak_scan.py`](tools/leak_scan.py) |
| **Writing rules** | How to write slash-commands and keep an AI agent on-style | [`.claude/rules/`](.claude/rules/) |
| **Methodology docs** | The memory-governance model + session-preservation patterns for long projects | [`docs/`](docs/) |
| **Runnable demos** | Each tool has a `examples/` entry you can run in 30 seconds | [`examples/`](examples/) |

## Generic vs. domain-specific — read this first

This kit is the **GENERIC** half of a larger private codebase. The table below is honest
about what's transferable and what was intentionally left behind:

| Transferable (here) | Left behind (domain-specific, not shareable) |
|---|---|
| Hook architecture (fail-open, crash-logged) | Business routes, ORM-less SQL joins |
| `secrets_guard` crypto | Profit/revenue formulas (trade secret) |
| Invariant *framework* | The 17 concrete project invariants |
| Memory governance *model* | The actual memory corpus |
| Prompt-refiner *mechanism* | Domain prompt vocabulary |

## Quickstart (5 minutes)

```bash
git clone <this-repo>
cd claude-code-methodology-kit
python -m pip install -r requirements.txt   # stdlib-only core; deps are for examples/tests

# See it work (each runs in seconds):
python examples/secrets_demo.py     # encrypt/decrypt round-trip + tamper detection
python examples/hook_block_demo.py  # dangerous-command classifier
python examples/invariant_demo.py   # the invariant gate

# Prove the tools actually work:
python -m pytest -q                 # 37 tests
```

## Install it into your own project

This is the part that makes it real, not a reference. Point the installer at any
project and it copies the hooks, skills, rules, tools, `secrets_guard`, and the memory
scaffold in, then prints the exact `settings.json` snippet that activates the hooks:

```bash
python install.py /path/to/your/project --with-git-hook
# --dry-run to preview first; --force to overwrite existing files
```

After installing and merging the printed `settings.json` snippet, opening that project in
Claude Code gives you, working immediately:

- **Dangerous `Bash` commands get blocked** (force-push, `rm -rf /`, `DROP TABLE`, …) via a
  real `PreToolUse` hook — verified against the documented hook I/O contract.
- **Vague prompts get flagged** to be refined first, via a `UserPromptSubmit` hook.
- **A git pre-commit gate** (`--with-git-hook`) that refuses to commit a leaked secret.
- **Drop-in skills** under `.claude/skills/` and a **working memory folder** under `memory/`.

Then make it yours: replace the example skills with your own, put your real rules in
`tools/invariants.py`, and list your project's identifiers in a private deny-list for
`tools/leak_scan.py`.

## Status & honesty

This is **best-fit as currently known, with better approaches left open** — not gospel.
It comes from *one* developer's context (solo, long-lived, AI-first). Your trade-offs may
differ. PRs that challenge a pattern are as welcome as PRs that extend one.

## License

[MIT](LICENSE) for the original code. Several pieces are ports/derivatives of other
open-source work — see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for attribution
and the obligations that come with them.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: this is a learning artifact,
so **"here's a better way" issues are the whole point.**
