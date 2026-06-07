---
name: launch-json-env-use-powershell-not-cmd
description: "To set an env var for an agent-launched Windows process (e.g. a VS Code launch.json), use a PowerShell runtimeExecutable with `$env:VAR='val'; …` — a cmd `/c \"set VAR=val && …\"` wrapper captures the trailing space (wrong value) and the quoted `set \"VAR=val\"&&` form can export nothing (process runs inert)."
metadata: 
  type: reference
---

Setting an env var inline via a **cmd** wrapper when an agent launches a Windows process is a trap
(observed setting a password env var for a debug launch):

- `cmd /c "set VAR=val && python …"` — `set` captures **everything up to the `&&`, including the
  trailing space**, so `VAR` becomes `"val "` → the value is silently wrong.
- `cmd /c "set \"VAR=val\"&&python …"` (quoted, no space) — in some harnesses the var is **not
  exported at all**, so the process starts as if it were unset (the feature came up inert).
- `powershell -NoProfile -Command "$env:VAR='val'; python …"` — **reliable**; the value is exactly
  `val`.

How to apply: for a launch.json (or any agent-spawned Windows process) that needs an env var, use a
**PowerShell** `runtimeExecutable` with `$env:VAR='…'; <cmd>`, not a cmd `set …&&` wrapper, and verify
the process actually saw it (a startup log line), not just that it launched. Same "prefer PowerShell
over cmd from an agent on Windows" spine as [[bat-from-agent-use-powershell-not-cmd]] (there a `.bat`
body is silently skipped; here an env var is silently wrong or unset).
