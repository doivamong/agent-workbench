# Contributing

This repo is a **learning artifact**, not a product. The most valuable contributions are
the ones that make a solo dev using Claude Code think differently.

## Especially welcome

- **"Here's a better way"** issues — challenge a pattern, propose an alternative, cite your context.
- **Portability reports** — "I tried hook X in my stack and it broke because Y."
- **Generalization fixes** — if something still smells domain-specific or leaks an assumption, flag it.

## Ground rules

1. **No secrets, ever.** This repo is intentionally domain-stripped. Don't add real paths,
   keys, customer data, or business identifiers — yours or anyone's. CI runs a secret scan.
2. **Keep the core stdlib-only** where it already is (e.g. `secrets_guard.py`). Dependencies
   belong in `examples/` and tests, not the reusable core.
3. **Every tool needs a runnable `examples/` entry.** "Readable but unrunnable" is the failure
   mode we're fighting.
4. **Frame conclusions as best-fit, not gospel.** This whole kit is one developer's context. The
   tenets it holds itself to — and the "what would betray this" review checklist — are canonical
   in [`PHILOSOPHY.md`](PHILOSOPHY.md).

## Before opening a PR

```bash
python -m pytest                                       # if you touched code
python tools/leak_scan.py . --entropy --fail-on-find   # must report 0 findings
```
