@echo off
rem restart_all.bat - restart the ui/web dashboard (Flask, port 5151) on Windows.
rem Thin wrapper: all logic lives in the cross-platform ops/dashboard_ctl.py.
rem Double-click it, or run from any directory. Restart clears __pycache__ first (fresh code).
rem Pass extra flags through, e.g.
rem   restart_all.bat --port 5252
rem   restart_all.bat --force          (kill whatever holds the port if a stale/foreign process
rem                                      blocks the restart; run as Administrator if it's elevated)
chcp 65001 >nul 2>&1
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ops\dashboard_ctl.py" restart %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo   [!] restart reported a problem ^(exit %RC%^). See .ops\dashboard.log
)
rem Keep the window open so the result/error stays readable on double-click (the proven,
rem battle-tested approach: just pause). Programmatic callers use ops/dashboard_ctl.py directly.
pause
endlocal & exit /b %RC%
