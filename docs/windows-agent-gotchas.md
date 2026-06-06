# Windows agent gotchas — silent failures specific to driving an agent on Windows

Most of this kit is platform-neutral, but an agent driving a Windows box hits a handful of traps that
fail *silently* — exit 0, a printed banner, a green local run — while nothing actually happened. They
cost hours because the symptom points away from the cause. Each entry below is symptom → root cause →
fix. This is the list we have actually hit, not an exhaustive platform guide.

## Invoking a `.bat` swallows the body under `cmd /c`

**Symptom:** an agent runs a `.bat` via a Bash `cmd /c "X.bat"` wrapper; it prints the batch's banner
and returns exit 0 — but the body never executed.

**Root cause:** the cross-shell wrapper can return success after the banner without running the script
body. Exit 0 plus visible output reads as "it worked," so the failure is invisible.

**Fix:** invoke the batch via PowerShell — `& "C:\path\to\X.bat"` — and verify a real side effect (a
status line, an output file, a changed value), never the exit code alone.

## Headless Python sets `sys.stdout` to `None`

**Symptom:** a script that runs fine in a terminal crashes at *import* under `pythonw.exe` or a service
host, with `AttributeError: 'NoneType' object has no attribute 'reconfigure'`.

**Root cause:** a headless runtime sets `sys.stdout`/`sys.stderr` to `None`, so a top-of-module
`sys.stdout.reconfigure(encoding="utf-8")` blows up before any of your code runs.

**Fix:** guard each stream — `if sys.stdout is not None: sys.stdout.reconfigure(encoding="utf-8")` —
and apply the same check to any module-level `sys.stdout` / `sys.stderr` access.

## "I restarted it but the change didn't take"

**Symptom:** you restart a service/app, the change doesn't appear, and you start re-reading the code.

**Root cause:** the *old* process is usually still alive — it still holds the port (so the new instance
bound nothing, or a different port), or a non-elevated shell couldn't kill a SYSTEM/elevated process so
the "kill" silently no-op'd.

**Fix:** before debugging the code, prove the old process died.
`Get-NetTCPConnection -LocalPort <port> | Select OwningProcess` → `Get-Process -Id <pid>`; if it's the
stale PID, kill it (elevate the shell if it's SYSTEM/elevated), confirm the port is free, then restart
and re-verify the change landed. **Verify served bytes, not the browser:** a long-lived server caches
what it loaded at startup (e.g. Flask with `debug=off` caches Jinja templates for the process lifetime),
so a stale process serves *old code even though the file on disk is new* — `curl` the endpoint and grep
for a recent marker rather than trusting a browser repro (which also caches). The kit's
[`ops/win/restart_all.bat`](../ops/win/restart_all.bat) now **automates the elevated-kill case**: it
auto-escalates with one UAC prompt to free the port even when the holder was launched elevated, then
restarts the dashboard non-elevated so it stays killable next time.

## A `requirements.txt` bump is not a deploy

**Symptom:** new code works locally but raises `ModuleNotFoundError` only in production.

**Root cause:** adding an import + editing `requirements.txt` is the *manifest*; a watcher / auto-reload
restarts the app but does **not** `pip install`. The dependency is simply absent from the deployed
virtualenv.

**Fix:** treat the manifest bump and the environment install as two separate acts; when a commit adds a
dependency, name the deploy step in the commit body (e.g. "run `pip install -r requirements.txt` in the
prod venv").

## Limits

These are observed traps on Windows + Python, not a complete platform guide. They share a shape worth
internalising: on Windows, *exit 0 / a printed banner / a green local run* is not proof the thing
happened — verify a real side effect. New traps belong here as they are hit.
