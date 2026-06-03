# Memory Index

> This file is loaded into context every session. Keep it small — one pointer line per
> memory, newest/most-relevant grouped at top. The full fact lives in the linked file and
> is read only when relevant. (The user/project/reference entries below are illustrative
> placeholders; the **Distilled craft** section is real, reusable facts shipped with the kit.)

## 🧭 Identity & working style

- [user_example_preferences.md](user_example_preferences.md) — solo dev; small commits; reviews diffs on mobile; reactive over proactive tooling

## 🔴 Hot — repeated corrections / traps

- [feedback_example_validate_at_boundary.md](feedback_example_validate_at_boundary.md) — validate input at the system boundary, not redundantly in every layer
- [feedback_example_verify_before_commit.md](feedback_example_verify_before_commit.md) — always `git diff --stat` + spot-check critical files before committing

## 🟢 Project — ongoing goals / constraints

- [project_example_migration.md](project_example_migration.md) — migrating off the legacy job queue; new code must not add dependencies on it

## 🔗 Reference

- [reference_example_dashboard.md](reference_example_dashboard.md) — where the perf + error dashboards live

## 🛠️ Distilled craft — real cross-stack / Windows / git lessons

- [cd && fail = wrong cwd](cd-and-fail-runs-in-wrong-cwd.md) — `cd X && cmd` with a failing cd runs cmd in the wrong cwd at exit 0; use abs paths or `cd X || exit`.
- [gh licenseInfo unreliable](gh-license-info-unreliable.md) — `gh ... licenseInfo` reports NONE for a repo that HAS a LICENSE; verify via `gh api repos/<o>/<r>/license`.
- [Windows locked-dir → robocopy](windows-locked-dir-rename-robocopy.md) — dir rename "Permission denied" = a handle lock; `robocopy SRC DST /E /MOVE` works where mv/Rename-Item fail.
- [sqlite live read needs mode=ro](sqlite-live-read-mode-ro.md) — default connect() is RW; close can checkpoint the WAL and change the file bytes; open `file:{path}?mode=ro`.
- [Dead feature is a chain with writers](dead-feature-is-a-chain-with-writers.md) — reader-dead ≠ writer-stopped; a scheduled writer keeps filling a table; trace the whole chain first.
- [Measure cold not warm (Windows)](measure-cold-not-warm-windows.md) — a warm re-run hides the cold Defender file-scan; state the regime; don't open big files for small metadata.
- [Security feature can be theater](security-feature-can-be-theater.md) — a 'verify'/'tamper-evident' feature can run yet assert nothing; grep the verifier + trace both sides are live.
- [.bat → PowerShell, not cmd /c](bat-from-agent-use-powershell-not-cmd.md) — `cmd /c "X.bat"` from Bash can banner + exit 0 while the body never runs; use `& "X.bat"` + verify a side effect.
- [Parallel-session git hygiene](parallel-session-git-hygiene.md) — shared worktree: index/stash race clobbers staged work; squash-merge → dup-hash → `git rebase --onto` + re-test.
- [Headless Python: stdout is None](headless-python-stdout-none-guard.md) — pythonw/service sets sys.stdout=None; `.reconfigure()` crashes at import; guard `if sys.stdout is not None`.
- [Restart didn't take? PID + elevation](restart-didnt-work-check-pid-and-elevation.md) — prove the old process died: old PID still holds the port + a non-admin shell can't kill a SYSTEM process.
- [requirements.txt ≠ deployed](requirements-txt-not-auto-installed.md) — a manifest bump doesn't pip-install in prod; new import = ModuleNotFoundError only in prod; name the deploy step.
