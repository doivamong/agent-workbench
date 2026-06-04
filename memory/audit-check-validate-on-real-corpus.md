---
name: audit-check-validate-on-real-corpus
description: "Validate a new lint / identity check against the messy REAL corpus, not clean self-authored fixtures — a contract that passes 5/5 tidy examples can fail the real distribution badly (~33% here), so it ships as WARN not ERROR."
metadata:
  type: feedback
---

When designing a `name == kebab(filename)` identity contract for a memory linter, the design pass
"proved" feasibility on a handful of clean, self-authored example files (all passed) and proposed it as
an **ERROR**. An adversarial check measured it against the real, large corpus: only ~33% satisfied it —
most `name` fields were free-text titles (spaces, caps, non-ASCII) the contract can't bind. It shipped
as **WARN, never ERROR**. A concrete instance of the measurement-honesty traps "n=1 false-zero" and
"selection-biased %": a contract validated only on clean fixtures, not on the real distribution it must
run against.

**Why:** a check tuned on tidy fixtures that fires ERROR on a real corpus is false confidence — it
blocks a legitimate migration with a wall of false errors, the exact stumble an honesty-first kit
should forbid.

**How to apply:** before deciding **ERROR vs WARN** for any new audit / lint / identity check, run it
against the **largest, messiest real corpus you can reach** and measure the true pass rate. If a
contract holds only on clean fixtures, demote it to WARN or quote the real denominator. Don't round a
5/5-fixture result up to "the convention holds."
