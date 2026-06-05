@echo off
rem autostart_on.bat - make the dashboard launch automatically at logon (Scheduled Task).
rem Thin wrapper around cross-platform ops/autostart.py. Creating an ONLOGON task usually needs
rem admin, so this self-elevates via UAC (no HKCU/env is touched here, so elevating is safe).
chcp 65001 >nul 2>&1
net session >nul 2>&1
if errorlevel 1 (
  echo   Requesting administrator (UAC) to register the logon task...
  powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ops\autostart.py" enable
echo.
echo   The dashboard will now start at logon. Run autostart_off.bat to undo.
pause
endlocal
