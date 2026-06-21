# DSF — Vigilancia en segundo plano de gap-empalme hasta objetivo (sim + 0 gaps)
# Uso:
#   .\scripts\run-gap-batch-watchdog.ps1              # lanza batch-loop en GitHub (recomendado)
#   .\scripts\run-gap-batch-watchdog.ps1 -Chain       # encadena gap-empalme individuales
#   .\scripts\run-gap-batch-watchdog.ps1 -Poll -RunId 27904918660
param(
    [switch]$Chain,
    [switch]$Poll,
    [string]$RunId = "",
    [double]$Target = 98,
    [int]$MaxBatches = 25,
    [int]$MaxRuns = 15,
    [switch]$NoDeploy,
    [switch]$AllowPartial,
    [switch]$ThenLaunch,
    [string]$LogDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Root "scripts\lovable-sync\gap-batch-watchdog.py"
if (-not $LogDir) { $LogDir = Join-Path $Root "artifacts\gap-watchdog" }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$Log = Join-Path $LogDir "watchdog-$ts.log"
$Status = Join-Path $LogDir "gap-watchdog-status.json"

if (-not $env:GH_TOKEN) {
    try { $env:GH_TOKEN = gh auth token 2>$null } catch { }
}
if (-not $env:GH_TOKEN) {
    Write-Error "GH_TOKEN requerido (gh auth login)"
}

$pyArgs = @(
    $Script,
    "--status-file", $Status,
    "--target", $Target,
    "--max-batches", $MaxBatches,
    "--max-runs", $MaxRuns
)
if ($Chain) { $pyArgs += @("--mode", "chain") }
elseif ($Poll) {
    if (-not $RunId) { Write-Error "Use -RunId con -Poll" }
    $pyArgs += @("--mode", "poll", "--run-id", $RunId)
}
else { $pyArgs += @("--mode", "launch") }
if ($NoDeploy) { $pyArgs += "--no-deploy" }
if ($AllowPartial) { $pyArgs += "--allow-partial" }
if ($ThenLaunch) { $pyArgs += "--then-launch" }

Write-Host "DSF Gap Watchdog — log: $Log"
Write-Host "Estado: $Status"
Write-Host "Modo: $(if ($Chain) { 'chain' } elseif ($Poll) { 'poll' } else { 'launch (batch-loop)' })"

$job = Start-Job -ScriptBlock {
    param($PyArgs, $LogPath)
    & python @PyArgs *>&1 | Tee-Object -FilePath $LogPath
    exit $LASTEXITCODE
} -ArgumentList (,$pyArgs), $Log

Write-Host "Watchdog en background Job Id: $($job.Id)"
Write-Host "  Get-Job -Id $($job.Id)"
Write-Host "  Receive-Job -Id $($job.Id) -Keep"
Write-Host "  Get-Content $Log -Wait"
Write-Host "  Get-Content $Status | ConvertFrom-Json"

# Guardar referencia al job
@{
    jobId = $job.Id
    log = $Log
    statusFile = $Status
    startedAt = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json | Set-Content (Join-Path $LogDir "watchdog-job-$ts.json")
