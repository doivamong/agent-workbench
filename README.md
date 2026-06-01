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
| **Safety hooks** | Block dangerous shell commands; scan for secrets before they're written; auto-refine vague prompts | [`.claude/hooks/`](.claude/hooks/) |
| **Secrets at rest** | A dependency-free (stdlib-only) file encryptor — HMAC-CTR stream cipher + PBKDF2 — to keep `config`/`db` encrypted in a private backup repo | [`scripts/secrets_guard.py`](scripts/secrets_guard.py) |
| **Invariant checker** | A tiny framework for codifying "rules that must never break" as fast, greppable checks (a pre-commit/CI gate) | [`tools/invariant_framework/`](tools/invariant_framework/) |
| **Test selection** | AST-based "which tests does this change affect?" selector — faster CI than running everything | [`tools/affected_tests.py`](tools/affected_tests.py) |
| **Writing rules** | How to write slash-commands and keep an AI agent on-style | [`.claude/rules/`](.claude/rules/) |
| **Memory & sessions** | A 3-layer memory governance model + session-preservation patterns for long projects | [`docs/`](docs/) |
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

# 1. Encrypt a file with the stdlib crypto
python examples/secrets_demo.py

# 2. Run the dangerous-command hook against sample input
python examples/hook_block_demo.py

# 3. Run the invariant framework against the sample project
python examples/invariant_demo.py
```

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
