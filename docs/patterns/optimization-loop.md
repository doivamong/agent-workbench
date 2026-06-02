# The metric-driven optimization loop — let a number decide each change

"Make it faster / lighter / smaller" invites the most expensive habit in performance work:
changing code because it *looks* slow. You spend an afternoon on the part that was 3% of the
cost, trade readability for a change you can't prove helped, and have no way to say whether you
finished. This page is the disciplined alternative: a loop where a **real measurement**, not
intuition, decides every change — and version control makes every attempt free to undo.

It is the concrete execution counterpart of the *measure before you optimize* default in
[`development-rules.md`](../development-rules.md).

## The loop

1. **Name the metric and the command that produces it.** One number, emitted by one repeatable
   command: request latency in ms, test-suite wall-clock, coverage %, binary size, peak memory.
   **If you can't name the command that prints the number, stop here** — the goal isn't
   measurable yet, and this loop does not apply to it (see *Honest limits*).
2. **Baseline.** Run the command on a clean tree and record the number. This is the only thing
   every later change is judged against.
3. **Find the top contributor.** Profile or instrument to see *where* the cost actually sits —
   most of it usually lives in a few places. Aim the next change there, not at whatever is
   easiest to edit.
4. **Make exactly one change.** One isolated edit per iteration. Change several things at once
   and you can't attribute the delta to any of them — you've measured nothing.
5. **Re-measure with the same command.** Same inputs, same environment, so the two numbers are
   comparable.
6. **Keep or revert — through version control.**
   - Better by a margin that clears the noise *and* is worth its readability cost → **commit it**.
   - No better, worse, or a real win too small to justify the complexity → **`git restore` /
     revert it** and try the next idea.
7. **Repeat until the target or diminishing returns.** Stop when you hit the number you set, or
   when the next change buys less than it costs.

## Why version control is the spine

The loop only works because each attempt is a **reversible experiment**. The working tree is a
scratchpad: try a change, measure, and if it doesn't earn its place, throw it away cleanly with
no residue. Without that, failed attempts silently accumulate as half-finished "improvements"
you can no longer disentangle — and the fear of losing work pressures you into keeping changes
that didn't actually help. Commit only the winners; the number is the gate.

```
metric: <command that prints one number>     target: <value>

| attempt | change                | before | after | kept? |
|---------|-----------------------|--------|-------|-------|
| base    | —                     |   —    | 2800  |  —    |
| 1       | hoist work out of loop| 2800   |  410  |  yes  |
| 2       | add a cache layer     |  410   |  395  |  no (3% for real complexity) |
| 3       | batch the I/O         |  410   |  120  |  yes  |
```

## Honest limits

- **Only for objectively measurable goals.** If "better" can't be reduced to a number a command
  prints, this loop lends false rigor to a judgment call. Readability, API ergonomics, and
  "cleaner" are decided by review, not by this loop.
- **The metric is a proxy — beware optimizing the number instead of the thing** (Goodhart's law).
  Coverage % rises with assertion-free tests; latency drops if you quietly skip a correctness
  check. Keep a **guard metric you never trade away** (the test suite stays green) and watch it
  every iteration.
- **A noisy measurement lies.** Warm vs cold caches, background load, and tiny sample sizes
  produce deltas that aren't real. Measure on a stable setup and re-run to confirm a change
  before you trust it.
- **It does not make the change for you.** This is discipline around *your* edits plus a safety
  net — not an autonomous self-improving system. A human or agent still writes each change and
  judges the trade-offs; the loop just refuses to let an unmeasured one through.

## Banned behaviours

- Claiming something was "optimized" with no before/after number.
- Adding a cache (or any complexity) before profiling tells you where the cost is.
- Chasing a contributor that's a small fraction of the total — the 3% is rarely where the win is.
- Trading readability for an improvement below your noise floor.
- Changing several things in one iteration, so no single change can be credited or blamed.

## Codifying it

The two halves that are mechanical can be enforced mechanically rather than remembered: wire the
**measure command** and the **guard metric** ("tests still pass") into CI so a regression on
either is caught on the diff, and record the loop itself as a path-scoped rule (see
[`lessons-as-rules.md`](../lessons-as-rules.md)) so the next person reaches for *measure → change →
keep/revert* by default instead of optimizing blind.
