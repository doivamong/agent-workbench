@echo off
rem autostart_off.bat - stop the dashboard from launching at logon (removes the Scheduled Task).
rem Thin wrapper around ops/autostart.py; self-elevates via UAC (schtasks /Delete needs admin).
chcp 65001 >nul 2>&1
net session >nul 2>&1
if errorlevel 1 (
  echo   Requesting administrator (UAC) to remove the logon task...
  powershell -NoProfile -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ops\autostart.py" disable
echo.
pause
endlocal
