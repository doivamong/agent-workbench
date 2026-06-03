---
name: restart-didnt-work-check-pid-and-elevation
description: "'I restarted it but the change didn't take' on Windows — before blaming the code, verify the OLD process actually died: the port may still be held by the old PID (Get-NetTCPConnection -LocalPort), and a non-elevated shell cannot kill a SYSTEM/elevated process, so the new instance never really took over."
metadata: 
  type: feedback
---

When a restart "didn't apply the change" on Windows, the code is often innocent. Two operational
causes masquerade as a code bug: (1) the **old process is still alive** holding the port — the new
instance bound nothing (or a different port) and you're still talking to the old binary; (2) you lack
**elevation** — a non-admin shell's `taskkill` / `Stop-Process` cannot terminate a process running as
SYSTEM or another elevated user, so the kill "succeeds" quietly while the old PID lives on.

**Why:** you re-read the code hunting for why the change didn't take, when the real issue is that the
old process is still serving — a wrong-layer hunt that burns time.

**How to apply:** before debugging the code, prove the old process died. Find who owns the port:
`Get-NetTCPConnection -LocalPort <port> | Select OwningProcess` → `Get-Process -Id <pid>`. If it's the
stale PID, kill it (elevate the shell if it's SYSTEM/elevated), confirm the port is free, then restart
and re-verify the change landed.
