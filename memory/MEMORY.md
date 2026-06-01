# Memory Index

> This file is loaded into context every session. Keep it small — one pointer line per
> memory, newest/most-relevant grouped at top. The full fact lives in the linked file and
> is read only when relevant. (These entries are illustrative placeholders.)

## 🧭 Identity & working style

- [user_example_preferences.md](user_example_preferences.md) — solo dev; small commits; reviews diffs on mobile; reactive over proactive tooling

## 🔴 Hot — repeated corrections / traps

- [feedback_example_validate_at_boundary.md](feedback_example_validate_at_boundary.md) — validate input at the system boundary, not redundantly in every layer
- [feedback_example_verify_before_commit.md](feedback_example_verify_before_commit.md) — always `git diff --stat` + spot-check critical files before committing

## 🟢 Project — ongoing goals / constraints

- [project_example_migration.md](project_example_migration.md) — migrating off the legacy job queue; new code must not add dependencies on it

## 🔗 Reference

- [reference_example_dashboard.md](reference_example_dashboard.md) — where the perf + error dashboards live
