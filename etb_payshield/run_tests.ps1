# ETB PayShield Master Automation Pipeline & Test Runner (fixed version)
# Changes: portable $PSScriptRoot paths; the fixed Start-Sleep 2 startup
# race is replaced with a /health readiness poll (up to ~20s), which was
# why Step A reported "Gate did not initialize properly"; a new Step A2
# proves the gate blocks a semantic injection payload even WITH a valid
# API key, i.e. it is a validation gate, not only an auth gate.
Clear-Host
$Root = $PSScriptRoot
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "[*] Initializing Automated ETB PayShield Testing Loop..." -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

$env:GATE_HOST = "localhost"
$env:GATE_PORT = "8080"
$env:N8N_PIPELINE_URL = "http://localhost:5678/webhook/etb-threats"
$env:GATE_ENGINE_API_KEY = "EB-COMMAND-CENTER-SECURE-KEY"

Write-Host "[*] Recycling active background process contexts..." -ForegroundColor Gray
Stop-Job -Name "ETB_Proxy_Gate" -ErrorAction SilentlyContinue
Remove-Job -Name "ETB_Proxy_Gate" -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Root "dashboard\gate_events.jsonl") -ErrorAction SilentlyContinue

& (Join-Path $Root "start_etb_shield.ps1")

Write-Host "[*] Waiting for gate to accept connections..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $h = Invoke-RestMethod -Uri "http://localhost:8080/health" -Method Get -TimeoutSec 1
        if ($h.status -eq "ok") { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) {
    Write-Host "[-] Gate did not become ready within 20 seconds. Job output:" -ForegroundColor Red
    Receive-Job -Name "ETB_Proxy_Gate"
    return
}
Write-Host "[+] Gate is ready." -ForegroundColor Green

Write-Host "`n[*] Automation Step A: Launching unauthorized simulation string..." -ForegroundColor Yellow
try {
    $null = Invoke-RestMethod -Uri "http://localhost:8080" -Method Post -Body '{"unauthorized_test": true}' -ContentType "application/json" -TimeoutSec 2
    Write-Host "[-] Unexpected: unauthorized request was NOT blocked." -ForegroundColor Red
} catch {
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.Value__
        Write-Host "[?] Success: Gate actively blocked request with HTTP Status Code: $statusCode" -ForegroundColor Green
    } else {
        Write-Host "[-] Connection error encountered: Gate did not initialize properly." -ForegroundColor Red
    }
}

Write-Host "`n[*] Automation Step A2: Authenticated injection payload (valid key, malicious body)..." -ForegroundColor Yellow
$headers = @{"X-ETB-Key" = "EB-COMMAND-CENTER-SECURE-KEY"}
$injBody = @{
    transaction_id = "PAYPAL-TX-INJ-001"
    amount = "149.00"
    status = "AUTOMATION_STREAMED"
    telemetry_class = "Zero-Click Ingestion Pipeline Active"
    note = "'; DROP TABLE transactions; --"
} | ConvertTo-Json
try {
    $null = Invoke-RestMethod -Uri "http://localhost:8080" -Method Post -Headers $headers -Body $injBody -ContentType "application/json" -TimeoutSec 5
    Write-Host "[-] Unexpected: injection payload was NOT blocked." -ForegroundColor Red
} catch {
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.Value__
        Write-Host "[?] Success: Gate blocked injection payload with HTTP Status Code: $statusCode" -ForegroundColor Green
    } else {
        Write-Host "[-] Connection error encountered." -ForegroundColor Red
    }
}

Write-Host "`n[*] Automation Step B: Launching authenticated sandbox payload..." -ForegroundColor Yellow
$simBody = @{
    transaction_id = "PAYPAL-TX-AUTO-777"
    amount = "149.00"
    status = "AUTOMATION_STREAMED"
    telemetry_class = "Zero-Click Ingestion Pipeline Active"
} | ConvertTo-Json
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8080" -Method Post -Headers $headers -Body $simBody -ContentType "application/json" -TimeoutSec 5
    if ($response.status -eq "Verified") {
        Write-Host "[?] Success: Gate successfully passed telemetry array. Response: Gateway Verified (HTTP 200)." -ForegroundColor Green
    }
} catch {
    Write-Host "[-] Request failed or timed out. Check if background engine is listening on 8080." -ForegroundColor Red
}

Write-Host "`n[*] Automation Step C: Triggering out-of-band AI synthesis engine..." -ForegroundColor Yellow
python (Join-Path $Root "pipeline\ai_analyzer.py")

Write-Host "`n====================================================" -ForegroundColor Cyan
Write-Host "[?] AUTOMATION PIPELINE RUN COMPLETE" -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "[*] Outputting final CISO compliance report matrix below:`n" -ForegroundColor Gray
$report = Join-Path $Root "dashboard\ai_compliance_report.json"
if (Test-Path $report) { Get-Content -Path $report } else { Write-Error "CRITICAL: AI Compliance output data target missing." }
Write-Host "`n====================================================" -ForegroundColor Cyan
