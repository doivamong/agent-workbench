---
name: bat-from-agent-use-powershell-not-cmd
description: "On Windows, invoke a .bat from an agent via PowerShell `& \"X.bat\"` — NOT a Bash `cmd /c` wrapper, which can print the batch's banner and exit 0 while the body never runs (silent exit-0 success)."
metadata: 
  type: feedback
---

Calling a Windows `.bat` through a Bash `cmd /c "X.bat"` wrapper (the reflex on a POSIX-shell tool)
can print the batch file's banner / echo output and return **exit 0** while the actual body never
executes — a silent success. The agent sees a clean exit and plausible output, and moves on; nothing
ran.

**Why:** exit 0 plus visible banner text reads as "it worked," so the failure is invisible — the
exact green-but-did-nothing class this kit hunts. The mechanism differs from a failed `cd`
([[cd-and-fail-runs-in-wrong-cwd]]): there the command runs in the wrong directory; here the wrapper
swallows the batch body entirely.

**How to apply:** on Windows invoke a `.bat` via PowerShell — `& "C:\path\to\X.bat"` — and verify a
real side effect (a status line, an output file, a changed value), never the exit code alone. Don't
trust a printed banner as proof the script body ran.
