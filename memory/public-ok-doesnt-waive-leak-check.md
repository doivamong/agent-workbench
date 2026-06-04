---
name: public-ok-doesnt-waive-leak-check
description: "A user's blanket 'publish it / it's all OK to be public' does NOT waive golden-rule-#1: each item still needs its own leak/secret/identifier check. Triage per-item and flag the leakers (machine paths, a paid-product ref, private internals) instead of executing the blanket instruction."
metadata:
  type: feedback
---

When a user says "publish all of X, it's fine to be public," that authorizes the *intent* — it does
**not** discharge your duty to leak-check each item against golden-rule #1 (no secrets / identifiers /
absolute machine paths). Over-compliance is the trap: executing "make it public" literally would push
the items that genuinely must not ship. (Lived it: a blanket "these are OK to publish" covered facts
holding an absolute machine path to a *paid* commercial product, a private internal pipeline, and
upstream-codebase internals — all golden-rule-#1 violations.)

**Why:** a blanket *authorization* is not a blanket *safety clearance*. The human approves the goal,
not each item; the leak / identifier gate is the agent's job and it is per-item. Publishing is
irreversible, so one missed item is a real, public leak.

**How to apply:** read "make it public" as "publish the **safe subset**." Triage each item, run the
leak check (`leak_scan` / the golden-rule list), and **flag the ones that must stay private** with
evidence — do not push them just because you were told "all of it is fine." Re-confirm the exclusions
with the user.
