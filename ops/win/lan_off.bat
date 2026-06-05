@echo off
rem lan_off.bat - revert the dashboard to localhost-only (the safe default). Thin wrapper around
rem cross-platform ops/lan_setup.py; resets the AWB_DASHBOARD_HOST env var. Re-open your terminal
rem / log out-in afterwards. (You may also remove the firewall rule it printed — see the output.)
chcp 65001 >nul 2>&1
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ops\lan_setup.py" disable %*
echo.
pause
endlocal
