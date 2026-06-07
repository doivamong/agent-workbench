---
name: awb-session-close
description: >
  WHAT: verify a working tree is safe to close at the end of a session — surface anything still
  dangling (uncommitted, unpushed, unmerged, stale branches) and clean it on your approval, so you
  close with certainty instead of fear of leftover work.
  USE WHEN: wrapping up and you want to be sure nothing is lost or left messy ("is it safe to
  close?", "did I leave anything uncommitted / unpushed?", "clean up the junk branches", "close out
  the session", "end-of-day repo check").
  DO NOT TRIGGER: packaging UNFINISHED work for the next session to execute (that is awb-handover);
  mining the session for durable lessons (that is awb-lessons-capture); shipping a specific change
  through review→commit→merge (that is the plan-then-code + review flow).
tier: workflow
---

# Session close-out — close with certainty, not fear

> **Announce on activation:** "Using awb-session-close — read-only audit first, then cleanup on your approval."

The fear this removes: after a long session you can't remember whether work is committed, pushed,
merged, or whether stale branches are piling up — so you close anxiously or comb git by hand. This
skill answers one question against ground truth: **"is it safe to close this window, and what's left
to clean?"** — then does the cleanup only after you say yes.

## The risk model (why some findings stop you and others only nudge)

Everything turns on one question: **would closing the window LOSE this?**

- **BLOCK** — uncommitted changes, or commits not on any remote. They live only in this working
  tree; close and they are at risk. Verdict: *not safe to close yet*.
- **WARN** — open PRs, and stale local branches. These are already on the server, so closing loses
  nothing — they are hygiene, surfaced with the exact cleanup command.

This is the whole point of the skill: scream only at real loss, stay quiet about the rest, so the
warning never becomes noise you learn to ignore.

## Process

1. **Audit (read-only).** Run the tool — it mutates nothing, it only reads git and `gh`:

   ```bash
   python tools/session_close_audit.py
   ```

   It reports four categories and a verdict: (1) uncommitted, (2) unpushed, (3) open PRs,
   (4) stale local branches — split into *delete-safe* (`-d`), *squash-merged, already in main*
   (`-D`), and *work-not-in-main* (review first).

2. **Relay the verdict in plain language** (in this project, Vietnamese). State clearly: safe to
   close, or the specific blockers that would be lost.

3. **Clear the BLOCKers first** — if anything would be lost:
   - Uncommitted work you want to keep → ship it (review → `pre-commit run --all-files` → commit →
     push → PR → enqueue auto-merge, per [`docs/workflow.md`](../../../docs/workflow.md)), or
     `git stash` to set aside.
   - Unpushed commits → push, then verify with the run-id / merge-tree check before relying on CI.

4. **Offer the cleanup, never auto-delete.** The tool prints the exact `git branch -d` / `-D`
   commands. Present them and get an explicit yes before running — deleting a branch is the user's
   call. Use `-d` for merged branches; `-D` only for the squash-merged ones the tool confirmed are
   already in main. Finish with `git fetch --prune origin`.

5. **Hand off or capture, if warranted** (not part of the safety check, but the natural next step):
   - Real work still in flight you'll resume next session → [`awb-handover`](../awb-handover/SKILL.md).
   - A surprising lesson worth keeping → [`awb-lessons-capture`](../awb-lessons-capture/SKILL.md).

## The squash-merge trap (the one this skill exists to encode)

A naive `git branch --merged` misses it: GitHub's squash gives the merge a **new** commit hash, so
the branch's original tip is never an ancestor of `main`, and `--no-merged` lists it as if it held
unmerged work — exactly the kind of "leftover" that makes you afraid to close. The tool cross-checks
the branch's commit **subject** against `origin/main`'s history (ignoring a trailing ` (#123)`): a
match + a gone remote means the work IS in main and the branch is safe to delete with `-D`, not real
work. Don't delete a `--no-merged` branch on the `--merged` check alone; trust the tool's
classification, which already did this.

## Concurrent sessions — the one case that makes the cleanup/ship steps unsafe

The audit (read) is always safe. The **cleanup and ship steps (writes)** are not, if another
session shares this checkout — and sharing one working tree is the *default* (separate `git
worktree`s are opt-in). So before any write, decide which case you're in:

- **Separate worktree / clone per session** — files are isolated, so committing your tree is safe.
  But it is **not a full firewall**: `.git/refs` and `.git/config` are still shared, so a commit
  can land on a branch the other worktree holds, and a stray `git branch -f` (plus a test that runs
  `git init`) can flip `core.bare` and freeze the repo. `git branch -d/-D` refuses to delete a
  branch checked out in another worktree — let that protection work; don't force around it.
- **Two sessions in the SAME tree** — they share HEAD and the index. Do **not** run the write steps
  in-tree: your `git checkout -b` moves the shared HEAD under the other session, and a regen gate
  (`sync_manifest` / `readme_metrics --write`, both used when shipping) bakes their uncommitted WIP
  into *your* commit. The `session_close_audit.py` report prints a concurrency caution before any
  write for exactly this reason.

**Always, before committing/pushing:** never trust the session-start "current branch" line — a
parallel session may have moved HEAD. Run `git branch --show-current` + `git status --short` and
confirm you're on your branch with a clean/expected tree.

**To still close a finished session while another runs in the same tree** (from
`land-shared-checkout-work-without-checkout`):

1. Verify the live branch (above).
2. Commit on a feature branch — confirm `git diff --cached` shows **only your files** (else `git add`
   swallowed their WIP; stage per-hunk with `git add -p`).
3. Before any `--write` regen gate, isolate any WIP that isn't yours, or it rides into your commit.
4. `git checkout main` to restore the tree to where the other session expects it.
5. `git push origin <branch>` + `gh pr create --base main --head <branch>` — these touch neither
   HEAD nor the working tree, so the other session is undisturbed.
6. Do **not** `git pull` / fast-forward the shared `main` afterwards — let the other session sync
   itself.
7. **Defer branch cleanup** until the other session ends — deletion is a WARN (nothing is lost by
   waiting), never a blocker.

The durable fix is one `git worktree` per session; the steps above are how you close *safely today*
when you can't split right now.

## Honest limits

- **Read-only by design.** The tool never commits, pushes, merges, or deletes — it reports and
  prints commands. The destructive steps are yours to approve and run.
- **`gh` may be absent.** Then the open-PR check degrades to "unknown" rather than failing; verify
  PRs another way before trusting "nothing unmerged".
- **It does not *detect* a second session — it reminds.** A reliable in-tree detector isn't
  possible from the tool: the per-worktree lock (`concurrent_session_guard.py`) holds only the
  *newest* session, so "the lock is alive" is true in normal single-session use and would
  false-alarm every run. So the report prints a concurrency *caution* before any write (with the
  factual worktree count), and leaves the verify-HEAD judgement to you. Real detection lives at
  session start, in the guard hook.
- **It is a nudge, not a gate.** Nothing forces you to run it at session end. It removes the
  *memory* burden; it cannot remove the *decision* to close.
