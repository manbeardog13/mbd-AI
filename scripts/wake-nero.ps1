# ============================================================
#  Wake Nero — bring the companion to life.
#  Boots Tailscale (HTTPS), Ollama, and Nero, with an animated
#  purple/black Ghost (Destiny-style) that pulses as it loads.
#  Windows PowerShell 5.1+ / Windows Terminal.
# ============================================================

$ErrorActionPreference = "SilentlyContinue"
$repo = Join-Path $env:USERPROFILE "mbd-AI"
$port = 8080
$ollamaPort = 11434

# ---- Enable ANSI truecolor even on legacy consoles ----
try {
  $sig = @'
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(IntPtr h, int m);
[DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
[DllImport("kernel32.dll")] public static extern bool GetConsoleMode(IntPtr h, out int m);
'@
  $k = Add-Type -MemberDefinition $sig -Name VT -Namespace WinNero -PassThru
  $h = $k::GetStdHandle(-11); $m = 0
  [void]$k::GetConsoleMode($h, [ref]$m)
  [void]$k::SetConsoleMode($h, $m -bor 0x4)
} catch {}

$ESC = [char]27
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { $Host.UI.RawUI.WindowTitle = "Nero" } catch {}
try { [Console]::CursorVisible = $false } catch {}
Clear-Host

function Fg($r,$g,$b) { "$ESC[38;2;$r;$g;${b}m" }
$RESET = "$ESC[0m"

# ---- Build a symmetric diamond "Ghost shell" (generated, so it never drifts) ----
$W = 19
$rowBlocks = @(2,6,10,14,18,14,10,6,2)
$diamond = @()
foreach ($n in $rowBlocks) {
  $pad = [int](($W - $n) / 2)
  $diamond += (" " * $pad) + ("$([char]0x2588)" * $n)
}
$eyeRow = 4                       # the widest row holds the eye
$block = [char]0x2588            # full block
$eye   = [char]0x25C9            # ◉

# ---- Layout (absolute rows captured after the header) ----
$colW = try { [Console]::WindowWidth } catch { 80 }
$gx = [int](($colW - $W) / 2); if ($gx -lt 0) { $gx = 0 }

function CenterWrite($text, $r, $g, $b) {
  $plain = ($text -replace "$ESC\[[0-9;]*m","")
  $pad = [int](($colW - $plain.Length) / 2); if ($pad -lt 0) { $pad = 0 }
  Write-Host ((" " * $pad) + (Fg $r $g $b) + $text + $RESET)
}

Write-Host ""
CenterWrite "N   E   R   O" 150 120 255
CenterWrite "waking the companion" 120 96 170
Write-Host ""
$gy = [Console]::CursorTop           # diamond starts here
$statusRow = $gy + $diamond.Count + 1
$barRow    = $statusRow + 1
$listRow   = $barRow + 2

# ---- Render the breathing Ghost (full redraw each frame = no drift) ----
function Render-Ghost($frame) {
  for ($i = 0; $i -lt $diamond.Count; $i++) {
    $line = $diamond[$i]
    $t = [Math]::Sin(($frame * 0.35) - $i * 0.55) * 0.5 + 0.5   # wave down the shell
    $r = [int](66 + 92 * $t); $g = [int](38 + 66 * $t); $b = [int](150 + 105 * $t)
    [Console]::SetCursorPosition($gx, $gy + $i)
    if ($i -eq $eyeRow) {
      $et = [Math]::Sin($frame * 0.6) * 0.5 + 0.5               # eye pulses faster
      $er = [int](150 + 95 * $et); $eg = [int](110 + 105 * $et); $eb = [int](205 + 50 * $et)
      $half = "$block" * 8
      Write-Host ((Fg $r $g $b) + $half + (Fg $er $eg $eb) + "$eye$eye" + (Fg $r $g $b) + $half + $RESET) -NoNewline
    } else {
      Write-Host ((Fg $r $g $b) + $line + $RESET) -NoNewline
    }
  }
}

$spin = "$([char]0x280B)$([char]0x2819)$([char]0x2839)$([char]0x2838)$([char]0x283C)$([char]0x2834)$([char]0x2826)$([char]0x2827)$([char]0x2807)$([char]0x280F)"

function Render-Bar($prog) {
  $barW = 26
  $fill = [int]($prog * $barW); if ($fill -gt $barW) { $fill = $barW }
  $bar = (Fg 150 120 255) + ("$block" * $fill) + (Fg 58 40 96) + ("$([char]0x2591)" * ($barW - $fill)) + $RESET
  $pct = [int]($prog * 100)
  $txt = "$bar  " + (Fg 150 120 255) + ("{0,3}%" -f $pct) + $RESET
  $plain = "$("$block" * $barW)   100%"
  $pad = [int](($colW - $plain.Length) / 2); if ($pad -lt 0) { $pad = 0 }
  [Console]::SetCursorPosition(0, $barRow)
  Write-Host ((" " * $pad) + $txt + (" " * 4)) -NoNewline
}

# steps: label + state (0 pending, 1 active, 2 done, 3 warn)
$steps = @(
  @{ label = "Opening the network  (Tailscale)"; state = 0 },
  @{ label = "Warming the mind     (Ollama)";    state = 0 },
  @{ label = "Bringing Nero online (server)";    state = 0 }
)
function Render-Steps($frame) {
  for ($i = 0; $i -lt $steps.Count; $i++) {
    $s = $steps[$i]
    switch ($s.state) {
      0 { $sym = "$([char]0x00B7)"; $c = (Fg 90 78 120) }
      1 { $sym = "$($spin[$frame % $spin.Length])"; $c = (Fg 160 130 255) }
      2 { $sym = "$([char]0x2713)"; $c = (Fg 150 120 255) }
      default { $sym = "$([char]0x2013)"; $c = (Fg 150 110 90) }
    }
    $line = " $sym  $($s.label)"
    $pad = [int](($colW - 40) / 2); if ($pad -lt 0) { $pad = 0 }
    [Console]::SetCursorPosition(0, $listRow + $i)
    Write-Host ((" " * $pad) + $c + $line + $RESET + (" " * 6)) -NoNewline
  }
}

$script:frame = 0
function Draw($prog) {
  Render-Ghost $script:frame
  Render-Bar $prog
  Render-Steps $script:frame
  $script:frame++
}

function Test-Port($p) {
  $c = New-Object System.Net.Sockets.TcpClient
  try { $c.Connect("127.0.0.1", $p); return $c.Connected } catch { return $false } finally { $c.Close() }
}

# Animate `Draw` until the condition is true (or timeout). Returns $true if it came up.
function Wait-Until([scriptblock]$cond, $prog, [int]$timeout) {
  $start = Get-Date
  while (-not (& $cond)) {
    Draw $prog
    Start-Sleep -Milliseconds 110
    if (((Get-Date) - $start).TotalSeconds -gt $timeout) { return $false }
  }
  return $true
}
function Breathe($prog, $times) { for ($n = 0; $n -lt $times; $n++) { Draw $prog; Start-Sleep -Milliseconds 90 } }

Draw 0.0
Breathe 0.02 8

# ---- Step 1: Tailscale (HTTPS remote access) ----
$steps[0].state = 1; Breathe 0.05 4
if (Get-Command tailscale -ErrorAction SilentlyContinue) {
  Start-Process tailscale -ArgumentList "serve","--bg","$port" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
  Breathe 0.15 10
  $steps[0].state = 2
} else {
  $steps[0].state = 3   # not installed — local access still works
}
Draw 0.2

# ---- Step 2: Ollama (the brain) ----
$steps[1].state = 1; Draw 0.25
if (-not (Test-Port $ollamaPort)) {
  Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
}
if (Wait-Until { Test-Port $ollamaPort } 0.45 40) { $steps[1].state = 2 } else { $steps[1].state = 3 }
Draw 0.55

# ---- Step 3: Nero (the server) ----
$steps[2].state = 1; Draw 0.6
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Start-Process -FilePath $py -ArgumentList "run.py" -WorkingDirectory $repo -WindowStyle Minimized -ErrorAction SilentlyContinue | Out-Null
if (Wait-Until { Test-Port $port } 0.9 45) { $steps[2].state = 2 } else { $steps[2].state = 3 }
Draw 1.0
Breathe 1.0 6

# ---- Awake ----
Start-Process "http://localhost:$port" -ErrorAction SilentlyContinue | Out-Null
[Console]::SetCursorPosition(0, $listRow + $steps.Count + 1)
CenterWrite "Nero is awake." 160 130 255
CenterWrite "she's live at  http://localhost:$port   (and on your devices via Tailscale)" 120 96 170
CenterWrite "press any key to close this window  —  Nero keeps running" 96 82 130

# Ambient presence: keep breathing until a key is pressed.
while (-not [Console]::KeyAvailable) {
  Render-Ghost $script:frame
  $script:frame++
  Start-Sleep -Milliseconds 130
}
try { [Console]::CursorVisible = $true } catch {}
Write-Host $RESET
