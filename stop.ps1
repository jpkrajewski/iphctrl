# Stops the phone session started by start.ps1.
Set-Location $PSScriptRoot
$env:VIRTUAL_ENV = $null
if (Test-Path cmd\serve.pid) {
    uv run python -m iphctrl.send quit | Out-Null
    Start-Sleep 2
    $old = Get-Content cmd\serve.pid -ErrorAction SilentlyContinue
    if ($old) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue }
    Remove-Item cmd\serve.pid -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*iphctrl.serve*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host 'stopped'
