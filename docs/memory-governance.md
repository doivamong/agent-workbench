# Memory Governance — a reference design

> **What ships here vs. what this describes.** Agent Workbench ships the file-based
> [`memory/`](../memory/) scaffold — one fact per file plus an index-gated `MEMORY.md` — this
> design note, and **one manual safety tool**: [`tools/memory_snapshot.py`](../tools/memory_snapshot.py)
> (snapshot the memory dir before a risky edit, then restore if it goes wrong). That tool is
> **manual-only — run it yourself, never from a hook or cron**: an unattended mutator with no
> rollback is the exact failure the honest lessons below warn about. It does **not** ship the
> rest of the `memory_*.py` automation (health checks, decay, auto-promotion), a `reports/`
> folder, or Semgrep enforcement; those belong to the private codebase this kit was extracted
> from. In that codebase the automation layer is **code-complete but unexecuted, with
> auto-promotion mathematically infeasible** (see the honest lessons at the end). So treat the
> *other* tooling named below as *the design you'd build*, not files in this repo. The portable,
> working parts are the **layout**, the **index-gating discipline**, and the **promotion model**
> (which you implement yourself), plus the shipped **snapshot-before-mutate** safety net.

---

## 1. Three layers

Lessons live at the narrowest scope that fits; don't duplicate across layers.

| Layer | Lives in | Loaded | Written by |
|-------|----------|--------|------------|
| **L1 — Core config** | `CLAUDE.md` / `AGENTS.md` | always, every session | human; keep it < ~200 lines |
| **L2 — Path-scoped rules** | `.claude/rules/*.md` | only when editing a path that matches the rule's `paths:` | human |
| **L3 — Auto memory** | the per-project path `~/.claude/projects/<id>/memory/` (per-machine) | `MEMORY.md` index each session (first 200 lines / ~25 KB); topic files on demand | the agent (and you) |

> **Where this actually lives — read before curating facts.** As of Claude Code v2.1.59+, the
> harness auto-loads `MEMORY.md` (the first 200 lines, or ~25 KB) from the **per-project path**
> `~/.claude/projects/<mangled-cwd>/memory/` — *not* from this repo's `memory/`. **This repo's
> `memory/` is a committed reference template** (example facts you replace), not the live store;
> nothing loads it. Curate your real facts at the per-project path (or set `autoMemoryDirectory`
> in `.claude/settings.json`), and run `python tools/memory_recall_doctor.py` to confirm the
> wiring. (An earlier version of this doc labelled `memory/` "per-machine, gitignored" — that was
> wrong: the repo dir is a committed template; the *live* store is the per-project path.)

---

## 2. What the scaffold actually uses (L3)

Each memory is one file: a short frontmatter plus the fact. This is the convention the shipped
[`memory/`](../memory/) examples follow — start here.

```yaml
---
name: <short-kebab-slug>
description: <one line — used to decide relevance during recall>
metadata:
  type: user | feedback | project | reference
---
```

`feedback` and `project` facts add **Why:** and **How to apply:** lines in the body. Link related
memories with `[[other-name]]` — a **convention only**: nothing on disk auto-follows it (the kit
ships no resolver), so treat it as a pointer, not a guaranteed jump.

## 3. The index-gating discipline (the working core)

Recall is **index-gated**: only the live `MEMORY.md` (at the per-project path — see §1) auto-loads
each session; the agent follows a link to a topic file only when it needs the detail. The whole
system's cost control rests on keeping that index small, so this is the one rule worth enforcing:

- **Each `MEMORY.md` entry is a single line**, target ≤ 200 characters including markup.
- The session-start load reads roughly the first **200 lines, or ~25 KB**, of `MEMORY.md` (Claude
  Code v2.1.59+). Entries past that are silently **truncated** — recall lost, with no error;
  `python tools/memory_recall_doctor.py` flags an over-budget index.
- Detail belongs in the topic file body. Trust that a future session follows the link.
- **Curation cadence — tie it to a recurring event, not a remembered intention.** At every
  `awb-lessons-capture` / end-of-session retro, run `python tools/memory_audit.py <live-dir>`
  against the live per-project dir (see §1) and act on its byte-budget WARNs — trim the longest
  hooks back toward the per-line target. Anchoring curation to that event is what stops the index
  drifting silently up to the truncation boundary between deliberate clean-ups.

```markdown
# GOOD — punchy hook + one key tag
- [feedback-x.md](feedback-x.md) — X problem (root: Y). Fix: Z pattern. ~150 chars.

# BAD — multi-sentence detail that belongs in the file body, pushes the index over budget
- [feedback-x.md](feedback-x.md) — Detailed explanation… root cause was X, the fix was Y, plus an
  aside about W, plus a ROI note… 320 chars.
```

"Archiving" a memory means **removing its line from `MEMORY.md`** (the file stays on disk). That
is enough to drop it out of recall — you don't need to delete anything.

---

## 4. The promotion model (grow into it)

A recurring lesson should climb from L3 → L2/L1 so it loads reliably instead of depending on
recall. A simple, defensible threshold: promote when a lesson has recurred **≥ 3 times across
≥ 2 sessions** and is still "hot" (first→last seen within ~90 days).

