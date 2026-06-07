---
name: land-shared-checkout-work-without-checkout
description: "To land your OWN committed work from a git checkout SHARED with a live parallel session WITHOUT disturbing it: don't stay on the branch. `git checkout -b` to commit moves the shared HEAD under the other session (it then commits onto your branch, or its uncommitted work is at risk). Recover by: commit on the branch, `git checkout main` to return the working tree to where the other session expects it (its uncommitted edits travel with the checkout, unharmed), then `git push origin <branch>` + `gh pr create --base main --head <branch>` — push and PR-create touch neither HEAD nor the working tree, so you merge without ever disturbing the parallel session."
metadata: 
  type: feedback
---

Two sessions sharing ONE working tree race on HEAD/index (see [[parallel-session-sweeps-uncommitted-work]],
[[parallel-session-git-hygiene]]). The hazard isn't only the *other* session sweeping your work —
your OWN routine "branch + commit" disturbs *them*: `git checkout -b` silently moves the shared HEAD,
so the parallel session, thinking it's still on `main`, would commit onto your branch.

**Why:** `git checkout`/`-b`/`commit` mutate the shared HEAD and index; `git push` and `gh pr create
--head` do NOT — they only update a remote ref and call the GitHub API, leaving HEAD and the working
tree exactly where they are.

**How to apply:** when you must land your own change from a checkout shared with a live session —
1. commit on a feature branch (pre-commit auto-stashes the other session's unstaged files, so they're
   not swept in — verify the commit shows only YOUR files);
2. `git checkout main` to restore the tree to where the other session expects it (their uncommitted
   `M`/`??` files are preserved by the checkout since you didn't touch those paths);
3. `git push origin <branch>` then `gh pr create --base main --head <branch>` — merge from there.
The working tree never leaves `main`. Don't `git pull`/fast-forward the shared `main` after merge —
that dislodges them too; let the parallel session sync on its own. Real fix: give each session its
own `git worktree` (mind [[worktree-commit-leaks-gitdir-corrupts-shared-config]]). Verify CI by
run-id before merge, not `--watch` ([[gh-pr-checks-watch-no-checks-race]]).
