---
name: gh-pr-checks-watch-no-checks-race
description: "gh's post-push async reads lag the real state: `pr checks --watch` exits 0 ('no checks reported') before CI registers, and `pr view --json mergeable` returns CONFLICTING before GitHub recomputes mergeability. Both are false signals — verify ground truth (run conclusion by id; git refs) before trusting or merging."
metadata:
  type: feedback
---

Right after `git push` + `gh pr create`, the CI run is often not yet associated with the PR. In that
window `gh pr checks <pr> --watch` finds **zero** checks, prints `no checks reported on the '<branch>'
branch`, and **exits 0** — which reads exactly like "all checks passed." It can make a background
CI-watch return success instantly and a PR get merged while its run is still `in_progress`.

**Second facet — same root cause.** Right after a push, `gh pr view <pr> --json mergeable` can return
`CONFLICTING` / state `DIRTY` even when the branch merges cleanly, because GitHub recomputes
mergeability **asynchronously** — a false alarm that would send you re-resolving nothing. Confirm
against git, not gh: `git log HEAD..origin/main` empty (branch contains all of main) **and**
`git merge-tree $(git merge-base HEAD origin/main) HEAD origin/main` showing no "changed in both"
means it IS mergeable; re-query gh a moment later and it flips to `MERGEABLE`.

**Why:** an empty check set is not a passing check set, and a not-yet-recomputed mergeable flag is not
a real conflict. gh surfaces GitHub's async / eventually-consistent state at face value; right after a
push that state is stale.

**How to apply:** before trusting a gh post-push read, confirm against the authoritative source. For
CI: skip the PR indirection and watch the concrete run — `gh run list --branch <b>` for the id, then
`gh run watch <run-id> --exit-status`, and `gh run view <run-id> --json conclusion,jobs` before
merging; never merge on a watcher that exited without seeing at least one check. For mergeability:
trust `git log HEAD..origin/main` + `git merge-tree` over a just-pushed `mergeable` field.
