[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8788,
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$serverScript = Join-Path $repoRoot 'scripts\serve_voidbound.py'
$url = "http://127.0.0.1:$Port/adventure/"
$healthUrl = "http://127.0.0.1:$Port/health"

if (-not (Test-Path -LiteralPath $serverScript -PathType Leaf)) {
    throw "Voidbound Codex server is missing: $serverScript"
}

$ready = $false
try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
    $ready = $health.ok -eq $true -and $health.app -eq 'nero-voidbound-codex/1'
} catch {
    $ready = $false
}

if (-not $ready) {
    $python = Get-Command python -ErrorAction Stop
    $quotedServerScript = "`"$serverScript`""
    Start-Process -FilePath $python.Source -ArgumentList @($quotedServerScript, '--port', $Port) -WorkingDirectory $repoRoot -WindowStyle Hidden
    for ($attempt = 0; $attempt -lt 30 -and -not $ready; $attempt++) {
        Start-Sleep -Milliseconds 100
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
            $ready = $health.ok -eq $true -and $health.app -eq 'nero-voidbound-codex/1'
        } catch {
            $ready = $false
        }
    }
}

if (-not $ready) {
    throw "Voidbound Codex did not become ready on 127.0.0.1:$Port. The port may be in use."
}

if (-not $NoOpen) {
    Start-Process $url
}
