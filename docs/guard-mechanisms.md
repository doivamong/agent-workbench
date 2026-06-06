# Guard mechanisms — skill vs hook vs tool vs sub-agent

A "guard" can live in four places in this kit, and **where you put it changes what it
guarantees**. Putting a guard in the wrong mechanism is a quiet downgrade: it *looks* like a
boundary while being bypassable. This page is the rule for choosing. It serves the honesty tenet
in [`PHILOSOPHY.md`](../PHILOSOPHY.md) — *"best-fit, honest about limits, not gospel."*

## The four mechanisms

| Mechanism | Fires | Bypassable? | Use it when | In this kit |
|---|---|---|---|---|
| **Hook** | deterministically, on an event (a tool call, a prompt, a compaction) | no — the harness runs it every time | the check must *always* fire and the trigger is a concrete event | [`block_dangerous.py`](../.claude/hooks/scripts/block_dangerous.py) (PreToolUse), `post_edit_simplify.py` (PostToolUse) |
| **Tool / CI gate** | when invoked (commit, CI, by hand) | only by not running it — but pre-commit/CI runs it for you | the check is deterministic and you want a hard gate with history | [`leak_scan.py`](../tools/leak_scan.py), [`invariants.py`](../tools/invariants.py), [`skill_lint.py`](../tools/skill_lint.py) |
| **Skill** | when the model matches its trigger | yes — the model can skip it or be talked out of it | the check needs *judgment* a rule can't encode (semantic completeness, "is the root cause right?") | `awb-review`, `awb-debug`, `awb-output-guard` |
| **Sub-agent** | when you spawn it | yes (you choose to run it) | you want an independent pass in a fresh context that didn't write the code | [`silent-failure-hunter`](sub-agents.md) |

## The decision rule

Ask: **does the guarantee come from *always firing*, or from *judgment*?**

- *Always firing* (a destructive command must never run; a secret must never commit; the registry
  must never drift) → **hook or tool/CI gate.** Deterministic, not bypassable in normal use.
- *Judgment* (is this output complete? is this the real root cause? does this design oversell a
  guard?) → **skill** (or a **sub-agent** when independence matters). No rule can make the call.

A file-system *event* (create / delete / rename) is a hook trigger, not an intent — route it to a
**hook**, not a keyword-matched skill, or a rename with no matching keyword silently skips the guard.

## Authority: the deterministic mechanism wins

When a guard exists as both a deterministic mechanism *and* a skill, **the deterministic one is
authoritative; the skill is only the advisory layer.** `block_dangerous.py` (a hook) is the
boundary against destructive commands; a skill that merely *reminds* the agent to be careful is
not, and must not be written as if it were. Never disable the hook because "a skill covers it."

## Honesty is mandatory for guard skills

Because a guard *skill* is bypassable, it must say so. Every guard-tier `SKILL.md` states **what it
does NOT do** — it is a seatbelt, not a security boundary. `skill_lint.py` warns when a guard-tier
skill is missing that line, so the honesty contract is greppable, not aspirational.

## Decision: `block_dangerous` is kept whole, not scoped

A recurring optimisation idea is to make `block_dangerous` cheaper or narrower — scope its matcher
to fewer commands, or add an allowlist so "safe" commands skip it. **Considered and rejected; the
guard stays byte-identical.** Two reasons:

- **The matcher keys on the tool *name* (`Bash`), not the command's content** — so there is no
  clean seam to "scope by verb". A content-aware allowlist is exactly what was removed earlier
  because substring-shadowing let `git push --force` / `git reset --hard` slip through; re-adding it
  would re-open that hole. A guard you can't scope safely is one you leave whole.
- **The per-command overhead is process spawn + import, not the matching.** Re-benchmarked on this
  machine (Windows, 12-core, Python 3.10, warm steady state, n=40 spawns): the hook costs **~70 ms
  per Bash command** (median) — of which **~36 ms is bare interpreter spawn** (`python -c pass`
  measures the same) and **~34 ms is the hook's own import + one-time regex compile**. The pattern
  *matching* itself is negligible (microseconds over ~18 short regexes on a normalized string). So
  scoping or shrinking the matcher would **not** move the number: the cost is paying for a Python
  process per command, which the matcher's content does not change. (Cold first-spawn measured
  ~70–76 ms here — not materially higher, because the interpreter and script were already cached; a
  true idle-cold spawn after a Defender eviction would be higher.) This *refines* the older
  qualitative "~80 ms, all interpreter-spawn" estimate: the order of magnitude was right, but about
  half the cost is the hook's import/compile rather than spawn — and crucially, **neither half is
  the matching** the scoping idea wanted to trim.

The net: a destructive-command guard earns its keep by being unconditional. The right place to make
a refused command *friendlier* is the deny message (the recovery-first text already does this), not
the coverage.

## Honest limit of this page

This is a guideline, not a generator: it tells you where a guard *belongs*; it does not enforce
that you put it there. The mechanisms also overlap at the edges (a skill may call a tool; a hook
may invoke one) — the table is the common case, not a taxonomy to litigate.
