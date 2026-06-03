---
name: gh-license-info-unreliable
description: "`gh repo view --json licenseInfo` reports NONE even when the repo HAS a LICENSE — it is heuristic. Verify with `gh api repos/<owner>/<repo>/license`, which reads the actual file and returns the SPDX id."
metadata: 
  type: feedback
---

`gh repo view <repo> --json licenseInfo` (and the web "License: —" label) is heuristic: it can
return NONE / null for a repo that ships a perfectly valid LICENSE, misclassifying its terms. This
silently corrupts any "is this safe to reuse?" decision that trusts it.

**Why:** an external-reuse decision (PORT vs SALVAGE, attribution, compatibility) hinges on the
license; a false NONE makes a permissively-licensed repo look unlicensed (and the reverse is just
as costly). Trust-but-verify any license claim before acting on it.

**How to apply:** confirm with the authoritative endpoint `gh api repos/<owner>/<repo>/license` —
it reads the actual LICENSE blob and returns the SPDX id. When two sources disagree, the file-
reading endpoint wins. Use this in the external-reference workflow before classifying anything.
