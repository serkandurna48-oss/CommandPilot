# CommandPilot — Pruefbefehl (JARVIS-A1, Aufgabe 1)
# Usage (aus dem Repo-Root): .\scripts\check.ps1
# Laeuft nacheinander: Backend-Pytest, Frontend-Type-Check, Frontend-Lint.
# Gibt am Ende eine Zusammenfassung aus und setzt den Exit-Code entsprechend
# (0 = alles gruen, 1 = mindestens ein Check rot).
#
# npm run build ist bewusst nicht enthalten — es scheitert ohne .env am
# Prerendering aller geschuetzten Seiten. Das ist bekannt und kein
# Regressionssignal (siehe CLAUDE.md).

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$frontendDir = Join-Path $repoRoot "frontend"

$script:checks = @()

function Invoke-Check {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$ArgumentList
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $FilePath @ArgumentList
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $script:checks += [PSCustomObject]@{ Name = $Name; ExitCode = $exitCode }
}

Invoke-Check -Name "backend: pytest" `
    -WorkingDirectory $repoRoot `
    -FilePath $pythonExe `
    -ArgumentList @("-m", "pytest", "backend/tests", "-q")

Invoke-Check -Name "frontend: type-check" `
    -WorkingDirectory $frontendDir `
    -FilePath "npm" `
    -ArgumentList @("run", "type-check")

Invoke-Check -Name "frontend: lint" `
    -WorkingDirectory $frontendDir `
    -FilePath "npm" `
    -ArgumentList @("run", "lint")

Write-Host ""
Write-Host "==================== Zusammenfassung ====================" -ForegroundColor Yellow
$overallExit = 0
foreach ($c in $script:checks) {
    if ($c.ExitCode -eq 0) {
        Write-Host ("  OK    {0}" -f $c.Name) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  {0} (exit {1})" -f $c.Name, $c.ExitCode) -ForegroundColor Red
        $overallExit = 1
    }
}
Write-Host "==========================================================" -ForegroundColor Yellow

exit $overallExit
