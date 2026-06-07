# Workflow — which skills to chain for which task

The [skills README](../.claude/skills/README.md) says *what each skill is* and how they're tiered.
This page is the other half: given a **kind of task**, what to run and in what order — and what the
hooks fire on their own without you asking. It's a routing map, not a rulebook; the tier and
precedence rules are defined once in that README and are linked, not repeated, below.

## skill vs hook vs tool vs doc — what kind of thing is each?

Four mechanisms, four different ways they run. Know which you're reaching for:

| Mechanism | How it runs | What you get |
|---|---|---|
| **skill** | intent-triggered *nudge* — you or the agent invoke it when the request matches | a reusable playbook the agent follows ([`.claude/skills/`](../.claude/skills/)) |
| **hook** | automatic + fail-open — fires on an event, no prompting | a guardrail at the seam ([`.claude/hooks/`](../.claude/hooks/)) |
| **tool** | manual CLI — you run it (or CI does) | a check or answer on demand ([`tools/`](../tools/)) |
| **doc / blueprint** | nothing runs — you read it and implement | a method or reference ([`docs/`](../docs/)) |

## What fires on its own

These run automatically — you don't invoke them. They're the ambient layer the chains assume:

| Event | Hook | What it does |
|---|---|---|
| At session start (not after a compaction) | [`session_start.py`](../.claude/hooks/scripts/session_start.py) | Injects the project primer (`.claude/session-primer.md`) so the skill system is in context from turn one |
| You submit a vague prompt | [`prompt-refiner-inject.py`](../.claude/hooks/prompt-refiner-inject.py) | Nudges you to sharpen the request first (see the `prompt-refiner` skill) |
| Before a `Bash` command | [`block_dangerous.py`](../.claude/hooks/scripts/block_dangerous.py) | Blocks obviously destructive shell commands (a seatbelt, not a security boundary) |
| After a burst of `Edit`/`Write` | [`post_edit_simplify.py`](../.claude/hooks/scripts/post_edit_simplify.py) | Reminds you to run a simplify pass |
| After each `Edit`/`Write` | [`context_tracker.py`](../.claude/hooks/scripts/context_tracker.py) | Nudges when the session context is getting heavy |
| Before a context compaction | [`precompact_backup.py`](../.claude/hooks/scripts/precompact_backup.py) | Backs up the transcript |
| After a compaction | [`compact_restore.py`](../.claude/hooks/scripts/compact_restore.py) | Re-injects the latest handover excerpt so work resumes |

All hooks are fail-open (a crash logs and exits clean — a guardrail must never halt the agent).

## Chains by task type

| When the task is… | Run, in order | Notes |
|---|---|---|
| **A non-trivial change** (feature, multi-file edit) | (`prompt-refiner` if the ask is vague) → [`awb-research`](../.claude/skills/awb-research/SKILL.md) *if the approach isn't obvious* → [`awb-plan-then-code`](../.claude/skills/awb-plan-then-code/SKILL.md) → [`awb-review`](../.claude/skills/awb-review/SKILL.md) before committing | The plan skill already folds in plan → implement → test → review |
| **A bug with an unknown cause** | [`awb-debug`](../.claude/skills/awb-debug/SKILL.md) (reproduce → root cause → fix → prove) | Don't skip to the fix; the gate below is "root cause first" |
| **Reviewing a change already written** | [`awb-review`](../.claude/skills/awb-review/SKILL.md) (spec → quality → adversarial) | Use before committing anything non-trivial |
| **Choosing between approaches** | [`awb-research`](../.claude/skills/awb-research/SKILL.md) → write the decision + why | Feeds the plan skill if you then build it |
| **A one-line fix with a known cause** | Just make it | No skill needed — but the gates and the auto-firing guards still apply |

## Blocking gates (don't skip)

These are enforced inside the skills above; collected here so the whole-flow view is in one place:

1. **Plan before implementation** — agree the approach before writing the change.
2. **Root cause before fix** — diagnose, don't guess-patch (see [`development-rules.md`](development-rules.md): *verify with evidence*).
3. **Tests green, with evidence** — run them and read the output; a claim isn't a result.
4. **Leak / dangerous-command guards** — clear the [leak scanner](../tools/leak_scan.py) and the command guard before a commit lands.

## Verifying a push before you merge

After `git push` + `gh pr create`, GitHub's state is **eventually consistent**, and `gh` surfaces it
at face value — so a post-push read can lie in two opposite directions, both from the same lag:

- **False green:** `gh pr checks <pr> --watch` finds *zero* checks in the window before CI registers,
  prints `no checks reported`, and **exits 0** — which reads exactly like "all passed." A background
  watcher can return success and a PR can merge while its run is still `in_progress`.
