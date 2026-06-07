---
name: git-cherry-detects-squash-merge
description: "To test whether a branch's work is already in main when it was SQUASH-merged (new hash → tip is NOT an ancestor), use `git cherry origin/main <branch>` (every line '-' = all patches upstream → safe to delete -D). Do NOT use `merge-base --is-ancestor` (squash rewrites the hash, tip never an ancestor) nor patch-id-equality of the tip (squash combines several commits into one). A multi-commit branch folded into one squash won't show as contained → fail SAFE to review, never auto -D. Subject-string matching is a false-positive trap (two commits share 'wip'/'update README' → force-deletes real work)."
metadata: 
  type: feedback
---

The question "is this `--no-merged` branch actually merged, just via squash?" has three
tempting-but-wrong answers and one right one.

- ❌ `git merge-base --is-ancestor origin/main <branch>` — a squash gives the merge a NEW commit
  hash, so the branch tip is **never** an ancestor of main. This is exactly why `git branch --merged`
  misses squash-merged branches in the first place.
- ❌ patch-id equality of the branch TIP vs a main commit — a squash combines *several* commits into
  one, so the tip's patch-id won't match any single main commit (it only works for a 1-commit branch).
- ❌ commit **subject** string match — two unrelated commits routinely share a subject (`wip`,
  `update README`, `fix typo`). On a destructive path this force-deletes real unmerged work; an
  empty/`(#N)`-only subject normalizes to `""` and matches anything. This is the one place a read-only
  tool can hand out a loss-bearing `-D` built on a coincidence.
- ✅ **`git cherry origin/main <branch>`** — patch-id equivalence per commit. Every output line
  starting `-` means that patch is already upstream; any `+` means a patch is NOT upstream. All `-`
  (or empty output) ⇒ the branch's work is contained in main ⇒ safe to delete with `-D`.

**Why:** `git cherry` answers the real question (are these changes already upstream by content?)
rather than a proxy (same hash / same subject) that squash breaks. Its one blind spot is the
inverse-safe direction: a MULTI-commit branch squashed into one upstream commit shows `+` (patch-ids
differ) and reads as "not contained" — so it stays in *review*, never auto-`-D`. That is the correct
failure mode for a tool that must never recommend an unprovable force-delete.

**How to apply:** for "is branch X already merged into Y" when squash/rebase is possible, run
`git cherry Y X` and treat all-`-` as contained. Never reach for `--is-ancestor` or subject-matching
on a squash workflow; if `git cherry` can't decide, fail toward "review", not "delete". Kin:
[[parallel-session-git-hygiene]] (squash dup-hash *recovery* via `rebase --onto`, the other half),
[[verify-load-bearing-before-asserting]] (the subject-match heuristic looks authoritative but rests
on a proxy).
