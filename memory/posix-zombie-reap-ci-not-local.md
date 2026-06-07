---
name: posix-zombie-reap-ci-not-local
description: "A POSIX child you SIGTERM/kill but don't os.waitpid becomes a ZOMBIE that os.kill(pid,0) still reports as alive — so a 'has it died?' loop false-fails and stop()/terminate() returns failure. It passes on local Windows (no zombies) and fails ONLY on CI Linux — the classic local≠CI gap. Reap with os.waitpid(pid, os.WNOHANG) (no-op when pid isn't your child / on Windows). For any process/subprocess test, CI Linux is the real cross-platform gate; reason about the POSIX path and verify the CI run's conclusion by id."
metadata: 
  type: feedback
---

A `stop()` that spawns a dummy child, sends it SIGTERM, then asserts it's gone can be **green on local
Windows, red on CI ubuntu** with `assert 'stop-failed' == 'stopped'`.

**Root cause:** on POSIX a child that exits but isn't reaped by its parent becomes a **zombie** — it
still occupies a PID, so `os.kill(pid, 0)` succeeds (no `ProcessLookupError`) and a liveness probe
reports it ALIVE. The terminate loop therefore runs to its timeout and returns failure. Windows has no
zombies (and a truly detached process is reparented to init, which reaps it), so the bug surfaces only
when the killed process is your own unreaped child — exactly a test's case, on Linux.

**Why:** `os.kill(pid, 0)` cannot distinguish a live process from a zombie; the OS keeps the PID entry
until the parent `wait()`s. "It still answers signal 0" ≠ "it's still running."

**How to apply:**
- After killing your own child, **reap it**: `os.waitpid(pid, os.WNOHANG)` wrapped in
  `try/except (ChildProcessError, OSError)` (a no-op when it isn't your child, or on Windows), then
  re-check liveness. `subprocess.Popen.wait()` tolerates an already-reaped child (returns 0).
- Treat any process/subprocess test as **platform-divergent**: a local Windows pass proves nothing
  about Linux. Push and verify the **CI run's conclusion by id** (`gh run view <id> --json conclusion`),
  don't trust the local pass or the false-green `gh pr checks --watch`.
- Cousin traps where local ≠ the real gate: [[measure-cold-not-warm-windows]],
  [[optin-dep-tests-skipif-not-importorskip]], [[local-gate-respect-gitignore]].
