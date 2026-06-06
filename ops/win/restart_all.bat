@echo off
rem restart_all.bat - restart the ui/web dashboard (Flask, port 5151) on Windows.
rem
rem Double-click it, or run from any directory. The real logic lives in restart_all.ps1
rem (one source), which restarts via the cross-platform ops/dashboard_ctl.py and, crucially,
rem DEFINITIVELY frees port 5151 even when the holder was launched ELEVATED: it auto-escalates
rem with a single UAC prompt to run `stop --force`, then starts the dashboard back as YOU
rem (non-elevated) so it stays killable next time. No more manual debugging to reclaim the port.
rem
rem Pass extra flags through, e.g.
rem   restart_all.bat --port 5252
rem   restart_all.bat --force      (force-free the port even if a stale/foreign process holds it;
rem                                 elevation is handled for you — approve the UAC prompt)
chcp 65001 >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_all.ps1" %*
exit /b %ERRORLEVEL%
