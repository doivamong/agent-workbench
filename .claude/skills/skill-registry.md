# Skill Registry

A single, greppable index of every skill: one row per skill with its tier and its
trigger / anti-trigger summary. The point is that a future session (or a tired you) can
`grep` this one file to see the whole library at a glance, instead of opening 30 folders.

> This is a from-first-principles index format. Keep it deliberately simple — name, tier,
> when it fires, when it must not. Resist adding columns you won't maintain.

## How to use it

- Add a row the moment you create a skill; delete the row when you archive one.
- When two skills feel like they overlap, the **Do-not-trigger** column is where you write
  the boundary that separates them.
- Treat this file as the source of truth; if a skill's `SKILL.md` description drifts from
  its row here, fix one to match the other.

## Conflict resolution (write your rule down)

When more than one skill could match a request:

1. **Workflow > Guard > Feature > Audit** (tier precedence).
2. A **domain-specific rule beats a general one** when they disagree.
3. If still ambiguous, the agent should ask rather than guess.

## Registry

| Skill | Tier | Fires when (triggers) | Does NOT fire when |
|-------|------|------------------------|--------------------|
| `awb-plan-then-code` | workflow | "implement X", "add feature", anything multi-file that needs a plan first | a one-line fix; a pure question; a code review |
| `awb-review` | guard | "review my changes", before a commit/merge of a non-trivial change | general "is my whole codebase good?" audits; research questions |
| `awb-debug` | guard | "it's broken / erroring / wrong / crashing" with an unknown cause | a known one-line fix; a feature; a code review |
| `prompt-refiner` | workflow | a vague, multi-part request (the `prompt-refiner-inject.py` hook flags these) | an already-specific request; a trivial one-liner |
| `awb-research` | workflow | "how should we / what's the best way", comparing approaches, understanding a module before a non-trivial change | a vague request to clarify (that's prompt-refiner); executing an already-chosen approach; a one-line fix |
| `awb-handover` | workflow | ending a session, "hand this off / package for next session / write a handover", research-done-move-to-execution | work not finished enough to hand off; a quick mid-task note; starting fresh implementation now |
| `awb-stress-test` | workflow | "stress test this / poke holes in this plan / what could go wrong / edge cases / is this design sound", before building or testing something non-trivial | a one-line / low-risk change; comparing approaches (research); reviewing code already written (review); a known bug (debug) |
| `awb-output-guard` | guard | generating a whole file / large template / big refactor | a small edit to an existing file; a question; prose-only output |
| `awb-using-skills` | meta | auto-injected each session; also when ≥2 skills could match, or you're unsure any applies | as a destination — it routes TO other skills, never does the work itself |
| `awb-config-guard` | guard | writing/modifying code that reads config — esp. a nested key or a cross-context read | reading config once to understand it; a single non-nested constant |
| `awb-tdd` | workflow | "do this TDD / test-first / red-green-refactor / write the test first", a regression test before a bug fix | a trivial change (<~30 lines); config/data-only edits; a spike; reviewing written code |
| `awb-optimize` | feature | "it's too slow / optimize / cut latency / reduce memory" with a measurable goal | "tidy / simplify" with no speed goal (review); a correctness bug (debug); no baseline to measure against |
| `awb-dead-code-audit` | audit | "find unused / dead code", post-refactor or pre-release prune, "is this called anywhere?" | "this function is too long" (a structural concern); bug hunting (review/debug); code already known-dead |
| `awb-cook` | workflow | "cook this / run the full workflow / build X with checkpoints / plan from a few angles", larger or higher-stakes builds | a routine single-file change (plan-then-code); a one-line fix; a question; no sub-agent fan-out wanted |
| `awb-external-ref` | workflow | about to copy/adapt outside code (GitHub/snippet/blog/LLM), "can we use this / port this / adopt this approach" | writing original code; a vetted dependency via the normal process; a licensing question with no code in play |
| `awb-lessons-capture` | workflow | end of a session, "capture the lessons / memory retro / what's worth remembering", after a surprising bug, a correction, or a counter-intuitive trap | a quick mid-session note; packaging unfinished work for next session (handover); promoting a recurring lesson to a rule (a human call); a session where nothing surprising happened (the honest output is zero) |
| `awb-install-and-verify` | workflow | "install the workbench / set up the hooks", "are my guards actually on?", "did the install work?" — wiring + verifying the kit's guards via `install.py --merge-settings` then `--doctor` | building a new feature/hook (plan-then-code); editing settings.json by hand; a general code review (awb-review) |
| `awb-uninstall` | workflow | "remove agent-workbench / uninstall the kit / take the hooks out / undo the install" — dry-run `uninstall.py` first, confirm, then `--yes`; keeps files you edited | installing or verifying guards (awb-install-and-verify); hand-deleting files by yourself; a general code review (awb-review) |
| `awb-session-close` | workflow | ending a session, "is it safe to close?", "did I leave anything uncommitted/unpushed?", "clean up the junk branches", end-of-day repo check — runs `session_close_audit.py` then cleans on approval | packaging UNFINISHED work for next session (awb-handover); mining lessons (awb-lessons-capture); shipping a specific change through review→merge (plan-then-code) |
| _your-ui-guide_ | feature | designing or editing the UI | backend performance work |

Replace the placeholder rows with your real skills. The non-placeholder rows correspond to the
runnable skills in this folder (the README metrics block carries the live count).

> **Naming convention:** the kit's skills use the `awb-` prefix. `prompt-refiner` deliberately keeps
> its bare name because the `prompt-refiner-inject.py` UserPromptSubmit hook references the skill by
> that name — don't "fix" it to `awb-prompt-refiner` without also updating that hook.
