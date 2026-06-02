---
name: example-config-guard
description: >
  WHAT: guard against the two silent failures of config access — reading a key in the wrong
  CONTEXT, and reading a nested key at the wrong LEVEL (which returns None silently).
  USE WHEN: writing or modifying code that reads/writes configuration — especially a nested
  key, or a read that runs in more than one execution context (in-request vs. a script/job).
  DO NOT TRIGGER: reading config once just to understand the system; a single hard-coded
  constant with no nesting and one obvious context.
tier: guard
oversight: high
---

# Config guard — two contexts, two levels

> **Announce on activation:** "Using example-config-guard — checking access context and key level."

Config bugs are quiet. The code runs, returns `None` or reads a stale value, and the failure
surfaces somewhere far away — an `AttributeError` on `None`, a per-request file read that drags
latency, a setting that silently never takes effect. The cheapest place to stop that is before you
write the access.

## HARD GATE — verify BOTH before writing config-access code

1. **Context** — *where* does this code run? Many apps expose config through two doors: an
   in-request accessor (cached, valid only inside a framework request) and an out-of-band loader
   (`load_config(path)` for scripts, jobs, init). Use the wrong one and you get a runtime error
   ("working outside of application context") or a file read on every request.
2. **Level** — is the key **top-level** or **nested** under a container? A nested key read one
   level deep returns `None` *silently* — no exception, just wrong behavior downstream.

If either is unclear, stop and read the two sections below before writing code.

## Two contexts — don't cross them

| Accessor | Use when |
|---|---|
| the in-request accessor (e.g. `get_cfg()`) | inside a framework request (routes, request-scoped services) |
| the out-of-band loader (e.g. `load_config(path)`) | outside the framework (scripts, batch jobs, init) |

## Two levels — the silent-None trap

A key under a container must be read **two levels deep**, with a typed fallback:

```python
cfg.get("config_section", {}).get("inner_value") or {}   # correct
cfg.get("inner_value")                                    # BUG: returns None silently
```

Always pair a nested read with `or {}` / `or []` / `or ""` so a not-yet-seeded container can't
raise downstream. Some settings live in the framework's own config object, *not* the config file —
changing them in the file does nothing. Confirm which surface owns a key before editing it.

## Checklist before you commit a config change

- [ ] Top-level or nested? Nested → two-level read with a typed fallback.
- [ ] In-request context → in-request accessor; out-of-band → the loader.
- [ ] Framework-owned setting → change it on that surface, not the config file.
- [ ] Grep your diff for a flat read of a known-nested key — expect zero.

## Failure-modes registry (append-only)

Each time a config access causes a new failure, add a row. **Never delete a row** — the table is
collective memory of every way this has bitten before.

| # | Trigger | Symptom | Fix | Severity |
|---|---|---|---|---|
| 1 | nested key read flat | silent `None` → `AttributeError` far downstream | two-level read + `or {}` | high |
| 2 | out-of-band loader inside a request | file I/O every request (latency) | in-request accessor | medium |
| 3 | framework-owned setting put in the config file | setting silently never applies | set it on the framework surface | medium |

## Honest limit

This skill is the **advisory** layer; it does **not** itself guarantee anything — it is
model-invoked and bypassable. The *deterministic* guarantee is the `config-flat-access` check in
[`tools/invariants.py`](../../../tools/invariants.py), which always fires on a flat read of a
known-nested key (wire your real container + key names into it). Per
[`docs/guard-mechanisms.md`](../../../docs/guard-mechanisms.md), that invariant is authoritative;
this skill only explains the discipline behind it. It cannot detect a *wrong-context* read
statically (that depends on the call path), and the invariant is a line scan that needs its keys
configured — neither replaces reading the access site.
