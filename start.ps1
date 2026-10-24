# iphctrl one-command start. Usage (normal PowerShell, in this folder):
#     .\start.ps1
# Checks the PC and the phone, fixes what it can, starts the phone session
# (serve) in its own window, unlocks the phone and takes a test screenshot.
# Safe to run again at any time: it restarts the session.

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:VIRTUAL_ENV = $null
$env:NO_COLOR = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Ok($m)   { Write-Host "[ok]  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!!]  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[XX]  $m" -ForegroundColor Red; exit 1 }

# ---- 1. PC: tools ---------------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Fail 'uv not found. Install: winget install astral-sh.uv' }
$amds = Get-Service 'Apple Mobile Device Service' -ErrorAction SilentlyContinue
if (-not $amds) { Fail 'Apple Mobile Device Service missing. Install iTunes (winget install Apple.iTunes) and run again.' }

# ---- 2. PC: things that need admin (one UAC prompt, only if needed) -------------
$fix = @()
if ($amds.Status -ne 'Running') { $fix += "Start-Service 'Apple Mobile Device Service'" }
$av = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like 'AutoViral*' -and $_.State -ne 'Disabled' }
foreach ($t in $av) { $fix += "Stop-ScheduledTask -TaskName '$($t.TaskName)'; Disable-ScheduledTask -TaskName '$($t.TaskName)' | Out-Null" }
if ($fix.Count -gt 0) {
    Warn "Needs admin once (click Yes): $($fix.Count) fix(es) - Apple service / disable AutoViral tasks"
    Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-Command', ($fix -join '; ')
}
if ((Get-Service 'Apple Mobile Device Service').Status -ne 'Running') { Fail 'Apple Mobile Device Service is not running.' }
Ok 'Apple Mobile Device Service running'
if (Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like 'AutoViral*' -and $_.State -ne 'Disabled' }) {
    Warn 'AutoViral tasks still enabled (they compete for the phone)'
} else { Ok 'AutoViral driver not running' }

# ---- 3. Python env ----------------------------------------------------------------
uv sync -q
if ($LASTEXITCODE -ne 0) { Fail 'uv sync failed' }
Ok 'python env ready'

# ---- 3b. Kernel tunnel (tunneld, admin) + USB power saving off: one-time UAC ----
if (-not (Get-ScheduledTask -TaskName 'iphctrl tunneld' -ErrorAction SilentlyContinue)) {
    Warn 'One-time admin setup (click Yes): kernel tunnel task + USB power saving off'
    Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSScriptRoot\scripts\setup-admin.ps1`"", '-Root', "`"$PSScriptRoot`"",
        '-User', "`"$env:USERDOMAIN\$env:USERNAME`""
}
if (-not (Get-NetTCPConnection -LocalPort 49151 -State Listen -ErrorAction SilentlyContinue)) {
    Start-ScheduledTask -TaskName 'iphctrl tunneld' -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 20 -and -not (Get-NetTCPConnection -LocalPort 49151 -State Listen -ErrorAction SilentlyContinue); $i++) { Start-Sleep 1 }
}
$tunneld = [bool](Get-NetTCPConnection -LocalPort 49151 -State Listen -ErrorAction SilentlyContinue)
if ($tunneld) { Ok 'kernel tunnel service (tunneld) running' }
else { Warn 'tunneld not running, using the userspace tunnel (see cmd\tunneld.log)' }

# ---- 4. Phone on the cable --------------------------------------------------------
$udid = $null
for ($i = 0; $i -lt 30 -and -not $udid; $i++) {
    $out = (uv run iphctrl devices 2>$null | Out-String).Trim()
    if ($out -match '^[0-9A-F]{8}-[0-9A-F]{16}') { $udid = $Matches[0] }
    else {
        if ($i -eq 0) { Warn 'No iPhone on USB yet: unlock it, replug the cable, tap Trust. Waiting up to 90 s...' }
        Start-Sleep 3
    }
}
if (-not $udid) { Fail 'Phone not visible. Unlock + replug + Trust. Still nothing: restart the phone (docs/LESSONS.md #1).' }
Ok "phone $udid"
if ($tunneld) {
    $tun = $false
    for ($i = 0; $i -lt 20 -and -not $tun; $i++) {
        try { $tun = [bool]((Invoke-RestMethod http://127.0.0.1:49151/ -TimeoutSec 3).$udid) } catch { }
        if (-not $tun) { Start-Sleep 1 }
    }
    if ($tun) { Ok 'kernel tunnel to phone up' } else { Warn 'tunneld has no tunnel to the phone yet, using userspace' }
}

$dev = (uv run pymobiledevice3 amfi developer-mode-status 2>$null | Out-String).Trim()
if ($dev -notmatch 'true') { Fail 'Developer Mode is OFF: Settings > Privacy & Security > Developer Mode > ON, restart, confirm Turn On.' }
Ok 'Developer Mode on'

$wda = (uv run iphctrl apps WebDriverAgent 2>$null | Out-String).Trim()
if (-not $wda) { Fail 'WebDriverAgent not installed: AltServer tray icon > SHIFT+click > Sideload .ipa > wda\WebDriverAgentRunner.ipa, then trust it on the phone (README).' }
Ok 'WebDriverAgent installed'

if (-not (Test-Path .env) -or -not (Select-String -Path .env -Pattern 'IPHCTRL_PASSCODE=' -Quiet)) {
    Warn 'No IPHCTRL_PASSCODE in .env: unlock will only work if the phone has no passcode.'
}

# ---- 5. (Re)start the phone session ----------------------------------------------
New-Item -ItemType Directory -Force cmd, shots | Out-Null
if (Test-Path cmd\serve.pid) {
    $old = Get-Content cmd\serve.pid -ErrorAction SilentlyContinue
    if ($old) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*iphctrl.serve*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
Remove-Item cmd\result.txt, cmd\next.txt -ErrorAction SilentlyContinue
Start-Process powershell -WindowStyle Minimized -ArgumentList '-NoProfile', '-Command',
    "Set-Location '$PSScriptRoot'; `$env:VIRTUAL_ENV=`$null; `$env:PYTHONIOENCODING='utf-8'; uv run python -m iphctrl.serve 2>&1 | Tee-Object cmd\serve.log"
Write-Host '      starting phone session (WebDriverAgent ~20-40 s)...'
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 2
    if ((Test-Path cmd\result.txt) -and ((Get-Content cmd\result.txt -Raw) -match '^ready')) { $ready = $true; break }
}
if (-not $ready) {
    Fail 'Session did not start. See cmd\serve.log. WDA failing to start = 7-day signature expired: re-sideload with AltServer (README).'
}
Ok 'phone session running (minimized window "serve")'

# ---- 6. Unlock + test screenshot --------------------------------------------------
uv run python -m iphctrl.send unlock 'shot startup' | Out-Host
Ok "Ready. Screenshot: $PSScriptRoot\shots\startup.png"
Write-Host ''
Write-Host 'Send commands:  uv run python -m iphctrl.send "launch instagram" "browse 30" "shot ig"'
Write-Host 'Stop:           .\stop.ps1'