| The lesson applies to… | Promote it to… |
|---|---|
| one path area (e.g. `scripts/**`) | `.claude/rules/lessons-<topic>.md` with a `paths:` filter |
| the whole project | a section in `CLAUDE.md` (keep the file short) |
| something a linter can check | a lint/AST rule |

Prefer path-scoped rules over growing `CLAUDE.md` — they load only when relevant and keep the
always-on prefix cacheable.

A fuller design can add lifecycle frontmatter (a stable `pattern_key` for dedup, a `severity`
that tunes decay, a `status` lifecycle with a resolution trail). Those are useful at scale, but
they are **the design you'd add**, not what the scaffold ships — add them when the corpus is big
enough to need them, not before.

**Optional `metadata.group` — a hand-set promotion-readiness bucket.** When you start to suspect
several facts are really the *same* recurring lesson, tag each with a shared, optional
`metadata.group` slug:

```yaml
metadata:
  type: feedback
  group: nested-config-reads   # OPTIONAL — a shared label, the SAME string on every related fact
```

`group` is the **only** legitimate key for grouping facts toward promotion. Bucket by `group`,
**never by `name`** — `name` is unique per fact, so bucketing by it puts every fact in a group of
one and surfaces nothing. That is exactly the wreck in §6: there the dedup key doubled as a unique
id, no key ever had ≥ 3 members, and auto-promotion produced zero candidates forever. `group` is
the inverse of `name` — it is *meant* to repeat across facts.

The opt-in `python tools/memory_audit.py <live-dir> --promotion-readiness` flag reports how many
fact files share each `group`. Run it against the **live per-project dir** (see §1) — that is
where your real facts live, not this repo's template. Treat the count as a *readiness hint, not a
trigger*: it **counts files, not distinct sessions**, so it cannot prove a lesson actually
recurred (a group of five could be one over-tagged session). Promotion stays the human judgment
above — recurred across ≥ 2 sessions and still hot; the flag only points you at candidates to
weigh. The field is optional and default-absent: without the flag the audit output is
byte-for-byte unchanged, and with the flag on a corpus where no fact carries a `group` the report
is a single `grouping INACTIVE` line.

## 5. Retention principle

If you do automate maintenance, one rule keeps it safe: **reads are safe to automate; writes and
deletes need a human in the loop.** The live memory dir (the per-project store) is outside git — there's no `git checkout` to
undo a bad bulk edit — so snapshot before any mutation and run such tools manually, never from a
hook or cron. And never age-sweep `feedback` (timeless lessons); only session-scoped `project`
entries should decay.

---

## 6. Honest lessons — what did *not* work

These cost real time to learn; the point of writing them down is so you skip them.

- **Git-log token matching is not a valid invalidation signal.** Scanning commit messages for
  "migrate X to Y" / "remove X" and decaying any memory that mentions X *seems* clever but
  misfires badly — a commit describes a code change, not that a lesson is stale. In the reference
  implementation it flagged the majority of memory files. Abandoned. Don't rebuild it without a
  new design and hard safety caps.
- **Auto-promotion was mathematically infeasible as designed.** Promotion needed ≥ 3 memories
  sharing one `pattern_key`, but `pattern_key` was also used as a *unique* identifier — so no key
  ever had 3 members and the cycle produced zero candidates. Every promotion that actually
  happened was a manual human decision. **The manual path is the one that works** — don't over-
  invest in automating it.
- **A destructive guard can be silently bypassed through a *different* parameter.** A cap meant to
  stop a bulk mutation only fired when one optional argument was absent — passing some *other*
  meaningful argument was treated as "the user clearly thought about this" and skipped the cap,
  which then let a damaging run through. An override must be its own explicit, single-purpose flag
  (`--force-...`), never a side effect of an unrelated option that happens to be set.
- **Deprecating a tool means deleting the things that still run it.** A mutation tool was retired as
  unsafe, but a scheduled task kept invoking it on a timer — the automation outlived the decision to
  kill the code. When you deprecate something dangerous, remove its cron/scheduler/hook entries in
  the *same* change, or the "dead" tool keeps running unattended.
- **Automated decay never earned its keep — archival is a manual, human-gated index edit.** The
  reference implementation's decay/age-sweep was **dead-spec**: code-complete but never run in
  anger, and its one concrete invalidation signal (the git-log token matching above) misfired so
  badly it was abandoned. What actually works is the cheap manual move from §3 — **delete a fact's
  line from `MEMORY.md`** to drop it from recall (the file stays on disk). Because archiving *is*
  removing that index line, an intentionally-archived fact then trips the audit's
  `not referenced in MEMORY.md (orphan / cold storage)` WARN **by construction** — for a fact you
  archived on purpose that warning is *expected and benign*, not a defect to chase. And never
  age-sweep `feedback`: those lessons are timeless — true until the code they describe changes, not
  until a clock runs out (only session-scoped `project` entries have a natural expiry; see §5).

