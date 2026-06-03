---
name: measure-cold-not-warm-windows
description: "On Windows the first (cold) run pays a Defender file-open scan + page faults; a warm re-run hides it, so you optimize the wrong thing or miss a regression. State the regime, measure cold (or N warm separately); don't open a big payload to read small metadata; cache by an immutable key."
metadata: 
  type: feedback
---

A perf number measured on a *warm* second run can be an order of magnitude off the *cold* first run
on Windows: the cold open pays a Defender on-access scan and page faults that the OS file cache then
hides. Benchmarking warm-only makes a real cost invisible (and a real regression look fine); cold-
only overstates steady-state cost. The number is meaningless without knowing which regime produced
it.

**Why:** the cold/warm gap is an environment artifact, not the code; trusting one number without its
regime points optimization at the wrong bottleneck.

**How to apply:** state the regime — measure cold for first-hit latency, report N warm runs
separately for steady-state. Two structural wins that dwarf micro-tuning on Windows: don't open a
large file just to read a small metadata field (the open itself is the cost), and cache metadata by
an immutable key (`name|size|mtime`) so repeats skip the open. Enriches the optimize workflow.
