<#
  NERO — Mission Control launcher (Windows)

  Starts the Companion if it isn't already running, waits for it to come up,
  then opens Mission Control in your default browser. This is what the desktop
  icon runs. It's also reachable from your phone/tablet on the same Wi-Fi —
  use the "Devices" link in Mission Control (or open /connect) for the URL + QR.

  Run directly:  powershell -ExecutionPolicy Bypass -File scripts\mission-control.ps1
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Get-Port {
  foreach ($f in @('config.yaml', 'config.example.yaml')) {
    $p = Join-Path $root $f
    if (Test-Path $p) {
      $m = Select-String -Path $p -Pattern '^\s*port:\s*"?(\d+)"?' | Select-Object -First 1
      if ($m) { return [int]$m.Matches[0].Groups[1].Value }
    }
  }
  return 8080
}

function Test-Port([int]$Port) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(400)
    if ($ok -and $c.Connected) { $c.EndConnect($iar); $c.Close(); return $true }
    $c.Close(); return $false
  } catch { return $false }
}

function Show-Error([string]$msg) {
  try { Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($msg, 'NERO Mission Control',
          'OK', 'Error') | Out-Null } catch { Write-Host $msg }
}

$port = Get-Port
$url  = "http://localhost:$port/mission-control"

if (-not (Test-Port $port)) {
  $py = Join-Path $root '.venv\Scripts\python.exe'
  if (Test-Path $py) {
    # Normal run — start the server hidden.
    Start-Process -FilePath $py -ArgumentList 'run.py' -WorkingDirectory $root -WindowStyle Hidden | Out-Null
  } elseif (Test-Path (Join-Path $root 'start.bat')) {
    # First run — show the one-time setup (bootstrap creates .venv, then launches).
    Start-Process -FilePath (Join-Path $root 'start.bat') -WorkingDirectory $root | Out-Null
  } else {
    Show-Error("Couldn't find NERO's Python environment or start.bat in`n$root`n`nRun start.bat once to set up, then try again.")
    exit 1
  }

  # Wait for it to come up (first run includes setup, so be patient).
  $deadline = (Get-Date).AddSeconds(90)
  while (-not (Test-Port $port)) {
    if ((Get-Date) -gt $deadline) {
      Show-Error("NERO didn't start within 90s on port $port.`nOpen start.bat manually to see what happened.")
      exit 1
    }
    Start-Sleep -Milliseconds 600
  }
  Start-Sleep -Milliseconds 400  # a beat for the first request to be served
}

Start-Process $url | Out-Null
