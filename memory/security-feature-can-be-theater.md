---
name: security-feature-can-be-theater
description: "A feature named 'verify'/'tamper-evident'/'audit' can run yet assert nothing — a no-op replay, a value compared to itself, a docs claim with no backing code — giving false confidence. Grep the verifier and trace that BOTH compared sides come from independent live sources."
metadata: 
  type: feedback
---

A security or integrity feature can be *theater*: the code path executes and looks reassuring but
performs no real check — a "replay/verify" that compares a value to itself, a "tamper-evident chain"
the docs describe but no code computes, a guard that returns before it asserts — or one that *does*
assert but on the wrong axis (flagging a decrease while the real threat is an increase: green, yet
zero real coverage). Tests and demos pass
because they exercise the happy path; the protection is absent exactly when it would matter.

**Why:** the feature's *name* and its docs become the evidence, not its behaviour — the most
dangerous kind of false confidence, because everyone downstream assumes it is covered.

**How to apply:** verify the mechanism, not the label — grep for the verifier/asserter and trace
that **both** inputs to the comparison come from independent live sources (not one value compared to
itself, not a constant). Pair with the adversarial review pass: assume the guard is a no-op until you
have read the assertion that proves otherwise. And confirm the guard watches the threat's real
*direction* — map threat→direction and check the allow-branch cannot pass it.
