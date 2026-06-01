---
name: feedback-example-verify-before-commit
description: Always review staged changes before committing — diff stat plus a spot-check.
metadata:
  type: feedback
---

Before every commit, run `git diff --cached --stat` and open the most critical changed file
to spot-check it. Don't commit blind.

**Why:** It's the cheapest place to catch a stray debug print, a file staged by accident, or
a half-finished edit — far cheaper than reverting after the fact.

**How to apply:** Make it a reflex: stage → `git diff --cached --stat` → eyeball the list for
anything unexpected → open one or two key files → commit.

Related: [[user-example-preferences]]
