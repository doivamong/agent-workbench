---
name: example-optimize
description: >
  WHAT: make code measurably faster (or lighter) with a disciplined loop — set a baseline,
  measure to find the real bottleneck, fix the top one, re-measure, and record a before/after
  table — so a change is kept only when a number says it helped.
  USE WHEN: a concrete performance goal on real code ("this is too slow", "optimize X", "cut the
  p95 latency / memory", "speed up the import"), where you can measure before and after.
  DO NOT TRIGGER: "tidy this up / simplify" with no speed goal (that is a review/simplify skill);
  a correctness bug (that is a debug skill); micro-tuning with no measurable target or baseline.
tier: feature
oversight: low
---

# Example: Optimize (measure-driven)

> **Announce on activation:** "Using example-optimize — baseline first, then measure → fix → verify."

If you can't state the goal as a number ("p95 under 200 ms", "peak RSS under 400 MB"), stop and
define that first — optimization without a metric is guessing.

## Scope

- **Does:** drive a measure → fix-one → re-measure loop and force a before/after record.
- **Does NOT:** ship a profiler (use `cProfile` / `perf` / `timeit` / your bench harness), guarantee
  a speedup, or pick the target for you. The thresholds here are per-app, per-workload heuristics.

## Process

1. **HARD GATE: baseline before any change.** Record the current number on representative data, with
   the exact command. No baseline → you can't tell improvement from noise. Run it 2–3×; if it swings
   wildly, your measurement is too noisy to act on — fix that first.
2. **Measure where the time goes.** Profile and rank the hotspots by actual cost. Intuition about
   "the slow part" is wrong often enough to waste the effort.
3. **Fix the single biggest one.** One change per loop, so the next measurement attributes the delta.
4. **Re-measure, keep or revert.** Same command. If it didn't beat the baseline past the noise,
   **revert it** (`git checkout`) — a change that doesn't move the number is just complexity. If it
   helped, that's the new baseline; loop.
5. **Record a before/after table** on every shipped win, so it's legible and reversible:

   | Metric | Before | After | How measured |
   |---|---|---|---|
   | p95 latency | 480 ms | 190 ms | `python -m bench api --n 1000` |

See [`docs/patterns/optimization-loop.md`](../../../docs/patterns/optimization-loop.md) for the
underlying pattern.

## Banned behaviors

- **No fix without a baseline** — you can't prove it helped.
- **No "while I'm here" rewrite** — optimizing isn't a licence to refactor untouched code.
- **No micro-optimization the profiler didn't point to** — it trades readability for noise.
- **No keeping a change that didn't beat the noise** — revert it.

## Honesty / limits

This skill ships no measurement engine and guarantees no speedup — it enforces discipline around
whatever profiler you use. Numbers are only as good as the input: optimizing against
unrepresentative data can make production slower. "It feels faster" is not a metric.
