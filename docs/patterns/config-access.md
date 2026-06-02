# Config access — two contexts, and the silent-None trap

Reading configuration looks trivial, so it rarely gets a second thought — which is exactly why two
recurring mistakes here produce bugs that are slow and confusing to trace. This page names both and
gives the cheap defensive habit that avoids them. (It's the concrete cousin of the *validate at the
boundary* default in [`development-rules.md`](../development-rules.md).)

## Two ways to read config — match the execution context

Many frameworks expose **two** routes to the same configuration, and they are not interchangeable:

| Accessor | Valid where | What it costs you in the wrong place |
|---|---|---|
| **Context-cached** — read from an in-memory object the framework populates when the app/request starts | Only *inside* that app/request context | Call it from a standalone script, a job, or a CLI and it raises (typically *"working outside of application context"*) |
| **Direct file load** — open and parse the config file on each call | Anywhere (scripts, jobs, startup) | Call it on a hot request path and you re-read + re-parse the file on *every* request — silent latency |

The rule is just: **pick the accessor that matches where the code runs.** Inside the request/app
context use the cached one; outside it, load the file.

## The silent-None nested-key trap (the expensive one)

A dict-style config returns `None` for a missing key instead of raising. That `None` doesn't fail
where you read it — it travels downstream and detonates somewhere else as
`AttributeError: 'NoneType' object has no attribute 'get'` (or `.items()`), on a line that looks
unrelated to config. You then debug the symptom, three layers from the cause.

```python
# UNSAFE — a missing key becomes None and leaks downstream
section = cfg.get("section")          # missing -> None (no error here)
for k, v in section.items():          # AttributeError, far from the real cause
    ...

# SAFE — supply the typed default you expect, at the access site
section = cfg.get("section", {})      # missing -> {}, fails (or is empty) right here
value = cfg.get("section", {}).get("key") or []   # nested: default at *each* level
```

**Habit:** at the point you read a key, give it the default of the type you expect (`{}`, `[]`, `0`,
`""`). A missing key then degrades *predictably and locally* instead of surfacing as a baffling error
elsewhere. This matters most for **nested** keys, where you must default at every level you descend.

## App/framework config ≠ your config file

There are usually two separate layers, and conflating them wastes time:

- the **framework's own runtime config** (session, cookie, security, template flags) — set in code when
  the app is constructed;
- your **project config file** (the business settings) — read via the accessors above.

Settings that live in the framework layer don't belong in your config file, and vice-versa. Know which
layer owns each key before you go looking for it (or adding it to the wrong place).

## Codifying it

These traps are mechanical, so they can be caught mechanically rather than by memory: encode the
"nested keys must be accessed with a default" and "don't load the file on a request path" checks as a
greppable invariant (see [`tools/invariants.py`](../../tools/invariants.py)) or a path-scoped rule (see
[`lessons-as-rules.md`](../lessons-as-rules.md)). A check that fires on the diff beats a rule you have
to remember.

## Honest limit

A default-at-the-access-site makes a missing key fail *locally and predictably* — it does **not** check
that the value is *correct*. When a config section's shape actually matters, validate it once at load
(a schema check), and treat the access-site default as the cheap floor underneath that, not a
replacement for it.
