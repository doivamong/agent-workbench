---
name: local-gate-respect-gitignore
description: "A whole-repo pre-commit gate (leak/lint) scans the LOCAL working tree, which carries gitignored files (handovers, scratch) that CI never sees on its fresh checkout — so the local gate false-fails where CI is green. Use --respect-gitignore (or scan staged/tracked only), and run the real gate before trusting it."
metadata:
  type: feedback
---

A pre-commit hook that scans the *whole repo* (e.g. `leak_scan . --fail-on-find`) runs against your
**local working tree** — which holds gitignored files (handovers, scratch notes, local caches) that
**CI never sees**, because CI runs on a fresh checkout where those files don't exist. So the same gate
is **green in CI but red locally** (or vice-versa): turning on pre-commit suddenly blocks every commit
on findings inside files that never ship. (Lived it: a pre-commit leak hook flagged ~15 gitignored
handover files; CI was green because its clean checkout had none.)

**Why:** it is a silent divergence between "the gate locally" and "the gate in CI" — same command,
different file set, opposite result. A gate never run on a real working tree can be *code-complete but
not operational*: it ships, looks fine, and blocks the first real commit.

**How to apply:** make a whole-repo local gate scan **what actually ships** — add `--respect-gitignore`
(skip gitignored files; they never publish) or scan only staged / tracked files. And before trusting
any local gate, **run the real thing** (`pre-commit run --all-files`) on a populated working tree
rather than reasoning about it.
