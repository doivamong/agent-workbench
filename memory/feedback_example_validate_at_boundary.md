---
name: feedback-example-validate-at-boundary
description: Validate input at the system boundary, not redundantly in every internal layer.
metadata:
  type: feedback
---

Validate untrusted input once, at the system boundary (request handler, CLI entry, external
API response). Trust it on internal calls below that point.

**Why:** Re-validating the same data in every layer adds noise, drifts out of sync, and
hides where the real contract is. The boundary is the one place an attacker's input enters.

**How to apply:** Put the guard in the handler/entrypoint. Below it, assume the data is
well-formed. If you find yourself writing the same null-check three layers deep, delete the
inner two and trust the boundary.

Related: [[feedback-example-verify-before-commit]]