- **False conflict:** `gh pr view <pr> --json mergeable` can return `CONFLICTING` before GitHub
  recomputes mergeability, even when the branch merges cleanly.

Confirm against ground truth, not the PR indirection:

1. **CI result — watch the concrete run by id, not the PR.** `gh run list --branch <branch>` for the
   id, then `gh run watch <run-id> --exit-status`, and `gh run view <run-id> --json conclusion` must
   read `success`. Never merge on a watcher that exited without seeing at least one check.
2. **Mergeability — trust git, not the just-pushed `mergeable` field.** `git log HEAD..origin/main`
   empty (branch contains all of main) **and** `git merge-tree $(git merge-base HEAD origin/main) HEAD
   origin/main` showing no "changed in both" means it merges cleanly.

Branch protection on `main` now **enforces the green half**: the required status checks (lint, the
test matrix, and `ui-web`) must pass before GitHub will merge, so the platform stops a red merge for
you. The loop above is still the agent's job — it catches a red or stale state *before* you enqueue,
rather than letting GitHub refuse the merge after the fact. The git-side mergeability check stays
useful regardless: `strict` is off, so a branch need not be up to date with `main`, only
conflict-free.

## Auto-merge: enqueue, don't wait

Because branch protection requires the CI checks, the safety of a merge lives in the **required
checks**, not in a human watching the run. So after verifying a push (above), enqueue the merge
and move on instead of babysitting CI:

```bash
gh pr merge <pr> --auto --squash --delete-branch
```

`--auto` queues the PR; GitHub merges it **only when every required check is green**, then deletes
the branch. The agent still runs the 4-point integrity check and the run-id / merge-tree
verification *before* enqueuing — `--auto` is not a substitute for that, it just removes the
dead-wait afterwards. Tell the user, in plain language, that the PR is **queued and will merge when
green** (in Vietnamese for this project: *"đã xếp hàng, sẽ merge khi CI xanh"*). For a genuinely
urgent merge of an already-green PR, `--now` (or an admin merge) is the escape hatch.

**The silent failure to guard (B5):** a queued PR whose *late* check goes red just sits open,
un-merged, with nobody watching. So after enqueuing — and again on your next ship — run the
surfacer:

```bash
python tools/automerge_status.py            # plain-language report of every open PR
python tools/automerge_status.py --exit-code # exit 1 if any queued PR is STUCK (alert/CI use)
```

It flags a PR that is **STUCK** (auto-merge on, but a required check failed → it will never merge)
distinctly from one merely **queued** (waiting on pending checks), and prints the exact recheck
command for each. It is read-only — it never merges or closes anything.

### Triage a STUCK PR (investigate + propose, don't auto-fix)

The surfacer tells you a PR is stuck and *which* check is red — it stops there by design. Don't leave
it there: a STUCK PR is a real red check, so treat it as a bug to diagnose, not a queue to retry.

1. **Pull the evidence, don't guess.** Get the failing run and read its log, not just the check name:
   `gh run list --branch <headRefName>` for the run id, then `gh run view <run-id> --log-failed`.
2. **Flake vs. real failure.** A timeout / network blip / a check that passes on a clean re-run is a
   *flake* — propose a re-run, don't change code. A failure that reproduces is real → step 3.
3. **Root cause, not symptom.** Hand the failure to [`awb-debug`](../.claude/skills/awb-debug/SKILL.md)
   (reproduce → name the root cause → fix → prove). Don't guess-patch to make CI green.
4. **Propose, don't auto-act.** Surface the root cause and the fix for a human to approve. The fix
   lands as a *new* commit/PR that must itself pass the required checks — **never** force-merge or
   admin-merge past a red required check (that defeats branch protection). `--now` is only for an
   already-green PR.

This is in-session triage: it fires when you (or the agent, on a ship) run the surfacer and see STUCK.
It does **not** watch unattended — a check that goes red at 2am with no session open is not caught here
(that would need a scheduled `--exit-code` alert, deliberately out of scope).

## When several skills could fire

Precedence (**Workflow > Guard > Feature > Audit**) and "a domain-specific rule beats a general
workflow rule" are defined once in the [skills README](../.claude/skills/README.md#organizing-many-skills-tiers)
and [`development-rules.md`](development-rules.md). This page defers to them — it routes tasks, it
doesn't re-rank skills.

For work you hand to a sub-agent rather than do inline, see [`orchestration.md`](orchestration.md).

## Honest limit

Skills are intent-triggered *nudges*, not rails — nothing forces a chain to run, and a skill fires
only if its description matches what you asked. The hooks are fail-open seatbelts, not guarantees.
This map shows the path that usually pays off; picking it on a given task is still a judgement call.
