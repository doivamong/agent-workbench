---
name: trust-git-diff-over-harness-read-during-editor-race
description: "When an external editor/watcher holds a file, the agent's file-state loses the race: an Edit succeeds but a later Read shows the OLD content — `git diff` is ground truth, not the Read snapshot; don't blindly re-apply."
metadata: 
  type: feedback
---

When an external editor or file-watcher has a file open while you edit it through the agent harness,
the harness's cached file-state can lose the race. Observed: three `Edit` calls each reported
**success**, yet a follow-up `Read` (and the post-edit reminder snapshot) showed the **original**
content — looking as if the edits had been reverted. `git diff --stat` proved all the edits were on
disk the whole time (`+23 lines`, all markers present). The editor had a stale buffer and was
re-saving over the working tree intermittently, and the harness's read-state caught a stale moment
while git read the true bytes.

**Why:** the dangerous move is to trust the failed-looking `Read` and **re-apply the edit** — that
duplicates content, or makes you thrash chasing a "revert" that never happened. The harness file
tracker is a cached view; an external writer can desync it. `git`/disk is the source of truth.

**How to apply:** when a `Read` after a successful `Edit` shows unexpected (old) content and an editor
may be open, do **not** re-apply blindly. Verify ground truth with `git diff --stat <file>` /
`git diff <file>` (or grep the on-disk bytes for your markers). If git shows your change, it landed —
reconcile the working tree with `git checkout -- <file>` and **commit** to lock it beyond the editor's
reach (the staged blob is immune to a later overwrite). If git does *not* show it, then re-apply. Tell
the user an editor appears to be racing the file. Related: [[verify-load-bearing-before-asserting]],
[[parallel-session-sweeps-uncommitted-work]].
