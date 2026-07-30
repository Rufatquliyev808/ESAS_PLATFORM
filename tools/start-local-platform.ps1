param(
    [int]$BackendWaitSeconds = 20,
    [int]$FrontendWaitSeconds = 30
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot "frontend"
$runtimeRoot = Join-Path $projectRoot ".runtime"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envPath = Join-Path $projectRoot ".env"

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

function Test-Url {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Save-ManagedProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$Path
    )

    @{
        pid = $Process.Id
        start_time_filetime = $Process.StartTime.ToFileTimeUtc()
    } |
        ConvertTo-Json |
        Set-Content -LiteralPath $Path -Encoding UTF8
}

function Wait-ForUrl {
    param(
        [string]$Url,
        [int]$Seconds
    )

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url -Url $Url) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python mühiti tapılmadı: $pythonPath"
}

if (-not (Test-Path -LiteralPath $envPath)) {
    throw "Lokal təhlükəsizlik konfiqurasiyası tapılmadı: $envPath"
}

$backendStarted = $false
$backendProcess = $null

if (Test-Url -Url "http://127.0.0.1:8000/health") {
    Write-Host "Backend artıq işləyir."
}
else {
    $backendProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @(
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--env-file",
            ".env"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeRoot "backend.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "backend-error.log") `
        -PassThru

    Save-ManagedProcess `
        -Process $backendProcess `
        -Path (Join-Path $runtimeRoot "backend-process.json")
    $backendStarted = $true

    if (-not (Wait-ForUrl `
        -Url "http://127.0.0.1:8000/health" `
        -Seconds $BackendWaitSeconds)) {
        Stop-ProcessTree -ProcessId $backendProcess.Id
        Remove-Item `
            -LiteralPath (Join-Path $runtimeRoot "backend-process.json") `
            -Force `
            -ErrorAction SilentlyContinue
        throw "Backend sağlamlıq yoxlamasından keçmədi. .runtime\backend-error.log faylını yoxlayın."
    }

    Write-Host "Backend başladıldı və verilənlər bazası yazma yoxlamasından keçdi."
}

if (Test-Url -Url "http://localhost:3000") {
    Write-Host "Frontend artıq işləyir."
}
else {
    $npmCommand = Get-Command npm.cmd -ErrorAction Stop
    $frontendProcess = Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $frontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runtimeRoot "frontend.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "frontend-error.log") `
        -PassThru

    Save-ManagedProcess `
        -Process $frontendProcess `
        -Path (Join-Path $runtimeRoot "frontend-process.json")

    if (-not (Wait-ForUrl `
        -Url "http://localhost:3000" `
        -Seconds $FrontendWaitSeconds)) {
        Stop-ProcessTree -ProcessId $frontendProcess.Id
        Remove-Item `
            -LiteralPath (Join-Path $runtimeRoot "frontend-process.json") `
            -Force `
            -ErrorAction SilentlyContinue
        if ($backendStarted) {
            Stop-ProcessTree -ProcessId $backendProcess.Id
            Remove-Item `
                -LiteralPath (Join-Path $runtimeRoot "backend-process.json") `
                -Force `
                -ErrorAction SilentlyContinue
        }
        throw "Frontend vaxtında açılmadı. .runtime\frontend-error.log faylını yoxlayın."
    }

    Write-Host "Frontend başladıldı."
}

Write-Host ""
Write-Host "ESAS Platform hazırdır: http://localhost:3000"
