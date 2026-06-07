---
name: moved-module-breaks-sibling-import
description: "Moving a module silently breaks a sibling import done via sys.path.insert(__file__-dir); a try/except fallback masks it with a re-derived value — resolve the sibling path explicitly and verify the import resolved, not the value."
metadata: 
  type: feedback
---

A module reused a shared constant with `sys.path.insert(0, str(HERE)); from sibling_mod import CONST`
(HERE = the file's own dir), plus an `import other_sibling` inside a function. When the file was
**moved** to a deeper package, `HERE` changed — the sibling modules were no longer on the path, so
BOTH imports fell through their `try/except` to a hardcoded fallback. No error, no log: the code kept
running with a re-derived constant instead of the real one. A review flagged the first sibling; the
second (imported deeper) was the one most reviewers missed. Fix: compute the siblings' REAL location
relative to the moved file (`_SIBS = HERE.parent.parent / "their_dir"`) and insert THAT.

**Why:** a broad `try/except` fallback turns a broken-after-move import into a plausible-but-wrong
value — false confidence with no signal. The trap is worse when the fallback equals the real value on
the dev machine, so a value-check would NOT catch it; only the import resolving (or not) reveals it.

**How to apply:** when moving a module that imports siblings via `sys.path.insert(<its-own-dir>)`, the
import target moves too — repoint `sys.path` to the siblings' real location explicitly. Verify the
import actually RESOLVED (e.g. `assert "sibling_mod" in sys.modules`), not that a value exists; a
silent fallback to a re-derived constant is exactly the false-confidence trap. See
[[verify-load-bearing-before-asserting]].
