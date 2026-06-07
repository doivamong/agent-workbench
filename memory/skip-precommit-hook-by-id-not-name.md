---
name: skip-precommit-hook-by-id-not-name
description: "pre-commit's SKIP env var takes the hook's `id` from .pre-commit-config.yaml, NOT its display name. A hook can show as 'pytest' in output while its id is `tests` — so `SKIP=pytest git commit` silently runs it anyway. Read the config for the real id (`SKIP=tests`), and skip a single hook only after verifying it green out-of-band (e.g. `pre-commit run --all-files`)."
metadata: 
  type: feedback
---

To skip exactly one pre-commit hook at commit time, `SKIP=<id>` must use the hook's **`id`** as
declared in `.pre-commit-config.yaml`, not the human-readable name shown in the hook's run output.
They often differ: a hook printed as `pytest......Passed/Failed` had `id: tests`, so `SKIP=pytest git
commit` did nothing and the hook still ran (and failed). `SKIP=tests` is what skips it.

**Why:** the run output's left-hand label is the hook's `name:` (cosmetic); `SKIP` matches on `id:`.
Guessing the label wastes a commit attempt and looks like "SKIP doesn't work."

**How to apply:** open `.pre-commit-config.yaml`, find the hook's `id:`, and use that. Skip a hook
ONLY when you've verified it green another way (`pre-commit run --all-files` does not export the
commit-hook env, so it's a clean check) — and never reach for SKIP to dodge a *real* failure. In a
linked worktree the cleaner fix is usually not to skip at all but to commit from a fresh clone — see
[[worktree-commit-leaks-gitdir-corrupts-shared-config]].
