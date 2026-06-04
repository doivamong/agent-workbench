---
name: synthetic-example-paths-trip-leakscan
description: "A synthetic EXAMPLE path in a committed test / docstring still trips a leak scanner — a realistic one hits both a denylist (a real machine path) AND path heuristics (a home-path shape); use a clearly-fake non-home path like Z:/code/proj_x. A deliberately secret-SHAPED fixture needs the NAMED `# leak-scan: ignore[name]` opt-out, not a bare one."
metadata:
  type: feedback
---

Writing a unit test for path-mangling, I used the real working path in a committed test + docstring,
so the leak denylist blocked the push (golden rule #1: no machine paths). My first "fix", a home-shaped
path, then tripped the `unix_home_path` heuristic. Only a clearly-synthetic, non-home-looking path
(`Z:/code/proj_x/sub`) passed both.

**Why:** the leak scanner catches BOTH named machine paths (denylist) AND home-directory SHAPES (a
heuristic for any path under the `/Users` or `/home` prefix). An "example" path that looks like a real
path or a home dir is indistinguishable from a real leak to the scanner.

**How to apply:** for any path used purely as an EXAMPLE in a committed test, docstring, or doc, use a
path that is obviously fabricated and not home-shaped — e.g. `Z:/code/proj_x/sub` — never the real
working / cwd path and never a real home directory. And when a fixture must contain a secret-SHAPED
string on purpose (e.g. an AWS-key pattern to test the scanner itself), a *bare* `# leak-scan: ignore`
will NOT silence a HARD pattern — use the NAMED opt-out `# leak-scan: ignore[aws_access_key]`.
