@echo off
rem set_password.bat - set or reset the /admin dashboard password on Windows.
rem Thin wrapper around the cross-platform ui/web/set_password.py. Writes a salted pbkdf2
rem hash to .ops\admin.hash (gitignored) - the plaintext is never stored. No admin/UAC
rem needed (it only writes a file in your repo). Double-click it, or run from any directory.
rem Use it to set the FIRST password, or to RECOVER a forgotten one (running on this machine
rem is what proves you're the owner, so it does not ask for the old password).
chcp 65001 >nul 2>&1
setlocal
set "REPO=%~dp0..\.."
python "%REPO%\ui\web\set_password.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo   [!] set_password reported a problem ^(exit %RC%^).
)
rem Keep the window open so the result/error stays readable on double-click.
pause
endlocal & exit /b %RC%
