<#
  Put a "NERO Mission Control" icon on your Windows desktop.

  Double-click  scripts\Create Desktop Icon.cmd  (easiest), or run:
    powershell -ExecutionPolicy Bypass -File scripts\install-desktop-icon.ps1

  Creates a desktop shortcut that runs the launcher (scripts\mission-control.ps1):
  it starts NERO if needed and opens Mission Control. The same screen is
  reachable from your phone/tablet on the same Wi-Fi — see the "Devices" link
  inside Mission Control (or open /connect) for the URL + QR.
#>
$ErrorActionPreference = 'Stop'
$root     = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot 'mission-control.ps1'
$icon     = Join-Path $PSScriptRoot 'nero-mission-control.ico'

if (-not (Test-Path $launcher)) { throw "Launcher not found: $launcher" }

$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'NERO Mission Control.lnk'
$psExe   = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnkPath)
$sc.TargetPath       = $psExe
$sc.Arguments        = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$sc.WorkingDirectory = $root
$sc.WindowStyle      = 7   # run minimized (no console flash)
$sc.Description      = 'Launch NERO Mission Control'
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host ""
Write-Host "  Desktop icon created:" -ForegroundColor Cyan
Write-Host "    $lnkPath"
Write-Host ""
Write-Host "  Double-click it to open Mission Control."
Write-Host "  On your phone/tablet (same Wi-Fi): open the 'Devices' link in"
Write-Host "  Mission Control for the address + QR, then Add to Home Screen."
Write-Host ""
