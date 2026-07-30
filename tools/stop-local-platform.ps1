$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"

function Stop-ManagedProcess {
    param(
        [string]$Name,
        [string]$StatePath
    )

    if (-not (Test-Path -LiteralPath $StatePath)) {
        Write-Host "$Name üçün idarə olunan proses qeydi yoxdur."
        return
    }

    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $process = Get-Process -Id ([int]$state.pid) -ErrorAction SilentlyContinue

    if ($null -eq $process) {
        Remove-Item -LiteralPath $StatePath -Force
        Write-Host "$Name artıq dayanıb."
        return
    }

    if ($process.StartTime.ToFileTimeUtc() -ne [long]$state.start_time_filetime) {
        throw "$Name proses qeydi başqa prosesə aiddir; təhlükəsizlik üçün dayandırılmadı."
    }

    & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
    Remove-Item -LiteralPath $StatePath -Force
    Write-Host "$Name dayandırıldı."
}

Stop-ManagedProcess `
    -Name "Frontend" `
    -StatePath (Join-Path $runtimeRoot "frontend-process.json")
Stop-ManagedProcess `
    -Name "Backend" `
    -StatePath (Join-Path $runtimeRoot "backend-process.json")
