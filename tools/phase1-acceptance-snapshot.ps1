param(
    [ValidateSet("Capture", "Compare")]
    [string]$Action = "Capture",
    [string]$BaselinePath = "",
    [string]$Label = "phase1",
    [ValidateRange(0, 168)]
    [double]$MinimumHours = 24
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime\phase1-acceptance"
$envPath = Join-Path $projectRoot ".env"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backendUrl = "http://127.0.0.1:8000"

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separator).Trim()
        if ($key -ne $Name) {
            continue
        }

        $value = $trimmed.Substring($separator + 1).Trim()
        if (
            $value.Length -ge 2 -and
            (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            )
        ) {
            return $value.Substring(1, $value.Length - 2)
        }
        return $value
    }

    throw "Lokal konfiqurasiyada $Name tapılmadı."
}

function Invoke-BackendJson {
    param(
        [string]$Method,
        [string]$Path,
        [hashtable]$Headers = @{},
        [object]$Body = $null
    )

    $parameters = @{
        Uri = "$backendUrl$Path"
        Method = $Method
        Headers = $Headers
        TimeoutSec = 10
        UseBasicParsing = $true
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json"
        $parameters.Body = $Body | ConvertTo-Json -Depth 10
    }

    $response = Invoke-WebRequest @parameters
    return $response.Content | ConvertFrom-Json
}

