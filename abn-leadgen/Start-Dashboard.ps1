[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8767,
    [switch]$NoBrowser,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$dashboardDirectory = $PSScriptRoot
$dashboardExitCode = 0

try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv was not found. Install uv and Python 3.12, then run this launcher again. See README.md.'
    }
    Push-Location -LiteralPath $dashboardDirectory
    try {
        Write-Host 'Preparing the local ABN Lead Engine dashboard...' -ForegroundColor Cyan
        & uv sync --frozen
        if ($LASTEXITCODE -ne 0) {
            throw 'Dependency setup failed. Check the output above and your network connection.'
        }
        $dashboardResultText = & uv run --frozen python ops/local_dashboard.py start --port $Port
        if ($LASTEXITCODE -ne 0) {
            throw ($dashboardResultText -join [Environment]::NewLine)
        }
        $dashboardResult = ($dashboardResultText -join [Environment]::NewLine) | ConvertFrom-Json
        if ($dashboardResult.status -ne 'ready') {
            throw 'The dashboard did not confirm that it was ready.'
        }
        Write-Host ''
        Write-Host ('Dashboard ready: ' + $dashboardResult.url) -ForegroundColor Green
        Write-Host 'The current dashboard uses synthetic practice data. Live sources remain unconfigured.'
        Write-Host 'You can close this window; the dashboard keeps running in the background.'
        Write-Host ('To stop: uv run --project "' + $dashboardDirectory + '" python "' +
                    (Join-Path $dashboardDirectory 'ops/local_dashboard.py') + '" stop --port ' + $Port)
        if (-not $NoBrowser) {
            Start-Process $dashboardResult.url
        }
    }
    finally {
        Pop-Location
    }
}
catch {
    Write-Host ''
    Write-Host ('Dashboard could not start: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Setup help: ' + (Join-Path $dashboardDirectory 'README.md'))
    $dashboardExitCode = 1
    if (-not $NoPause) {
        [void](Read-Host 'Press Enter to close')
    }
}

exit $dashboardExitCode
