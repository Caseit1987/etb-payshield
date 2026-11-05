# ETB PayShield Unified Control Script (fixed version)
# Changes: paths and environment are derived from $PSScriptRoot and passed
# explicitly into the background job, instead of hardcoded
# C:\Users\casei\Desktop paths and assumed env inheritance.
$Root = $PSScriptRoot
$TargetHost = $env:GATE_HOST
$TargetPort = $env:GATE_PORT

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "[*] Launching ETB PayShield System Infrastructure..." -ForegroundColor Cyan
Write-Host "[*] Interface: http://$($TargetHost):$($TargetPort)" -ForegroundColor Yellow
Write-Host "====================================================" -ForegroundColor Cyan

if (-not $env:GATE_ENGINE_API_KEY) {
    Write-Error "CRITICAL: GATE_ENGINE_API_KEY environment variable is missing from session state. Aborting."
    return
}

$GateScript = Join-Path $Root "gate\proxy_listener.py"
$ApiKey = $env:GATE_ENGINE_API_KEY
$N8nUrl = $env:N8N_PIPELINE_URL

$GateJob = Start-Job -Name "ETB_Proxy_Gate" -ArgumentList $GateScript, $TargetHost, $TargetPort, $ApiKey, $N8nUrl -ScriptBlock {
    param($GateScript, $h, $p, $k, $n)
    $env:GATE_HOST = $h
    $env:GATE_PORT = $p
    $env:GATE_ENGINE_API_KEY = $k
    $env:N8N_PIPELINE_URL = $n
    python $GateScript
}

Write-Host "[+] LayerZero Verification Gate spawned safely in background process context." -ForegroundColor Green
Write-Host "[*] Run 'Get-Job' or 'Receive-Job -Name ETB_Proxy_Gate' to monitor execution stream." -ForegroundColor Gray
Write-Host "[*] To close infrastructure down completely, execute: Stop-Job -Name ETB_Proxy_Gate" -ForegroundColor Gray
Write-Host "====================================================" -ForegroundColor Cyan