function Get-DatabaseEvidence {
    $script = @'
import json
from backend.app.database.connection import get_connection

with get_connection() as connection:
    quick_check = connection.execute("PRAGMA quick_check;").fetchone()[0]
    acknowledgement_count = connection.execute(
        "SELECT COUNT(*) FROM loss_acknowledgements;"
    ).fetchone()[0]

print(json.dumps({
    "quick_check": quick_check,
    "acknowledgement_count": acknowledgement_count,
}))
'@

    $env:PYTHONPATH = $projectRoot
    try {
        $result = $script | & $pythonPath -
        if ($LASTEXITCODE -ne 0) {
            throw "SQLite sübutu alına bilmədi."
        }
        return $result | ConvertFrom-Json
    }
    finally {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}

function Get-AcceptanceSnapshot {
    $userCode = Get-DotEnvValue -Path $envPath -Name "ESAS_USER_CODE"
    $password = Get-DotEnvValue -Path $envPath -Name "ESAS_USER_PASSWORD"
    $login = Invoke-BackendJson `
        -Method "POST" `
        -Path "/auth/login" `
        -Body @{
            user_code = $userCode
            password = $password
        }
    $headers = @{
        Authorization = "Bearer $($login.access_token)"
    }

    $health = Invoke-BackendJson -Method "GET" -Path "/health"
    $operational = Invoke-BackendJson `
        -Method "GET" `
        -Path "/status/operational" `
        -Headers $headers
    $statistics = Invoke-BackendJson `
        -Method "GET" `
        -Path "/statistics/ticks" `
        -Headers $headers
    $database = Get-DatabaseEvidence

    $bridges = @($operational.bridge_delivery.bridges)
    $rejectedEvents = 0
    $queueCount = 0
    $queueCapacity = 0
    $lossAcknowledged = $true
    foreach ($bridge in $bridges) {
        $rejectedEvents += [int64]$bridge.rejected_events
        $queueCount += [int64]$bridge.queue_count
        $queueCapacity += [int64]$bridge.queue_capacity
        if (-not [bool]$bridge.loss_acknowledged) {
            $lossAcknowledged = $false
        }
    }

    return [ordered]@{
        schema_version = 1
        label = $Label
        captured_at = (Get-Date).ToUniversalTime().ToString("o")
        health_status = $health.status
        backend_version = $health.version
        operational_status = $operational.status
        tick_stream_status = $operational.tick_stream.status
        total_ticks = [int64]$statistics.total_ticks
        queue_count = $queueCount
        queue_capacity = $queueCapacity
        rejected_events = $rejectedEvents
        loss_acknowledged = $lossAcknowledged
        sqlite_quick_check = $database.quick_check
        acknowledgement_count = [int64]$database.acknowledgement_count
        bridge_count = $bridges.Count
    }
}

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Lokal təhlükəsizlik konfiqurasiyası tapılmadı: $envPath"
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python mühiti tapılmadı: $pythonPath"
}

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$snapshot = Get-AcceptanceSnapshot
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$snapshotPath = Join-Path $runtimeRoot "$timestamp-$Label.json"
$snapshot | ConvertTo-Json -Depth 10 | Set-Content `
    -LiteralPath $snapshotPath `
    -Encoding UTF8

Write-Host "Qəbul göstəriciləri saxlanıldı: $snapshotPath"

if ($Action -eq "Capture") {
    Write-Host "Tick: $($snapshot.total_ticks)"
    Write-Host "Növbə: $($snapshot.queue_count) / $($snapshot.queue_capacity)"
    Write-Host "Rədd edilən event: $($snapshot.rejected_events)"
    Write-Host "SQLite: $($snapshot.sqlite_quick_check)"
    exit 0
}

if (-not $BaselinePath) {
    throw "Compare əməliyyatı üçün -BaselinePath verilməlidir."
}
$resolvedBaseline = Resolve-Path -LiteralPath $BaselinePath
$baseline = Get-Content `
    -LiteralPath $resolvedBaseline `
    -Encoding UTF8 `
    -Raw | ConvertFrom-Json

$elapsedHours = (
    (
        [datetime]$snapshot.captured_at -
        [datetime]$baseline.captured_at
    ).TotalHours
)
$checks = [ordered]@{
    minimum_duration_met = $elapsedHours -ge $MinimumHours
    health_ok = $snapshot.health_status -eq "ok"
    operational_ok = $snapshot.operational_status -eq "ok"
    tick_stream_active = $snapshot.tick_stream_status -eq "active"
    ticks_increased = $snapshot.total_ticks -gt [int64]$baseline.total_ticks
    queue_empty = $snapshot.queue_count -eq 0
    rejected_unchanged = (
        $snapshot.rejected_events -eq [int64]$baseline.rejected_events
    )
    loss_acknowledgement_preserved = $snapshot.loss_acknowledged
    sqlite_ok = $snapshot.sqlite_quick_check -eq "ok"
    audit_preserved = (
        $snapshot.acknowledgement_count -ge
        [int64]$baseline.acknowledgement_count
    )
}
$passed = -not ($checks.Values -contains $false)

$comparison = [ordered]@{
    schema_version = 1
    baseline_path = $resolvedBaseline.Path
    final_snapshot_path = $snapshotPath
    compared_at = (Get-Date).ToUniversalTime().ToString("o")
    required_hours = $MinimumHours
    elapsed_hours = $elapsedHours
    tick_delta = (
        [int64]$snapshot.total_ticks -
        [int64]$baseline.total_ticks
    )
    rejected_delta = (
        [int64]$snapshot.rejected_events -
        [int64]$baseline.rejected_events
    )
    checks = $checks
    result = $(if ($passed) { "PASSED" } else { "FAILED" })
}
$comparisonPath = Join-Path $runtimeRoot "$timestamp-$Label-comparison.json"
$comparison | ConvertTo-Json -Depth 10 | Set-Content `
    -LiteralPath $comparisonPath `
    -Encoding UTF8

Write-Host "Müqayisə nəticəsi: $($comparison.result)"
Write-Host "Müddət: $([math]::Round($comparison.elapsed_hours, 2)) saat"
Write-Host "Yeni tick: $($comparison.tick_delta)"
Write-Host "Yeni rədd edilən event: $($comparison.rejected_delta)"
Write-Host "Müqayisə sübutu: $comparisonPath"

if (-not $passed) {
    exit 1
}
