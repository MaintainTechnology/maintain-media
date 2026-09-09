param(
  [ValidateSet('start', 'status', 'stop')][string]$Action = 'start',
  [ValidateRange(1024, 65535)][int]$Port = 3001,
  [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$siteRoot = $PSScriptRoot
$runtimeDir = Join-Path $siteRoot '.local'
$recordPath = Join-Path $runtimeDir "website-$Port.json"
$nextCli = Join-Path $siteRoot 'node_modules/next/dist/bin/next'
$url = "http://127.0.0.1:$Port/abn-lead-gen/dashboard"

function Get-OwnedWebsite {
  if (-not (Test-Path -LiteralPath $recordPath)) { return $null }
  try {
    $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$record.pid)"
    if ($process -and $process.CommandLine.Contains($nextCli) -and $process.CommandLine.Contains("--port $Port")) { return $process }
  } catch { }
  return $null
}

function Get-ReadyWebsite {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/abn-lead-gen/sign-in" -TimeoutSec 3
    return $response.StatusCode -eq 200 -and $response.Headers['X-Maintain-Workspace'] -eq 'abn-lead-gen'
  } catch { return $false }
}

$owned = Get-OwnedWebsite
if ($Action -eq 'status') {
  @{ status = $(if ($owned -and (Get-ReadyWebsite)) { 'ready' } elseif ($owned) { 'starting_or_unhealthy' } else { 'stopped_or_unowned' }); url = $url; pid = $owned.ProcessId } | ConvertTo-Json
  exit 0
}
if ($Action -eq 'stop') {
  if ($owned) {
    # Only descendants of the verified website CLI process belong to this launch.
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($owned.ProcessId)")
    foreach ($child in $children) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $owned.ProcessId -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $recordPath -ErrorAction SilentlyContinue
  }
  Write-Output 'Website stopped if owned. The fixture engine and database remain running.'
  exit 0
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $nextCli)) { throw 'Website dependencies are missing. Run npm ci in the website directory first.' }
if (-not (Test-Path -LiteralPath (Join-Path $runtimeDir 'admin-auth.json')) -and -not $env:ABN_ADMIN_ACCOUNTS_JSON) {
  throw 'Create the first admin account with npm run admin:account before opening the dashboard.'
}

# The Python helper reuses healthy owned services and safely recovers its isolated database.
Push-Location (Join-Path (Split-Path $siteRoot -Parent) 'abn-leadgen')
try {
  & uv run --frozen python ops/local_dashboard.py start
  if ($LASTEXITCODE -ne 0) { throw 'The local lead engine could not start.' }
} finally { Pop-Location }

if ($owned) {
  if (-not (Get-ReadyWebsite)) { throw 'The owned website is not ready. Inspect .local/website-PORT-error.log, then stop and start it again.' }
} else {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($listener) { throw "Port $Port belongs to another process. It was left running. Choose another port with -Port." }
  $node = (Get-Command node -ErrorAction Stop).Source
  $process = Start-Process -FilePath $node -ArgumentList @("`"$nextCli`"", 'dev', '--hostname', '127.0.0.1', '--port', "$Port") -WorkingDirectory $siteRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "website-$Port.log") -RedirectStandardError (Join-Path $runtimeDir "website-$Port-error.log")
  @{ pid = $process.Id; url = $url; created_at = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $recordPath
  $deadline = [DateTime]::UtcNow.AddSeconds(90)
  while (-not (Get-ReadyWebsite)) {
    if ($process.HasExited -or [DateTime]::UtcNow -gt $deadline) { throw "The website did not become ready. Inspect .local/website-$Port-error.log." }
    Start-Sleep -Milliseconds 500
    $process.Refresh()
  }
}
Write-Output "ABN Lead Gen is ready: $url"
if (-not $NoBrowser) { Start-Process $url }
