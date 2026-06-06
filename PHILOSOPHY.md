# PHILOSOPHY

**Canonical.** This is the source of truth for why Agent Workbench exists and how it must
behave. [`README.md`](README.md), [`CLAUDE.md`](CLAUDE.md), and [`AGENTS.md`](AGENTS.md) quote
one line and link here — they do not restate it. If anything in the repo conflicts with this
file, this file wins.

> **best-fit, honest about limits, not gospel.**

That is the one line every other file quotes verbatim.

## The four tenets

1. **Liberation.** The kit is the generic methodology layer pulled out of a private production
   codebase that can never be public — extracted so the knowledge isn't buried there forever.
   *Consequence:* it carries zero business IP, PII, secrets, or domain identifiers; distill the
   method, never bulk-transfer the source.

2. **Utility over metrics.** It is not published for stars, adoption, or attention. It exists so
   that whoever needs it can skip avoidable mistakes. *Consequence:* an artifact has done its job
   the moment it is available, correct, and honest the day someone reaches for it — counted or
   not. Don't add features to look bigger — but *do* grow by need: a tool or lesson earns its
   place when it distills real methodology someone would otherwise stumble without. The gate is
   on vanity, not on ambition; disciplined growth over many cycles is the mission, not a risk.

3. **Honesty about limits is the ethical core.** Load-bearing, not decoration: an oversold guard
   causes the very stumble it should prevent. *Consequence:* every tool and doc states plainly
   what it does NOT do; guardrails are seatbelts, not security boundaries; and what SHIPS is
   always distinguished from what is a BLUEPRINT you implement (the status table lives in
   [README.md](README.md#status--honesty) — link there, don't restate it).

4. **Dual, co-equal beneficiary.** Two readers matter equally: a stranger who needs it, and the
   author's own future self bootstrapping a new codebase. *Consequence:* the kit stays a
   droppable day-1 starter framework; lessons are products too, equal to tools.

## What would betray this

A change *protects* this philosophy if it distills a real need, closes a loophole, or makes a
hidden principle greppable — disciplined growth is welcome. A change *betrays* it if it does any
of these — catch them in review:

- a feature or tool is added to look bigger rather than because a real need demands it — bloat
  that isn't distilled (betrays tenets 2 and 4);
- a guard's doc drops its "what it does NOT do" line, or an absolute claim ("prevents",
  "guarantees", "secure") sits next to a guard with no hedge;
- star / adoption / traffic framing creeps into the copy;
- a tool ships without labeling SHIPS vs BLUEPRINT;
- a business identifier, real machine path, PII, or secret re-enters;
- `CLAUDE.md` grows past its short budget instead of linking out;
- work done **for the non-programmer persona** ships as dashboard polish or "easy / safe for
  non-coders" marketing, OR hides its caveat in a doc that persona will never read — instead of
  being a silent **fail-closed** guard, or a caveat the agent **relays in plain language at the
  moment of risk**. An honest "seatbelt" that the user reads as a "vault" betrays the very person
  it claims to protect. (A *fail-open* guard is fine — the kit's own leak-scan is one — as long as
  its hedge is relayed or stated, not buried.)
- **this file grows into a manifesto** instead of a terse constraint.

## For a fresh-context agent editing this repo

The four tenets are load-bearing, not decoration. Before you change a tool's behavior, its docs,
or the project's voice, re-read them. Keep the honesty line on every guard. Keep each satellite's
link back to this file. Change this file only if the philosophy itself moved — never let a
satellite contradict it.

## How this stays aligned — and its limit

[`tests/test_philosophy_anchor.py`](tests/test_philosophy_anchor.py) is a CI tripwire: it checks
that the satellites still link here and that the canonical tenet wording lives only in this file.
The [`awb-review`](.claude/skills/awb-review/SKILL.md) skill adds the semantic check a
regex can't. **Honest limit:** this keeps the public surface, adopters, and a future repo seeded
from this file aligned — it does **not** govern this repo's own private build/port pipeline,
which has its own internal charter.

## What this is NOT

- **Not a manifesto.** If a line here preaches instead of constraining code or docs, cut it.
- Not always-loaded — `CLAUDE.md` carries the one-line gist; this is the detail it links to.
- This file is also a **day-1 seed**: copy it (and its anchor test) into a new repo to carry the
  operating philosophy intact from commit one.
