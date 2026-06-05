#!/usr/bin/env pwsh
# restart_all.ps1 - restart the ui/web dashboard (Flask, port 5151).
# Thin wrapper around the cross-platform ops/dashboard_ctl.py. Pass-through flags:
#   .\restart_all.ps1 --port 5252
$ErrorActionPreference = "Stop"
$Repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
& python (Join-Path $Repo "ops\dashboard_ctl.py") restart @args
$rc = $LASTEXITCODE
if ($rc -ne 0) {
  Write-Host ""
  Write-Host "  [!] restart reported a problem (exit $rc). See .ops\dashboard.log"
}
# Keep the window open so the result/error stays readable on double-click (the proven
# approach: just wait for a keypress). Programmatic callers use ops/dashboard_ctl.py directly.
Read-Host "Press Enter to close" | Out-Null
exit $rc
