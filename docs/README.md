# Documentation index

A topic map of `docs/`. Start with **[getting-started.md](getting-started.md)** (install → use →
uninstall → troubleshoot — the single source for setup) and **[workflow.md](workflow.md)** (which
skill to reach for when).

> **Note on the Vietnamese files.** `README.vi.md` and `PHILOSOPHY.vi.md` here are translations of the
> **root** [`../README.md`](../README.md) and [`../PHILOSOPHY.md`](../PHILOSOPHY.md) — *not* of this
> index. `getting-started.vi.md` is the translation of `getting-started.md`. This `README.md` is the
> docs index and is English-only.

## Start here

- [getting-started.md](getting-started.md) — a ~10-minute walkthrough: run the demos, install into
  your project, uninstall, and troubleshoot. The single source for install/uninstall.
- [workflow.md](workflow.md) — which skills to chain for which task.
- [guard-mechanisms.md](guard-mechanisms.md) — skill vs hook vs tool vs sub-agent: when to use which.

## Security & honesty

- [SECURITY.md](SECURITY.md) — the security model & threat model (what the guards do *not* defend).
- [SANITIZATION.md](SANITIZATION.md) — sanitization & provenance: how the kit was domain-stripped.
- [pre-commit-failure-modes.md](pre-commit-failure-modes.md) — a pre-commit gate that learns: the
  failure-modes registry.
- [external-tool-reliability.md](external-tool-reliability.md) — trusting an external analysis tool:
  benchmark before you believe it.

## Memory & sessions

- [memory-governance.md](memory-governance.md) — the memory governance reference design.
- [session-preservation.md](session-preservation.md) — session context preservation reference design.

## Skills, agents & orchestration

- [skills-as-cli.md](skills-as-cli.md) — blueprint: running skills outside Claude Code.
- [skill-system-roadmap.md](skill-system-roadmap.md) — the skill system roadmap (proposed expansion).
- [sub-agents.md](sub-agents.md) — focused reviewers you spawn on demand.
- [orchestration.md](orchestration.md) — delegating work to sub-agents.

## Engineering discipline & patterns

- [development-rules.md](development-rules.md) — defaults for everyday code.
- [design-discipline.md](design-discipline.md) — make UI quality explicit, not a vibe.
- [lessons-as-rules.md](lessons-as-rules.md) — turning a mistake into a guardrail.
- [architecture-vocabulary.md](architecture-vocabulary.md) — a small vocabulary for architectural quality.
- [ui-redesign-workflow.md](ui-redesign-workflow.md) — a gated UI redesign method (admin + public).
- [patterns/](patterns/) — focused pattern notes: boundary coherence, config access, the optimization loop.

## Platform & ops

- [windows-agent-gotchas.md](windows-agent-gotchas.md) — silent failures specific to driving an agent
  on Windows.
- [ops-scripts-survey.md](ops-scripts-survey.md) — distilling an ops-script layer into the kit: survey
  & verdict.
- [ops-web-admin-design.md](ops-web-admin-design.md) — the opt-in `/admin` web layer: design & decisions.

## Vietnamese editions (bản tiếng Việt)

Translations of the **root** documents (and of getting-started), kept in sync by CI drift-guards:

- [README.vi.md](README.vi.md) — bản dịch của [`../README.md`](../README.md).
- [PHILOSOPHY.vi.md](PHILOSOPHY.vi.md) — bản dịch của [`../PHILOSOPHY.md`](../PHILOSOPHY.md).
- [getting-started.vi.md](getting-started.vi.md) — bản dịch của [getting-started.md](getting-started.md).
