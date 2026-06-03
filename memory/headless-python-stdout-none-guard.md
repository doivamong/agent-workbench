---
name: headless-python-stdout-none-guard
description: "On Windows a headless Python runtime (pythonw.exe, a service host) sets sys.stdout/sys.stderr to None; an unguarded `sys.stdout.reconfigure(encoding='utf-8')` then raises AttributeError at IMPORT time. Guard `if sys.stdout is not None` (each stream separately) before reconfiguring."
metadata: 
  type: feedback
---

A common top-of-module idiom — `sys.stdout.reconfigure(encoding="utf-8")` to force UTF-8 output —
crashes when Python runs headless: `pythonw.exe`, a Windows service host, or some embedded runtimes
set `sys.stdout` and `sys.stderr` to `None`. The call then raises `AttributeError: 'NoneType' object
has no attribute 'reconfigure'` at **import time**, before any of your code runs — so it looks like a
mysterious startup crash, not an I/O concern.

**Why:** it fires at import, in an environment (headless) you rarely test interactively, and the
traceback points at the reconfigure line rather than the real cause (no stdout stream exists). Easy to
lose an hour to.

**How to apply:** guard each stream separately before touching it —
`if sys.stdout is not None: sys.stdout.reconfigure(encoding="utf-8")` (same for `sys.stderr`). Apply the
same care to any module-level access to `sys.stdout`/`sys.stderr` in code that might run under
`pythonw` or as a service.
