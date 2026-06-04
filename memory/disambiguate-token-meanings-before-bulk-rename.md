---
name: disambiguate-token-meanings-before-bulk-rename
description: "Before a repo-wide token rename / find-replace, enumerate the token's DISTINCT meanings in the repo — a homonym is silently corrupted by a blind replace. Scope the replace to the exact target tokens, exclude the rest, and grep for residuals after."
metadata:
  type: feedback
---

A repo-wide rename treats one string as one concept, but a token often means several things. In one
`example-*` -> `awb-*` prefix rename, "example" had THREE distinct meanings: the `example-*`
folder-name prefix (the rename target), the `*_example_*` sample files (a demonstration of
categories), and the `examples/` runnable-demo dir (a fixture). Only the first should change; a naive
`sed s/example/.../` would have corrupted the other two silently.

**Why:** find-replace operates on the string, not the meaning. A homonym of the target token gets
swept up with no error — the change "succeeds," the corruption is silent, and a green test suite won't
catch a mangled prose phrase or a fixture path. The cost lands later, when a sample file or a demo path
is quietly wrong.

**How to apply:** before a bulk rename, (1) enumerate the token's distinct meanings (grep broadly, read
a sample of each cluster); (2) scope the replace to the EXACT target tokens — here the specific
`example-<name>` slugs, not the bare word `example`; (3) explicitly exclude the homonym clusters and
any history / records you must not rewrite; (4) dry-run, then grep for residuals after applying. A
linter and a review won't flag a homonym corruption — only the up-front enumeration does.
