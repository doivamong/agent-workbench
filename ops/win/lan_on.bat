@echo off
rem lan_on.bat - default the dashboard to a LAN bind so another device (e.g. a phone on the same
rem Wi-Fi) can view the read-only page. Thin wrapper around cross-platform ops/lan_setup.py.
rem Step 1 (env var + start-state) runs as YOU (HKCU must be the logged-in user, so it is NOT
rem elevated). Step 2 (open the firewall) needs admin, so only that step self-elevates via UAC.
chcp 65001 >nul 2>&1
setlocal
set "REPO=%~dp0..\.."

echo   [1/2] Setting AWB_DASHBOARD_HOST + start-state to a LAN bind...
python "%REPO%\ops\lan_setup.py" enable %*

echo.
echo   [2/2] Opening firewall port 5151 to the local subnet (UAC will prompt for admin)...
set "PY="
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY set "PY=python"
powershell -NoProfile -Command "Start-Process -FilePath '%PY%' -Verb RunAs -ArgumentList '%REPO%\ops\lan_setup.py','firewall'"

echo.
echo   Done. Now restart the dashboard so it binds the LAN:  restart_all.bat
echo   (Re-open your terminal / log out-in so new shells also default to LAN.)
pause
endlocal
