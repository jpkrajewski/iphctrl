# One-time admin setup, run elevated by start.ps1 (one UAC prompt). Safe to re-run.
#  1. Scheduled task "iphctrl tunneld": runs `pymobiledevice3 remote tunneld` at logon
#     with admin rights. That is the kernel (wintun) tunnel to the phone, steadier than
#     the no-admin userspace one. Phone.__aenter__ uses it whenever it is running.
#  2. USB power saving off: USB selective suspend (power plan) and "allow the computer
#     to turn off this device" on every USB device, so Windows never naps the phone's port.
param([Parameter(Mandatory)] [string]$Root, [Parameter(Mandatory)] [string]$User)
$ErrorActionPreference = 'Stop'

$uv = (Get-Command uv).Source
$cmd = "Set-Location '$Root'; `$env:VIRTUAL_ENV=`$null; & '$uv' run --no-sync pymobiledevice3 remote tunneld *> cmd\tunneld.log"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Root `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
$principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'iphctrl tunneld' -Force -Action $action -Principal $principal `
    -Settings $settings -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $User) | Out-Null

$usb = '2a737441-1930-4402-8d77-b2bebba308a3'; $suspend = '48e6b7a6-50f5-4782-a5d4-53bb8f07e226'
powercfg /SETACVALUEINDEX SCHEME_CURRENT $usb $suspend 0
powercfg /SETDCVALUEINDEX SCHEME_CURRENT $usb $suspend 0
powercfg /SETACTIVE SCHEME_CURRENT
Get-CimInstance -Namespace root\wmi -ClassName MSPower_DeviceEnable |
    Where-Object { $_.InstanceName -like 'USB*' -and $_.Enable } |
    ForEach-Object { Set-CimInstance -InputObject $_ -Property @{ Enable = $false } }
