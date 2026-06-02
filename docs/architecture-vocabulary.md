# A small vocabulary for architectural quality

You can't review what you can't name. This is a tiny, domain-free vocabulary for talking about
*structural* quality — the kind a test suite won't catch — so a design discussion has words sharper
than "this feels messy". Use it in a review, a plan, or the Architecture lens of a stress-test. It's
a vocabulary, **not a checker**: it sharpens judgement, it doesn't replace it.

## Deep vs shallow module

A **module** is anything with an interface and a hidden implementation (a function, a class, a
service). Its quality is the ratio of the two:

- A **deep** module hides a lot of complexity behind a small interface — much capability, little
  surface to learn. `read(file) → bytes` hides buffering, syscalls, and encoding behind two words.
- A **shallow** module exposes nearly as much surface as it implements — a thin wrapper whose
  signature is as complicated as just doing the thing yourself. It adds a name without subtracting
  complexity.

Prefer deep. When you add a parameter, an exception, or a return shape, you're widening the
interface — charge it against the complexity it actually hides.

## Seam

A **seam** is a place where you can change behaviour *without editing the code in place* — by
passing a different argument, subclass, or implementation. Seams are what make code testable
(swap the real clock/network for a fake at the seam) and extensible (add a case without touching
the dispatcher). "Hard to test" usually means "no seam here" — the fix is to introduce one, not to
mock internals.

## The deletion test

To gauge coupling, ask: **if I deleted this, what would break, and how hard would it be to find
out?**

- Nothing breaks → it may be dead (confirm with a real [dead-code
  audit](../.claude/skills/example-dead-code-audit/SKILL.md), which guards against false positives).
- One obvious thing breaks → healthy coupling.
- You can't tell without running everything → it's too entangled; that opacity *is* the problem.

## Interface as test surface

The public interface is also the test surface: tests written against it survive refactors, tests
written against internals shatter on them. So design the interface to be the thing worth asserting
on — if it's awkward to test through the front door, that's a design signal, not a testing problem.
This is the same idea [`example-tdd`](../.claude/skills/example-tdd/SKILL.md) leans on.

## Honest limit

These are lenses, not laws. "Deep", "shallow", and "too coupled" are judgement calls with no
threshold a tool can check; the vocabulary makes the judgement *discussable*, not automatic. The
deep-module framing is from Ousterhout's *A Philosophy of Software Design*; "seam" is from Feathers'
*Working Effectively with Legacy Code* — both books, cited as concept sources, not redistributed.
