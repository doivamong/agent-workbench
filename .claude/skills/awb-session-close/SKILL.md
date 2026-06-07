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

Everything turns on one question: **would closing the window LOSE this, or leave it mid-operation?**

- **BLOCK** — uncommitted changes; commits not on any remote (or an *unmeasurable* unpushed count —
  unknown is not "safe"); an in-progress **rebase / merge / cherry-pick**; **detached-HEAD** commits
  (reflog-only). These are local-only or mid-flight; close and they are at risk. Verdict: *not safe
  to close yet*.
- **WARN** — a **stash**, open PRs, and stale local branches. These persist on disk / are already on
  the server, so closing loses nothing immediately — they are hygiene (a stash is the classic
  *forgotten* one), surfaced with the exact command.

This is the whole point of the skill: scream only at real loss, stay quiet about the rest, so the
warning never becomes noise you learn to ignore.

## Process

1. **Audit.** Run the tool. It is read-only **to your work** — it never commits, pushes, merges, or
   deletes — but it *does* run `git fetch --prune` once (a network call) so the branch state is
   real; pass `--no-fetch` offline.

   ```bash
   python tools/session_close_audit.py          # or --no-fetch offline
   ```

   It reports six categories and a verdict: (1) uncommitted, (2) unpushed (or *unknown* if it can't
   compare against the remote), (3) **stash**, (4) **in-progress op** (rebase/merge/cherry-pick),
   (5) open PRs, (6) stale local branches — split into *delete-safe* (`-d`), *changes already in
   main via squash/rebase* (`-D`, verified with `git cherry`), and *work-not-provably-in-main*
   (review first). A detached HEAD is flagged inline.

2. **Completeness checkpoint — BEFORE you relay "safe to close".** Git safety is *proven* by the
   tool; whether the session's **task is done** is NOT a git signal, so do not mint it as a second
   verdict in the same definite register. Be **asymmetric**: if the objective was clearly met — or
   there was no multi-step objective (an exploratory, answered, or trivial session) — add nothing and
   go to step 3. Otherwise surface the task axis as a **question / a belief to confirm** (never a
   fabricated "1/3 phases" verdict), across the short open set you actually know from context:
   *objective state · tests/CI green/red/not-run · a promise made this session kept/open*. Three
   branches, with **unknown as the fail-safe default**:
   - **Confirmed done** → go to step 3.
   - **Unfinished and you'll resume** → *offer* a handover; on yes, run
     [`awb-handover`](../awb-handover/SKILL.md) as its own skill (its cold-reader HARD GATE stays
     intact — don't inline a thin version). The handover lands in the gitignored `handovers/` dir,
     local to this worktree, so it survives the close with **no commit needed**. Then go to step 3.
   - **Cannot determine** — a vague / changed / drifted goal, multi-session work, or a context
     compaction wiped the objective this session → do **not** assume done. Say "I can't verify your
     task is complete from my current context", ask the user, and offer a handover before closing.

3. **Relay the git verdict** (in this project, Vietnamese), stated as *proven*: git-safe to close, or
   the specific blockers that would be lost. The tool prints a one-line scope clause (git-safe ≠
   task-done) — reference it, don't re-author it.

4. **Clear the BLOCKers first** — if anything would be lost:
   - Uncommitted work you want to keep → ship it (review → `pre-commit run --all-files` → commit →
     push → PR → enqueue auto-merge, per [`docs/workflow.md`](../../../docs/workflow.md)), or
     `git stash` to set aside.
   - Unpushed commits → push, then verify with the run-id / merge-tree check before relying on CI.

5. **Offer the cleanup, never auto-delete.** The tool prints the exact `git branch -d` / `-D`
   commands (a branch whose name carries odd characters is listed for *manual* deletion, never put
   in a runnable line). Present them and get an explicit yes before running — deleting a branch is
   the user's call. Use `-d` for merged branches; `-D` for the squash/rebase-merged ones the tool
   verified with `git cherry`. (The tool already pruned remote-tracking refs in step 1 — no extra
   fetch needed.)

6. **Capture lessons, if warranted** — a surprising lesson worth keeping →
   [`awb-lessons-capture`](../awb-lessons-capture/SKILL.md). (Unfinished-work *packaging* is handled
   in step 2; this is only the lessons pointer.)

## The squash-merge trap (the one this skill exists to encode)

A naive `git branch --merged` misses it: a squash gives the merge a **new** commit hash, so the
branch's tip is never an ancestor of `main`, and `--no-merged` lists it as if it held unmerged work
— exactly the "leftover" that makes you afraid to close. The tool does **not** guess from the commit
*subject* (two unrelated commits can share a subject like `wip` or `update README` — matching on
that would force-delete real work). It asks **`git cherry origin/main <branch>`**: only when *every*
patch on the branch is already present upstream does it mark the branch `-D`-deletable.

**Honest limit you must relay:** `git cherry` is patch-id based, so a branch of **several** commits
combined into **one** squashed commit will *not* show as contained — it stays in *review*, not in
the `-D` bucket. That is deliberate (fail safe). When the tool says "review before deleting", it has
not proven the work is unmerged — verify (e.g. `git log origin/main --grep`), then delete by hand.
Never `-D` a `--no-merged` branch on the `--merged` check alone.

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

- **Read-only *to your work*, not zero-write.** The tool never commits, pushes, merges, or deletes
  — it reports and prints commands for you to run. It *does* run `git fetch --prune` once (a network
  call that refreshes remote-tracking refs) so the branch state is real; use `--no-fetch` to skip it
  offline. The destructive steps are yours to approve and run.
- **Squash detection is conservative, not omniscient.** It proves containment with `git cherry`
  (patch-id), so a multi-commit branch folded into one squash stays in *review*, not `-D` — verify
  and delete by hand. It will never *recommend* a force-delete it can't prove.
- **It measures git safety, not task-completeness — and asks, it does not assert.** "Safe to close"
  is git-only and *proven*; whether your *work* is done has no git signal. The completeness
  checkpoint (step 2) surfaces that as a question and **fails safe to "ask"** when it can't tell
  (e.g. after a compaction wiped the objective) — never to "done". Unfinished work is *packaged* by
  [`awb-handover`](../awb-handover/SKILL.md), not here; this skill only routes to it.
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
