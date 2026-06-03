---
name: cd-and-fail-runs-in-wrong-cwd
description: "A `cd X && cmd` (esp. backgrounded) where cd fails silently runs cmd in the DEFAULT cwd at exit 0 — no error — so the command lands on the wrong repo/dir and its result is meaningless."
metadata: 
  type: feedback
---

`cd <dir> && cmd` (or `cd <dir>; cmd`) does NOT guarantee `cmd` runs in `<dir>`. If `<dir>` does
not exist, `cd` fails but `cmd` still runs — in the shell's default working directory — and the
whole line often still exits 0. Backgrounded or piped, the failure is invisible: e.g. a background
`cd <new-worktree> && pytest` silently runs the suite against the *original* repo, and the green
result is meaningless.

**Why:** it is a silent failure — wrong context, no error signal, a falsely-passing result — which
is exactly the class this kit exists to catch. (Seen for real: a backgrounded pytest silently ran
against the original repo instead of the intended worktree.)

**How to apply:** prefer absolute paths over `cd` for one-shot commands; when you must change dir,
use `cd <dir> || exit 1` (POSIX) or `Set-Location <dir> -ErrorAction Stop` (PowerShell) so a failed
cd aborts instead of running `cmd` in the wrong place. Re-check cwd for any backgrounded command.
