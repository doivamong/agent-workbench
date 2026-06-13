---
name: awb-verify-docs
description: >
  WHAT: before writing framework- or library-specific code, ground it in the official docs for the
  version actually in use — cite the source, and flag anything you could only get from memory as
  unverified.
  USE WHEN: writing or changing code that depends on a specific library/framework/API (a hook
  signature, a config key, a version-sensitive pattern), or about to assert "this library does X" —
  anywhere a wrong-from-memory detail would compile but misbehave.
  DO NOT TRIGGER: choosing which library/approach to use (that's awb-research); deciding whether you
  may reuse outside code (that's awb-external-ref); original logic with no framework/version surface.
tier: feature
---

# Verify against the docs (don't code frameworks from memory)

> **Announce on activation:** "Using awb-verify-docs — I'll ground this in the official docs for the
> installed version before writing it."

Training data goes stale: an API you "remember" may have been renamed, deprecated, or had its default
changed between versions. A detail recalled from memory can compile and still be wrong. This skill
makes the cheap check — read the real docs first — routine for the parts where memory most often
betrays you.

## When this applies

You're about to write or change code against a specific library, framework, or external API, and the
exact signature, config key, or behavior matters. The point isn't to doc-check everything — it's to
not *guess* the version-sensitive parts.

## Scope

- **Does:** detect the version in use, fetch the matching official docs, write the code to them, and
  cite the source — flagging anything still unverified.
- **Does NOT:** choose between libraries/approaches (→ [`awb-research`](../awb-research/SKILL.md)),
  clear a reuse/license decision (→ [`awb-external-ref`](../awb-external-ref/SKILL.md)), or guarantee
  the docs are current (they can lag the code too — see Honesty).

## Process

1. **Pin the version.** Find what's actually installed (`requirements.txt` / `package.json` / a
   lockfile / `pip show` / `--version`), not the latest. The docs you read must match it — a default
   or a signature can differ across majors.
2. **Fetch the authoritative source.** Prefer, in order: the project's official docs/changelog → the
   web standard or spec → official type stubs. Use `WebFetch`, or a docs MCP (e.g. Context7) if one is
   connected. **Not authoritative — never the primary source:** a random blog, a forum answer, an
   AI-generated summary, or **your own training data**.
3. **HARD GATE: each load-bearing detail is cited, or marked UNVERIFIED.** For every signature, config
   key, or behavior the code relies on, either point to the doc (a deep link with an anchor — it
   survives doc restructuring better than a top-level URL) or write `UNVERIFIED: <claim> — from
   memory, may be outdated` next to it. Do **not** present a from-memory detail as confirmed.
4. **Surface a docs-vs-codebase conflict — don't silently pick.** If the official pattern differs from
   what the surrounding code already does (old API vs new, your convention vs theirs), state it and
   let the human choose: `CONFLICT: existing code uses X; docs for v<N> recommend Y — match the
   codebase, or modernize?` Choosing silently bakes in a decision that wasn't yours.

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "I know this API" | You know *an* API — possibly a prior major's. The rename / deprecation / changed default is exactly what memory misses; 20 seconds of docs beats a subtle runtime bug. |
| "It compiled, so it's right" | Wrong-from-memory code often compiles and misbehaves (a deprecated default, a changed return shape). Compilation isn't verification. |
| "The docs are basically the same across versions" | Defaults and signatures are where they quietly aren't. Pin the version and read *that* one. |

## Honesty / limits

This is a discipline, not an oracle. Official docs can lag the code, omit edge behavior, or be wrong;
the version you read must be the version you run, or the check misleads. It does not make you verify
everything — it makes you stop *guessing the version-sensitive parts* and label what you couldn't
confirm. The doc-fetch tool may be unavailable (no network, no MCP); when it is, say so and mark the
detail UNVERIFIED rather than proceeding as if confirmed.
