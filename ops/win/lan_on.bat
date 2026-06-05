@echo off
rem lan_on.bat - default the dashboard to a LAN bind so another device (e.g. a phone on the
rem same Wi-Fi) can view the read-only page. Thin wrapper around cross-platform ops/lan_setup.py.
rem It sets the AWB_DASHBOARD_HOST env var and PRINTS the firewall command for you to run once
rem as administrator (it never opens the firewall for you). Re-open your terminal / log out-in
rem afterwards so a double-click of restart_all picks up the change.
chcp 65001 >nul 2>&1
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ops\lan_setup.py" enable %*
echo.
pause
endlocal
