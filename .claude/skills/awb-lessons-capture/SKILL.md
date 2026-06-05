---
name: awb-lessons-capture
description: >
  WHAT: an end-of-session discipline that mines the just-finished session for durable
  lessons, scores each against a fixed bar, and writes only the survivors you approve to
  the live per-project memory so a future session recalls them. It is an honesty overlay
  on native auto-memory, not a capture engine: it adds the report-zero gate, a value
  score, dedup against the existing corpus, and a hard write-gate.
  USE WHEN: wrapping up a session and you want to keep what was learned ("capture the
  lessons", "memory retro", "what is worth remembering from this", "save the lessons
  before we stop"), especially after a surprising bug, a correction, or a counter-intuitive
  trap.
  DO NOT TRIGGER: a quick mid-session note (just jot it down); packaging unfinished work
  for the next session (that is a handover skill); promoting an already-captured recurring
  lesson to a rule (a human call in the lessons doc); a session where nothing surprising
  happened, where the honest output is simply zero.
tier: workflow
oversight: high
---

# Capture the lessons a session taught — without manufacturing them

> **Announce on activation:** "Using awb-lessons-capture — I'll mine this session for durable lessons, score them against a fixed bar, and write only what you approve to the live memory dir."

Most sessions teach nothing worth keeping, and a retro that always "finds three key learnings"
is inventing them to look productive — that noise is exactly what buries the rare lesson that
mattered. This skill imposes a fixed bar so the same junk gets culled every time and the same gem
gets kept every time. It runs at the **end** of a session, when invoked. It does not invent a
lesson to have an output: **zero is the common, correct answer.**

On a harness that captures memory natively (Claude Code v2.1.59+), the harness already writes
memory for you. This skill is not a second capture engine — it is the *discipline* the raw
capture lacks: a report-zero honesty gate, an explicit value score, a dedup pass against the
corpus you already have, and a hard gate that writes **nothing** until you approve.

## Scope

- **Does:** at end of session, surface candidate lessons, gate and score them, and — after your
  approval — write the survivors to the **live per-project memory dir** so they are recalled
  later. Reads the corpus to avoid duplicates; suggests (never performs) promotion.
- **Does NOT:** capture mid-session (jot those down), package unfinished work for a successor
  (that is a handover skill), or promote a lesson to a path-scoped rule (a human call — see
  [`docs/lessons-as-rules.md`](../../../docs/lessons-as-rules.md)). It writes to memory and
  nowhere else, and only with a human in the loop.

## Before you start — locate the live memory dir (do not guess it)

The repo's `./memory/` is a committed **template**; the harness loads memory from a **per-project
path**, not from the repo. Writing a fact to the wrong dir means it is never recalled — a silent
loss. So resolve the path explicitly, never by silent derivation:

1. Run [`tools/memory_recall_doctor.py`](../../../tools/memory_recall_doctor.py) and read the
   `Live (harness-loaded) memory dir:` line it prints.
2. Use that exact path as `<live-dir>` for every read and write below (pass it as `--dir` to the
   tools that take one). If the doctor cannot locate a live dir, **stop and ask** — do not invent
   a path. The write-spec for a fact is canonical in
   [`docs/memory-governance.md`](../../../docs/memory-governance.md) §2.

## The phases

### P0 — Collect knowledge-generating events

Scan the session for the things that actually generate a lesson, not for "what I did":

- a **bug and its ROOT cause** — especially a *silent* one that did not raise or log;
- a **counter-intuitive surprise** — "I expected X, it was Y";
- a point where the **user corrected you**;
- a **domain trap** (a sharp edge specific to this codebase or stack);
- a **decision with a counter-default rationale** (you chose the non-obvious option for a reason);
- a **recurring mistake in your OWN process** — a place the user corrected you, you reversed
  yourself, you declared "done" prematurely, or you relayed a claim you had not checked. This is the
  lesson a retro most often dodges, and since the kit's mission is *reliable agents* it is the most
  on-mission kind — do not skip it because it is uncomfortable.

Classify each as a **lesson** (a durable "do it this way / not that way"), a **retro** (a
narration of what happened), or a **decision** (a choice and its rationale). Only **lessons** —
and decisions whose rationale is strong enough to re-bind a future session — proceed.

**For a failure event specifically — ask the prevention question.** A bug, a silent trap, or a
self-process miss carries a second question beyond "what's the lesson": *what standing directive
would have structurally prevented it?* A fact in recall memory is *maybe* surfaced next time; an
always-loaded `CLAUDE.md` line or a path-scoped rule is *always* enforced. Note that candidate
sink now — you weigh it at P6. This does **not** change where this skill *writes* (still memory
only); the sink is a suggestion for the human, not an auto-write.

### P1 — Extract raw candidates, then checkpoint

Write each candidate as **one line**: *symptom -> root cause -> the correct way*. Merge obvious
near-duplicates now. **Checkpoint immediately:** dump this raw list to a scratch file before you
go further — it is cheap insurance if the session's context runs out mid-retro.

**Then synthesize — look ACROSS the candidates for the pattern.** Before you gate, ask: do several
events share a common root cause or a recurring behavioural pattern? The pattern (e.g. "I kept
asserting before verifying") is usually more valuable than any single atom, and a per-candidate
pipeline is blind to it — so add the pattern itself as a candidate and gate it like the rest.

### P2 — Gate, then score

**P2A — four binary gates (fail one and the candidate drops or is re-routed, *before* scoring):**

- **G1 grounding** — it comes from a real observed event this session, not speculation.
- **G2 non-redundancy** — it is not already in the corpus or an existing rule. Run the dedup read:
  `python tools/memory_audit.py <live-dir>` (pass the live dir — the audit defaults to the repo
  `./memory/`, the wrong corpus) and skim for an existing near-duplicate.
- **G3 right-type** — it is a lesson, not a retro or a bare decision.
- **G4 durability** — it is still true after the next library or code change. Ask: *would a future
  session do this wrong without the note?* If a refactor makes it moot, it is not durable.

**P2B — value_score (four axes, each 0-5):**

```
value_score = non_obvious + reusable + actionable - cliche_risk
```

- **non_obvious** — would a competent engineer plausibly get it wrong without the note?
- **reusable** — does it apply beyond the one incident that spawned it?
- **actionable** — does it tell a future session what to *do*, concretely?
- **cliche_risk** — how close is it to generic advice anyone could write without this session?
  (This one *subtracts*.)

### P3 — Decision matrix (stop at the first row that matches)

| # | Condition | Verdict |
|---|-----------|---------|
| 1 | **Severity-rescue:** catastrophic when it recurs (data loss / security / silent corruption) AND passes all four gates AND value_score >= 3 | **KEEP** (worth a fact on a single sighting) |
| 2 | cliche_risk >= 4 | **CULL** |
| 3 | value_score >= 7 AND actionable >= 2 AND cliche_risk <= 2 | **GEM** (write it) |
| 4 | 3 <= value_score < 7 | **MAYBE** (present it; default to drop unless you can name why it clears the bar) |
| 5 | otherwise | **CULL** |

**Mandatory report-zero honesty gate.** If no candidate reaches GEM or KEEP, say so plainly —
*"this session produced no durable lesson"* — and stop. Never lower the bar to manufacture one. A
session that yields zero gems is the normal case, not a failure of the retro. **And the inverse:**
do not let "report zero" become cover for dodging the uncomfortable lesson about your *own* process
(P0) — a comfortable technical finding does not discharge a real self-lesson you would rather not write.

### P4 — HARD GATE: present, then wait

Present every surviving candidate as a table and **write nothing until the human approves.**

```
## Lessons to capture (awaiting approval — NOTHING is written yet)

| Lesson (one sentence) | value_score | Verdict | Proposed frontmatter (name + type) | Proposed filename |
|---|---|---|---|---|
| ... | 9 | GEM | name: <slug>, metadata.type: feedback | <slug>.md |

Approve which rows to write (all / a subset / none). I will not touch memory until you do.
```

If the human approves none, that is a valid outcome — stop without writing.

### P5 — Write (only what was approved)

For each approved row, against the **live dir** from the setup step:

1. Write one fact file to `<live-dir>/<slug>.md` using the canonical frontmatter (see
   [`docs/memory-governance.md`](../../../docs/memory-governance.md) §2). For a `feedback` or
   `project` fact, add the **Why:** and **How to apply:** lines; link related facts with
   `[[other-name]]`.
2. Add one index line to `<live-dir>/MEMORY.md`, **<= 200 characters**, punchy hook plus one tag.
   **Read the file before you edit it.**
3. Verify: `python tools/memory_audit.py <live-dir>` — fix any error it raises before you finish.

### P6 — Suggest-only promotion

A single session cannot prove a lesson *recurs*, so never auto-promote. At most, **suggest** the
human consider promoting an apparently-recurring pattern to a path-scoped rule (the thresholds and
the reason promotion stays manual are in
[`docs/memory-governance.md`](../../../docs/memory-governance.md) §4). The decision is theirs.

There are **two distinct reasons** to suggest an always-loaded sink, and only the first needs
recurrence:

- **Recurrence** — a pattern seen ≥ 3× across ≥ 2 sessions (the §4 threshold) earns a path-scoped
  rule because it keeps happening.
- **Failure-prevention guarantee** — a *single* severe failure (the P3 severity-rescue kind) whose
  correct fix only binds if it is *always loaded* can warrant suggesting the sink on one sighting —
  the same one-sighting logic P3 row 1 already uses for KEEP. The case here is enforcement-guarantee,
  not frequency.

Either way it stays **suggest-only**: name the candidate sink — recall memory vs an always-on
`CLAUDE.md` line vs a path-scoped rule that loads only on a matching edit (place the directive where
it *fires*; see [`docs/lessons-as-rules.md`](../../../docs/lessons-as-rules.md)). The human writes
the rule; this skill still writes to memory and nowhere else.

## What this skill does NOT do

- Does **NOT** replace native auto-memory — on harnesses that auto-capture (Claude Code v2.1.59+),
  the harness already captures; this skill adds the report-zero gate, the value_score, the
  dedup-against-corpus, and the HARD GATE on top.
- Does **NOT** self-fire — it is *routable* via the SessionStart routing map
  ([`skill_routing_inject.py`](../../hooks/scripts/skill_routing_inject.py)), invoked when you
  recognize retro / end-of-session language. Nothing auto-fires it.
- Does **NOT** auto-promote — it only suggests (see P6).
- Writes **NOTHING** before HARD-GATE human approval (P4).
- Writes to the **per-project path** — run [`tools/memory_recall_doctor.py`](../../../tools/memory_recall_doctor.py)
  first and pass that path as `--dir`; do not let this skill silently derive it.
- Its value is **unverifiable on the ~5-fact placeholder corpus** shipped here — an honest limit;
  the in-repo demonstration is the worked example in
  [`references/example-run.md`](references/example-run.md).

## Anti-rationalization

| You'll think | Reality |
|---|---|
| "Surely this session taught *something*." | Most don't. Zero is the honest output; a forced lesson is noise that buries the real ones. |
| "It's basically a duplicate, but I'll add it anyway." | A near-dup splits recall across two files and dilutes both. Run the dedup read (G2) and merge instead. |
| "The path looks right, I'll just write it." | A mis-derived path writes the fact where nothing recalls it — a silent loss. Confirm with the recall-doctor first. |
| "I'll write it now and ask after." | The whole point of the HARD GATE is that memory is outside git — there's no clean undo. Approval comes first. |
| "It recurred, I'll promote it to a rule." | One session can't prove recurrence. Suggest it; let the human decide (P6). |
| "It's a failure, but filing it to recall memory is enough." | Recall *may* surface it next time; if a standing directive would have prevented it, also suggest the always-loaded sink (P6). For a failure, "maybe recalled" vs "always enforced" is the whole difference. |

## Honest limit

This is a discipline, not an enforcer: nothing here *forces* the gates to run or stops a forced
lesson from being written if you ignore the report-zero gate. The value of the scoring is real
only on a corpus large enough to have duplicates and clichés to catch — on the tiny placeholder
corpus it cannot be measured, only demonstrated (see the worked example). It improves the *odds*
that what reaches memory is worth its recall cost; it cannot guarantee it.

## References

- [`references/example-run.md`](references/example-run.md) — a worked end-to-end run: a fabricated
  session, the raw candidates, the scored table, and the single fact that survived to be written.
