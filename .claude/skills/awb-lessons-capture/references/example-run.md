# Worked example — one capture run, end to end

A concrete walk-through of the [`SKILL.md`](../SKILL.md) phases on a **fabricated** session. The
point is to make the mechanism demonstrable even though the shipped placeholder corpus is too
small for the value-scoring to be *measurable* (see the skill's *Honest limit*). Nothing here is
written to real memory — it shows what the run looks like.

---

## The fabricated session

> A feature flag (`beta_export`) was "always off" in one environment. ~40 minutes went into it.
> Root cause: the code read `config.get("flags", {}).get("beta_export")`, but in that environment
> the flags lived under `config["features"]["flags"]`. The wrong-level `.get()` returned `None`
> with no error, and `None` read as "off". The fix was to read at the correct level and assert the
> key path exists rather than trusting a falsy default. A smoke test for the flag was added.

## P0 — Collect knowledge-generating events

| Event | Classify |
|---|---|
| The flag silently read as off because a nested key was read at the wrong level | **lesson** |
| "Spent ~40 min bisecting the flag logic" | retro (narration) |
| "Decided to add a smoke test for the flag" | decision (weak rationale) |
| "We should write more tests" | lesson-shaped, but generic |

Only the first is a candidate lesson; the retro and the bare decision do not proceed.

## P1 — Raw candidates (one line each), then checkpoint

```
1. flag reads as "off" -> nested config key read at the wrong level, .get() returned None silently -> read at the right level / assert the key path
2. "write more tests" -> (generic)
```

Checkpoint: this list is dumped to a scratch file before scoring (insurance against context loss).

## P2 — Gate, then score

**P2A — four binary gates**

| Candidate | G1 grounded | G2 non-redundant | G3 right-type | G4 durable | Proceeds? |
|---|---|---|---|---|---|
| 1 — silent None from wrong-level read | yes (observed) | yes (`python tools/memory_audit.py <live-dir>` shows no near-dup) | yes (a lesson) | yes (true across any nested-config read) | **yes** |
| 2 — "write more tests" | weak | n/a | n/a | n/a | no (drops at G1/G3) |

**P2B — value_score for candidate 1**

| axis | score | reason |
|---|---|---|
| non_obvious | 4 | the read *looks* correct; the failure is invisible |
| reusable | 4 | applies to any nested-config read, any stack |
| actionable | 4 | "read at the right level / assert the path" is a concrete move |
| cliche_risk | 1 | specific to the silent-None mechanism, not generic advice |

`value_score = 4 + 4 + 4 - 1 = 11`

## P3 — Decision matrix

- Row 1 (severity-rescue): not catastrophic-on-recurrence — skip.
- Row 2 (cliche_risk >= 4): cliche_risk is 1 — skip.
- Row 3 (value_score >= 7 AND actionable >= 2 AND cliche_risk <= 2): **11 >= 7, 4 >= 2, 1 <= 2 -> GEM.**

Candidate 2 was already gated out, so **one** gem survives. (Had none survived, the run would stop
at the report-zero gate with *"this session produced no durable lesson"* — and that would be a
correct, complete outcome.)

## P4 — HARD GATE (nothing written yet)

```
## Lessons to capture (awaiting approval — NOTHING is written yet)

| # | Lesson (one sentence) | value_score | Verdict | Proposed frontmatter | Proposed filename |
|---|---|---|---|---|---|
| 1 | A feature that reads as "off" can be a nested config key read at the wrong level returning None silently. | 11 | GEM | name: feedback-nested-config-silent-none, metadata.type: feedback | feedback-nested-config-silent-none.md |

**Recommended pick:** write the GEM/KEEP rows (here: row 1) — these cleared the bar outright.
Reply `all recommended` / a subset of #s / `none`.
```

The human approves the single row (`all recommended`).

## P5 — Write (to the live dir from the recall-doctor)

`<live-dir>/feedback-nested-config-silent-none.md`:

```markdown
---
name: feedback-nested-config-silent-none
description: A feature behaving as if its config value is unset is often a nested key read at the wrong level returning None silently.
metadata:
  type: feedback
---

When a flag or feature acts as if its config value is missing, suspect a nested-key read at the
wrong nesting level: `.get()` on the wrong parent returns None with no error, so the value reads
as falsy and the feature silently stays off.

**Why:** the failure is silent — no exception, no log — so it masquerades as "the value is off"
and costs real debugging time.

**How to apply:** read at the correct level, or assert the full key path exists, instead of
trusting a falsy default; a guard that fires on a flat read of a nested key catches the class.
```

One index line appended to `<live-dir>/MEMORY.md` (under 200 chars, read-before-edit):

```markdown
- [feedback-nested-config-silent-none.md](feedback-nested-config-silent-none.md) — feature reads "off"? Suspect a wrong-level nested config read returning None silently. Fix: read at the right level / assert the path.
```

Verify: `python tools/memory_audit.py <live-dir>` reports no error.

## P6 — Suggest-only promotion

One sighting cannot prove recurrence, so nothing is promoted. If this same trap shows up again in
a later session, the suggestion to the human would be: *consider a path-scoped rule for code that
reads configuration* — but that is their call, not this skill's.