The meta-lesson: a memory system's failure mode is silent (a truncated index, a wrongly-decayed
lesson). Favor read-only health checks and manual mutation over clever automation you can't see
fail.

---

## 7. Deferred capabilities & triggers

A capability we chose **not** to build is recorded here — in this committed, greppable file, never
only in a handover or in human memory. A defer that lives only in a handover silently dies, and that
forgetting is the exact failure the memory system exists to fight. The **Trigger is a gate**: if you
cannot name a concrete, falsifiable condition that would make the capability worth building, it is a
*reject* (say why), not a defer. A **measurable** trigger is also wired into a read-only audit WARN,
so the tool surfaces it the moment the condition fires; an **incident** trigger (a recall-miss, a new
third-party mutator) is noticed in the moment and recorded here. The kit never *acts* on a trigger —
surfacing is read-only; building the capability is a human decision (see §5, §6).

| Capability (deferred — do NOT build yet) | Why deferred (+ the alternative in use) | Trigger to revisit (concrete, falsifiable) | Self-surface channel | Recorded |
|---|---|---|---|---|
| **Query / recall CLI** | the reference implementation built one and left it wired into none of its skills — unused even at a multi-hundred-fact corpus; the agent's Grep/Read *is* recall at this scale | a real recall-miss incident: the agent fails to find a fact that exists on disk | this register (incident — noticed in the moment) | 2026-06-04 |
| **Decay / archival lister** (read-only `--list`, never `--apply`) | automated age-sweep is a documented wreck (git-log invalidation flagged the majority of files, §6); archiving today is the manual one-line index edit (§3) | **the early-margin (~80%) byte WARN fires** — authorizes the manual trim (redefined 2026-06-07; see note ‡) | `memory_audit` early-margin (~80%) + hard byte-size / line-count WARN (names this remedy + §7) | 2026-06-04; trigger redefined 2026-06-07 |
| **Consolidation / merge organ** | the external `anthropic-skills:consolidate-memory` plugin already merges duplicates — re-building it is feature-to-look-bigger | two+ facts trip the near-duplicate WARN (descriptions ≥ 70% token overlap) | `memory_audit` near-duplicate WARN (now names the external pass + §7) | 2026-06-04 |
| **MEMORY.md index generator** | hand-maintaining the small index is cheap, and a generator is a *write* tool (writes need a human, §5) | the hand-edited index repeatedly drifts from the facts on disk (recurring dangling-index-link ERRORs) | `memory_audit` dangling-index-link ERROR (already fires loudly) + this register | 2026-06-04 |
| **`[[wiki-link]]` resolver** | the links are a human-readable convention with no consumer — the capture skill does not follow resolved links | a built workflow/skill step actually consumes resolved links | this register (the dangling-wiki-link WARN flags broken links, but not "a consumer was built") | 2026-06-04 |
| **Importable snapshot precondition** (the code half of "snapshot before any mutation") | only one mutator exists — the manual `memory_snapshot.py`; the doc + snapshot + recall-doctor halves already shipped | a real third-party mutator of the live memory dir appears (anything but `memory_snapshot` writes there) | this register + the `defer-discipline` rule (fires when a memory tool is added) | 2026-06-04 |
| **`tools/memory/` package** (restructure the flat `memory_*.py` into a package) | **⚠ TRIGGER REACHED (2026-06-04), now SIX memory tools** (`audit`, `recall_doctor`, `snapshot`, `budget`, `sync`, `eval`) — each addition past five deepens the case; restructuring into a package is a live human call (§5/§6), deferred until someone takes it, the flat dir still holds | ≥ ~5 memory tools live under `tools/` | this register + the `defer-discipline` rule (its `paths:` covers `tools/memory_*.py`) | 2026-06-04 (eval added 2026-06-06) |

> ‡ **Trigger redefinition — Decay/archival lister (2026-06-07).** The original trigger, "the live
> index *repeatedly* trips the ~25 KB / 200-line budget", could only fire *after* the budget was
> already blown — i.e. after recall had begun silently truncating — and "repeatedly" made the durable
> fix wait on repeated data loss. It is deliberately redefined to fire on the **early-margin (~80%)
> byte WARN** added to `memory_audit` this session, so the manual trim is authorized while there is
> still headroom to act. The deferred capability is unchanged (still no automated `--apply`); only the
> surfacing threshold moved earlier. This is a genuine **trigger move** — an early-margin WARN neither
> "trips the budget" nor "repeats" — recorded here with date + rationale per
> [`defer-discipline.md`](../.claude/rules/defer-discipline.md), not slipped in as incidental copy.

> Recording a defer is a **human/agent judgment write**, not an auto-generated row — the kit never
> writes this table for you (writes need a human, §5). To revisit an item, build it only *after* its
> trigger has actually fired, then delete its row.

---

## Related

A HANDOVER is *session-scoped* working state, a different thing from these *durable* memories —
see [`session-preservation.md`](session-preservation.md) for that template and how the two
relate.

**Design influences:** Anthropic's
[memory](https://docs.claude.com/en/docs/claude-code/memory) and
[context-engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
guidance, and claudekit (MIT) — see [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
