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
- [Parallel session sweeps uncommitted work](parallel-session-sweeps-uncommitted-work.md) — a 2nd session in the SAME tree switches HEAD + sweeps your edits into ITS commit; use separate worktrees.
- [Land work from a shared checkout](land-shared-checkout-work-without-checkout.md) — `checkout -b` moves shared HEAD under a parallel session; land via push + `gh pr --head`, no tree touch.
- [Worktree commit leaks GIT_DIR](worktree-commit-leaks-gitdir-corrupts-shared-config.md) — a LINKED-worktree commit leaks GIT_DIR → tests corrupt the SHARED `.git/config`; strip GIT_* in conftest.
- [git cherry detects squash-merge](git-cherry-detects-squash-merge.md) — already squash-merged? `git cherry origin/main <b>` (all `-` = contained → `-D`); not `--is-ancestor`/subject-match.
- [SKIP a pre-commit hook by id, not name](skip-precommit-hook-by-id-not-name.md) — `SKIP` matches the hook `id` not the display label ('pytest' shown, id `tests`); skip only after verifying green.
- [github anchor slug = double dash](github-anchor-slug-double-dash.md) — GitHub maps each space→dash + strips `&`/`—` without collapsing: `## Status & honesty` → `#status--honesty` (double dash).
- [Moved module breaks sibling import](moved-module-breaks-sibling-import.md) — moving a file breaks its `sys.path.insert` sibling import; a try/except fallback masks it → repoint, verify resolved.
- [posix zombie reap: CI ≠ local](posix-zombie-reap-ci-not-local.md) — a killed child you don't `os.waitpid` is a zombie `os.kill(pid,0)` calls "alive" → false-fails on CI Linux; reap `WNOHANG`.
- [opt-in-dep tests: skipif not importorskip](optin-dep-tests-skipif-not-importorskip.md) — `importorskip` drops a module from `pytest --co` → a count gate drifts CI; use guarded import + `skipif`.
- [launch.json env: PowerShell not cmd](launch-json-env-use-powershell-not-cmd.md) — set a launched Windows env via PowerShell `$env:`, not cmd `set VAR=val &&` (trailing space / exports nothing).
- [PS here-string fails in the Bash tool](ps-here-string-fails-in-bash-tool.md) — `@'...'@` isn't a bash here-string; it mangles commit msgs + breaks `gh --body`; multi-line args → a file + `-F`.

## 🔒 Distilled craft — security (concept-only, from MIT sources)

- [Allowlist external-exec directory](external-exec-allowlist-dir.md) — a tool/hook that execs a binary shouldn't trust `shutil.which`/PATH; accept it only if its dir is on an allowlist (anti hijack).
- [defusedxml for untrusted XML](defusedxml-untrusted-xml.md) — stdlib `xml.etree`/`minidom` is unsafe on hostile XML (XXE/billion-laughs); use `defusedxml` — non-stdlib, awareness-only for core.

## 🧠 Distilled craft — agent reasoning, review & verification

- [Verify load-bearing before asserting](verify-load-bearing-before-asserting.md) — check the load-bearing assumption + deciding axis against ground truth BEFORE you assert/recommend.
- [Harness Read can lie in an editor race](trust-git-diff-over-harness-read-during-editor-race.md) — editor open → an Edit lands but a later Read shows OLD bytes; `git diff` is ground truth.
- [Audit can be right yet misreason](audit-can-be-right-yet-misreason.md) — accurate on FACTS can still be wrong on cause/severity/fix; verify ground truth and correct it.
- [Recommend user-benefit first](recommend-user-benefit-first.md) — rank by real user benefit/output quality FIRST; minimalism is only a tiebreaker, never an excuse.
- [Read the full source before a verdict](read-full-skill-before-verdict.md) — judge an artifact from its full body, not its one-line blurb; guessing causes wrong verdicts.
- [Apply a correction to all instances](apply-correction-to-all-instances.md) — corrected for a bias? scan the rest of the plan for the SAME bias and fix it pre-emptively.
- [Retro: self-audit + pattern synthesis](retro-self-audit-and-pattern-synthesis.md) — lens your OWN process (corrections/reversals) AND synthesize the recurring pattern, not just atoms.
- [gh post-push state is stale](gh-pr-checks-watch-no-checks-race.md) — `--watch` false-greens before CI registers; verify the run conclusion by id + git refs, not gh.
- [Local gate must respect gitignore](local-gate-respect-gitignore.md) — a whole-repo scan hits gitignored local files CI never sees; use `--respect-gitignore`, run the real gate.
- [Public-OK ≠ per-item safe](public-ok-doesnt-waive-leak-check.md) — a blanket "publish it all" authorizes intent, not per-item safety; leak-check each item.
- [Disambiguate tokens before bulk rename](disambiguate-token-meanings-before-bulk-rename.md) — blind find-replace corrupts homonyms; scope to the exact target tokens, grep residuals after.
- [Place a rule where it fires](place-rule-where-it-fires.md) — a path-scoped rule loads only on a matching EDIT; a fileless reasoning lesson belongs in always-loaded CLAUDE.md.
- [Validate a check on the real corpus](audit-check-validate-on-real-corpus.md) — measure a new check on the messy REAL corpus, not clean fixtures; WARN not ERROR if only tidy pass.
- [Synthetic example paths trip leak-scan](synthetic-example-paths-trip-leakscan.md) — an example path in a committed test/doc trips the scanner; use a fake non-home path like `Z:/code/proj_x`.
