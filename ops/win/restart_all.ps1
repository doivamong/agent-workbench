#!/usr/bin/env pwsh
# restart_all.ps1 - restart the ui/web dashboard (Flask, port 5151), DEFINITIVELY.
#
# Wraps the cross-platform ops/dashboard_ctl.py. The engine already kills EVERY process on the
# port with `stop --force` (netstat -ano -> taskkill /T /F) -- but a non-elevated taskkill is
# DENIED against a process launched ELEVATED ("Access is denied: higher integrity level"). That
# left a stale elevated dashboard serving cached templates and made restart_all unusable without
# manual debugging. This script closes that hole:
#
#   1. Try a normal restart (no UAC when the port-holder is a normal-integrity process).
#   2. If that is blocked (exit != 0) and we are NOT elevated, free the port with ONE elevated
#      `stop --force` (a single UAC prompt) -- which CAN kill the elevated holder -- then
#   3. start the dashboard again as YOU (non-elevated), so the NEW dashboard is normal-integrity
#      and killable next time with no UAC at all (no perpetual-elevation cycle).
#
# Pass-through flags work as before:  .\restart_all.ps1 --port 5252   /   --force
#
# Honest limit: killing an elevated process REQUIRES elevation -- there is one unavoidable UAC
# prompt in that case. If you cancel it, the old (elevated) server keeps the port; re-run and
# approve, or End the PID on port 5151 from an elevated Task Manager.
#
# ASCII-only on purpose: this runs under Windows PowerShell 5.1, which mis-decodes a non-ASCII
# (no-BOM) script and fails to parse it -- so no em-dashes / arrows / smart quotes here.
$ErrorActionPreference = "Stop"
$Repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Ctl  = Join-Path $Repo "ops\dashboard_ctl.py"

# Resolve the full python path: an elevated child may not inherit YOUR PATH, so pass an absolute
# exe (the same care lan_on.bat takes). Fall back to the bare name if discovery fails.
$Py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Py) { $Py = "python" }

function Test-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
    [Security.Principal.WindowsBuiltinRole]::Administrator)
}

# 1) Normal restart first - no UAC unless we actually need it.
& $Py $Ctl restart @args
$rc = $LASTEXITCODE

# 2) Blocked? The usual cause is an ELEVATED process holding the port that a normal taskkill
#    cannot reach. Free the port with an elevated 'stop --force', escalating only if needed.
if ($rc -ne 0) {
  Write-Host ""
  Write-Host "  [!] restart blocked (exit $rc) - port is likely held by an ELEVATED process."
  $freed = $true
  try {
    if (Test-Admin) {
      Write-Host "      Already elevated - freeing the port with 'stop --force'..."
      & $Py $Ctl stop --force @args
    } else {
      Write-Host "      Freeing the port with an elevated 'stop --force' (UAC will prompt)..."
      $stopArgs = @($Ctl, "stop", "--force") + $args
      $p = Start-Process -FilePath $Py -Verb RunAs -PassThru -Wait -ArgumentList $stopArgs
      Write-Host "      Elevated free-port finished (exit $($p.ExitCode))."
    }
  } catch {
    $freed = $false
    Write-Host "  [!] Could not elevate to free the port: $($_.Exception.Message)"
    Write-Host "      Approve the UAC prompt on a re-run, or End the PID on port 5151 from an"
    Write-Host "      elevated Task Manager (Details tab), then run this again."
  }
  # 3) Start again as the CURRENT user, so the new dashboard stays non-elevated (cycle broken).
  if ($freed) {
    Write-Host "      Port freed - starting the dashboard as you (non-elevated)..."
    & $Py $Ctl restart @args
    $rc = $LASTEXITCODE
  }
}

if ($rc -ne 0) {
  Write-Host ""
  Write-Host "  [!] restart reported a problem (exit $rc). See .ops\dashboard.log"
}
# Keep the window open so the result/error stays readable on double-click. Programmatic callers
# use ops/dashboard_ctl.py directly (no prompt). Skip the prompt in non-interactive sessions.
if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
  Read-Host "Press Enter to close" | Out-Null
}
exit $rc
