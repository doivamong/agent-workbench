---
name: parallel-session-git-hygiene
description: "Multiple sessions/sub-agents sharing ONE git worktree race on the index/stash (one silently clobbers another's staged work); stage per-hunk, don't unstage shared files. And after a parallel branch squash-merges, local commits go same-content/different-hash → recover with `git rebase --onto origin/main <last-dup> <branch>` then re-test. And `git add` of a shared file can swallow a parallel session's in-flight edits — stage per-hunk or commit from a separate worktree."
metadata: 
  type: feedback
---

The staging index and stash are **per-worktree**, and parallel sessions / sub-agent fan-out share one
worktree by default (isolated worktrees are opt-in and expensive). Four failure modes follow:

1. **Shared index/stash race.** A second session's `git add` / `git stash` can clobber the first's
   staged work with no error — silent loss of staged changes.
2. **Squash-merge duplicate-hash divergence.** When a parallel branch is squash-merged to the remote
   (GitHub's default merge button), your local commits become "same content, different hash"; the
   push is rejected and the branch looks diverged.
3. **Stale session-start branch.** The harness's session-start git block (branch, recent commits) is
   a point-in-time snapshot; a parallel session can move HEAD onto another open PR's branch *after* it
   was taken. One session's block said `main` while the tree was actually on a parallel branch
   mid-stash — a blind commit would have landed on someone else's PR.
4. **`git add` of a shared file swallows another session's in-flight edits.** Staging a file a
   concurrent session is also editing (`git add README.md`) captures *their* uncommitted lines too, so
   your commit silently carries a change you never wrote — e.g. a test-count bump valid only with
   their tests (which aren't in your branch), then a red CI on your PR you'll chase as if it were yours.

**Why:** (1) and (4) are *silent* — your staged work vanishes, or a foreign change rides into your commit, with no signal. (2) is *loud* (git
shows the divergence) but the recovery incantation is non-obvious under pressure, and a naive reset
loses or re-does work.

**How to apply:** for (1) stage per-hunk with `git add -p`, never blind-unstage a file another
session may own, and watch `git status` for surprise modifications. For (2) replant only your own
commits onto the new base — `git rebase --onto origin/main <last-duplicate-commit> <branch>` — then
**re-test**, because the squashed base can differ semantically from what you branched off. For (3)
never trust the session-start `Current branch` line — run `git branch --show-current` + `git status
--short` to confirm the live branch and a clean/expected tree *before* any commit/push; if you're on
an unexpected branch, stash and branch off the intended base. For (4), stage with `git add -p` (or
confirm `git diff --cached` shows only *your* lines) before committing a file a parallel session may be
touching. Giving each session its own worktree avoids (1) and (4) entirely.
