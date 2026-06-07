---
name: worktree-commit-leaks-gitdir-corrupts-shared-config
description: "Committing from a LINKED git worktree runs the pre-commit test hook with an absolute GIT_DIR exported by git; tests that spawn their own `git init`/`git config` subprocesses inherit it, so their writes land in the SHARED .git/config — flipping core.bare=true (every work-tree op then fails 'must be run in a work tree') and overwriting user.name/user.email. A normal checkout exports a RELATIVE .git so it's CI-safe; only worktree commits leak. Defend at the suite level (strip GIT_* in a conftest autouse fixture); otherwise use a fresh clone, `pre-commit run --all-files`, or SKIP the test hook."
metadata: 
  type: feedback
---

When you `git commit` from a **linked worktree**, git exports `GIT_DIR` as an **absolute** path
(`<main>/.git/worktrees/<name>`) to the pre-commit hooks. A pytest hook then runs tests that spawn
their own git repos via `subprocess.run(["git", ...], cwd=tmp_path)` — and those inherit the absolute
`GIT_DIR`, so git ignores `cwd` and operates on the worktree's gitdir instead of `tmp_path`.
Consequences observed (cost ~an hour of thrash):

- a test fixture's `git config user.email …` wrote into the **shared** `.git/config`, silently
  overwriting the real `user.name`/`user.email` for the whole repo.
- a test's `git init` flipped **`core.bare=true`** in the shared config → every subsequent work-tree
  op (in the worktree AND the main tree) failed `fatal: this operation must be run in a work tree`,
  and uncommitted edits got swept on the next checkout.
- `git add`/`git commit` in those tests failed (no `GIT_WORK_TREE`), so no junk commits — the damage
  was config-only, but config damage is invisible until a later commit is mis-authored.

A **normal checkout** exports a *relative* `GIT_DIR=.git`, which resolves per-`cwd`, so the same tests
pass — which is why CI and a normal commit are fine and only the worktree commit breaks.

**Why:** the failure looks like "my code broke 4 unrelated tests" but it's the harness leaking git
state; chasing the tests (or blaming a parallel session's tool with zero evidence) wastes time and
propagates a false accusation. See [[verify-load-bearing-before-asserting]],
[[audit-can-be-right-yet-misreason]].

**Root fix (best):** give the test suite a **suite-wide autouse fixture** that `monkeypatch.delenv`s
the repo-location vars for EVERY test — `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`,
`GIT_OBJECT_DIRECTORY`, `GIT_NAMESPACE`, `GIT_PREFIX`. Do it once in `conftest.py`, not per test file:
the trap recurs whenever a *new* test that shells out to git forgets to strip them. With that fixture
in place a plain `git commit` from a linked worktree is safe — no `--no-verify` needed.

**Fallback (suite not hardened):** don't run the full pytest pre-commit hook *from a linked worktree*.
Either (a) author the change in a **fresh `git clone`** (own config, immune), or (b) verify with
`pre-commit run --all-files` (does NOT export GIT_DIR — passes every time) **then commit with the hook
SKIPPED** — `git commit --no-verify` or `SKIP=<hook-id> git commit`. CRITICAL: a *plain* `git commit`
after the manual run still RE-RUNS the hook and re-corrupts. `--no-verify` is justified here precisely
because the gate was already run green out-of-band and running it inline corrupts the repo — note it
in the commit body.

**Recovery if it already fired:** restore the SHARED config in both views —
`git config core.bare false`, `git config user.name "<you>"`, `git config user.email "<you>"`
(and the same via `git --git-dir=<main>/.git config ...`); the failed commit makes no commit, so
staged changes survive; re-commit with `--no-verify`. After ANY worktree/parallel-session git
trouble, **audit `git config --local --list`** (esp. `user.*`, `core.bare`) and check recent commit
authors before trusting the repo. Kin: [[parallel-session-sweeps-uncommitted-work]],
[[parallel-session-git-hygiene]].
