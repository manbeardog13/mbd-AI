$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$signals = Join-Path $folder '.signals'
New-Item -ItemType Directory -Force -Path $signals | Out-Null

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = [System.Drawing.SystemIcons]::Information
$icon.Visible = $true

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $folder
$watcher.Filter = '*.txt'
$watcher.NotifyFilter = [System.IO.NotifyFilters]'LastWrite, FileName'
$watcher.EnableRaisingEvents = $true
$state = [pscustomobject]@{ Signals = $signals; Icon = $icon }

$action = {
    $state = $Event.MessageData
    $name = $Event.SourceEventArgs.Name
    if ($name -notin @('LOG.txt', 'DEBATE CC.txt')) { return }
    $timestamp = [DateTimeOffset]::UtcNow.ToString('o')
    foreach ($target in @('codex', 'claude')) {
        $payload = [ordered]@{ target=$target; source='filesystem-watcher'; file=$name; timestamp=$timestamp }
        $path = Join-Path $state.Signals "$target.pending.json"
        $json = $payload | ConvertTo-Json
        [System.IO.File]::WriteAllText($path, $json + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
    }
    [console]::Beep(880, 120)
    $notify = $state.Icon
    $notify.BalloonTipTitle = 'Nero School'
    $notify.BalloonTipText = "$name changed. Codex and Claude signals are pending."
    $notify.ShowBalloonTip(4000)
    Write-Host "[$timestamp] $name changed; durable signals written."
}

$subscription = Register-ObjectEvent -InputObject $watcher -EventName Changed -MessageData $state -Action $action
Write-Host 'Watching DEBATE CC.txt and LOG.txt. Press Ctrl+C to stop.'
try {
    while ($true) { Wait-Event -Timeout 1 | Out-Null }
}
finally {
    Unregister-Event -SubscriptionId $subscription.Id -ErrorAction SilentlyContinue
    $watcher.Dispose()
    $icon.Visible = $false
    $icon.Dispose()
}
