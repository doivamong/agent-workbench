---
name: verify-load-bearing-before-asserting
description: "Front-load verifying the LOAD-BEARING assumption and the DECIDING AXIS before you assert or recommend; a confident conclusion handed to the user / an adversarial pass / a CI gate as its FIRST verification is how the deepest errors slip through. Confidence is proportional to what you actually checked."
metadata:
  type: feedback
---

A recurring root cause behind several separate failures: confident outputs built on something never
verified. Examples from one investigation — assuming a file "auto-loads" when it did not (caught only
when a runtime check was finally forced); relaying a sub-agent's overclaim as fact; "proving" a
contract on a few clean examples that turned out to be ~33% of the real corpus; declaring a doc fix
"done" while the file still carried the exact false claim; quoting a guessed constant instead of the
measured one. One shape: **conclude first, let someone/something downstream verify.**

**Why:** the verification you skip doesn't disappear — it happens later, after the wrong thing is
recommended or built, when it is costlier to undo. When the user, an adversarial review pass, or a
CI / leak gate is your FIRST verifier, you are shipping unverified analysis and depending on them to
catch it.

**How to apply:** before stating an analysis or recommendation, run a fast self-check: (1) what is the
LOAD-BEARING assumption this rests on, and have I verified it against the running system / the source
itself — not the docs' *claim* about it? (2) what is the DECIDING AXIS, and have I actually evaluated
it (not a cheap proxy like DRY / effort)? (3) is any number measured or guessed? State confidence
proportional to (1)-(3); never call something "genuinely better" before evaluating the axis that
decides it.
