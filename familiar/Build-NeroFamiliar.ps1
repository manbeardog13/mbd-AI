[CmdletBinding()]
param(
    [switch]$InstallShortcut
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$framework = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319'
$wpf = Join-Path $framework 'WPF'
$compiler = Join-Path $framework 'csc.exe'
$source = Join-Path $root 'src\NeroFamiliar.cs'
$icon = Join-Path $root 'assets\nero\nero-voidcaster.ico'
$outputDir = Join-Path $root 'bin'
$output = Join-Path $outputDir 'NeroFamiliar.exe'
$manifest = Join-Path ([System.IO.Path]::GetTempPath()) ("NeroFamiliar-{0}.manifest" -f [guid]::NewGuid().ToString('N'))

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw "Required .NET Framework compiler not found: $compiler"
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$manifestXml = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity version="2.0.0.0" processorArchitecture="*" name="Nero.VoidGuardian.DesktopFamiliar" type="win32" />
  <description>Nero Void Guardian Desktop Familiar</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false" /></requestedPrivileges></security>
  </trustInfo>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">True/PM</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2,PerMonitor</dpiAwareness>
    </windowsSettings>
  </application>
</assembly>
'@

try {
    [System.IO.File]::WriteAllText($manifest, $manifestXml, [System.Text.UTF8Encoding]::new($false))
    & $compiler /nologo /target:winexe "/out:$output" "/win32icon:$icon" "/win32manifest:$manifest" `
        "/reference:$wpf\WindowsBase.dll" `
        "/reference:$wpf\PresentationCore.dll" `
        "/reference:$wpf\PresentationFramework.dll" `
        "/reference:$framework\System.Xaml.dll" `
        "/reference:$framework\System.Windows.Forms.dll" `
        "/reference:$framework\System.Drawing.dll" `
        "/reference:$framework\System.Web.Extensions.dll" `
        $source
    if ($LASTEXITCODE -ne 0) { throw "Nero Familiar compilation failed ($LASTEXITCODE)" }
    if ($InstallShortcut) {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $shortcutPath = Join-Path $desktop 'Nero - Void Guardian.lnk'
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $output
        $shortcut.WorkingDirectory = $outputDir
        $shortcut.IconLocation = "$icon,0"
        $shortcut.Description = 'Launch the Nero Void Guardian desktop familiar'
        $shortcut.Save()
        Write-Output $shortcutPath
    }
    Write-Output $output
} finally {
    Remove-Item -LiteralPath $manifest -Force -ErrorAction SilentlyContinue
}
