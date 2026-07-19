[CmdletBinding()]
param(
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$executable = & (Join-Path $root 'Build-NeroFamiliar.ps1')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw 'Nero Familiar build did not produce an executable.'
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Nero - Void Guardian.lnk'
$icon = Join-Path $root 'assets\nero\nero-voidcaster.ico'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $executable
$shortcut.WorkingDirectory = Split-Path -Parent $executable
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = 'Nero Void Guardian desktop familiar'
$shortcut.Save()

if ($Launch) {
    Start-Process -FilePath $executable -WorkingDirectory $shortcut.WorkingDirectory
}

Write-Output $shortcutPath
