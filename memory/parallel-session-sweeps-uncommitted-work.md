---
name: parallel-session-sweeps-uncommitted-work
description: A second agent/Claude session sharing ONE working tree can switch HEAD under you and sweep your uncommitted edits into ITS commit + merge them — back up uncommitted work as a patch before pausing and re-check the branch after any gap.
metadata: 
  type: feedback
---

Two agent sessions running in the **same working directory** (not separate `git worktree`s) collide
destructively:

- You are on a feature branch with uncommitted work. The parallel session runs `git checkout -b
  other-branch` **in the same tree** → your HEAD moves under you (your next `git status` says a
  different branch), and your uncommitted change carries onto their branch.
- The parallel session then `git add -A`'s (or `commit -am`) → **your uncommitted change gets swept
  into THEIR commit**, pushed, and merged to main. Net effect: your work lands on main, but inside
  someone else's commits, with no review of the merged result, and your own branch label is left
  reset to base.

**Why it's nasty:** "uncommitted" feels safe but isn't — another writer in the same tree can commit
it for you. And HEAD/branch is shared mutable state, so your assumptions about "which branch am I on"
go stale across any pause.

**How to work safely:**
- Prefer a dedicated `git worktree add <path> <branch>` per session so the working trees are
  physically separate (the only real fix; no git command un-shares one tree).
- Before pausing / handing off, **back up uncommitted work as a patch** (`git diff [--cached] >
  x.patch` or copy the file) — it survives a branch-switch or sweep by another session.
- After any gap, **re-verify `git rev-parse --abbrev-ref HEAD` and `git status` before committing** —
  don't assume you're still on your branch.
- If your work was swept onto main by the other session, you may not need to redo it — `git diff
  <base>..origin/main -- <file>` tells you what actually landed; verify it's complete + gate-clean
  rather than re-applying blindly.

**Separate worktrees aren't a full firewall — and scary local state ≠ lost work:**
A dedicated `git worktree` per session separates the working *files*, but `.git/refs` and
`.git/config` stay **shared**, so the streams still collide: a commit can land on a branch another
worktree has checked out, and `git branch -f` on such a branch (plus a test hook that runs `git init`)
can flip `core.bare=true` and freeze the whole repo
([[worktree-commit-leaks-gitdir-corrupts-shared-config]]).

- **Diagnose FIRST, don't fight symptoms.** When files you didn't touch show as modified, a commit
  lands on an unexpected branch, or git suddenly errors, STOP and establish ground truth:
  `git worktree list` (is another worktree live?), `git config core.bare`, `git log origin/main`.
  Reacting symptom-by-symptom (repeated failed rebases, stash juggling) burns far more time than the
  one `git worktree list` that would have explained it.
- **Don't conclude "lost" from local state alone.** A deleted worktree + a branch with no WIP commit
  can look like lost work — but the parallel session may have already committed→merged→pushed it as a
  merged PR on `origin/main`. Check `origin/main` and merged PRs before you alarm.

Extends [[parallel-session-git-hygiene]] (index/stash races) with the commit-and-merge escalation.
