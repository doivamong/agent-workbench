---
name: audit-can-be-right-yet-misreason
description: "An external audit/review can be accurate on the FACTS yet wrong on cause, severity, or remedy — your job reviewing it is to verify against ground truth and CORRECT the reasoning, not confirm it. \"Matches the reference\" is not the same as \"is correct\"."
metadata:
  type: feedback
---

An external audit handed to you can have all its FACTS check out yet be wrong in its *reasoning*, in
three recurring ways: (1) it treats "the reference / dogfooded setup does X" as proof "the target
should do X" — but tracing the dependency chain can show X relies on parts that never reach the target
context, so doing X there would be the bug, not the fix; (2) it counts ONE root cause as several
separate HIGH findings, inflating severity; (3) its recommended FIX is itself wrong (e.g. swapping a
correct "not applicable here" marker for the wrong one). Often only a fraction of the findings are
genuine.

**Why:** the easy, default move on an audit is to confirm it — it already did the work and sounds
authoritative. But an audit handed to you unverified is just another unchecked claim; its facts and
its inferences fail independently, and the inferences (cause / severity / fix) are where it most often
slips while the numbers stay right. Confirming a wrong inference propagates it with extra credibility.

**How to apply:** when asked to evaluate an audit / review / external assessment, verify against the
running system or the source, not the audit's framing. For each finding ask: is "matches the
reference" being conflated with "is correct"? Trace whether the thing's dependency chain actually
reaches the target context before calling a gap a bug. Watch for one root cause double-counted as
several findings (recompute the severity profile yourself). And sanity-check each recommended FIX — a
plausible-sounding remedy can itself be the bug. Spawn independent verifiers for breadth, but verify
the load-bearing claim yourself.
