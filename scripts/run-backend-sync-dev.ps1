# BSF — Runner local Backend Sync Framework
param(
  [string]$LovableDir = "",
  [string]$WebDir = "",
  [string]$BackDir = "",
  [string]$CicdDir = "",
  [string]$RunId = "",
  [switch]$DryRun,
  [switch]$SkipDeploy,
  [switch]$SkipImplement,
  [switch]$UseCi
)

$ErrorActionPreference = "Stop"
if (-not $CicdDir) { $CicdDir = Split-Path $PSScriptRoot -Parent }
$AppRoot = Split-Path $CicdDir -Parent

if (-not $LovableDir) { $LovableDir = Join-Path $AppRoot "discover-joyful-feed" }
if (-not $WebDir) { $WebDir = Join-Path $AppRoot "DoEventsWEB" }
if (-not $BackDir) { $BackDir = Join-Path $AppRoot "DoEventsBack" }
if (-not $RunId) { $RunId = "local-bsf-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }

. (Join-Path $CicdDir "scripts\load-dsf-secrets.ps1")
$secret = Import-DsfSecrets -CicdRoot $CicdDir

# Sin key local: usar GitHub Actions con secret CURSOR_API_KEY existente
if ((-not $secret.ok) -and ($UseCi -or (-not $DryRun -and -not $SkipImplement))) {
  if (-not $RunId) { $RunId = "local-bsf-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
  Write-Host "Sin CURSOR_API_KEY local - ejecutando BSF en CI (secret GitHub existente)..." -ForegroundColor Cyan
  gh workflow run dsf-backend-sync-dev.yml --repo doeventsrepo/DoEventsCICD `
    -f "run_id=$RunId" `
    -f "dry_run=$($DryRun.ToString().ToLower())" `
    -f "skip_deploy=$($SkipDeploy.ToString().ToLower())"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  Write-Host "Workflow iniciado. Ver: https://github.com/doeventsrepo/DoEventsCICD/actions/workflows/dsf-backend-sync-dev.yml" -ForegroundColor Green
  Write-Host "RunId: $RunId"
  exit 0
}

if ($secret.ok) {
  Write-Host "CURSOR_API_KEY: cargada desde $($secret.source)" -ForegroundColor DarkGray
} elseif (-not $DryRun -and -not $SkipImplement) {
  Write-Host $secret.hint -ForegroundColor Yellow
  Write-Host "Continuando sin implement/healer Cursor (dry-run parcial)..." -ForegroundColor Yellow
  $DryRun = $true
}

$env:CICD_DIR = $CicdDir
$env:LOVABLE_DIR = $LovableDir
$env:WEB_DIR = $WebDir
$env:BACK_DIR = $BackDir
$env:DSF_LOCAL_RUN_ID = $RunId
$env:GITHUB_RUN_ID = $RunId
$env:BSF_WAIT_CURSOR = "1"

$manifest = Join-Path $LovableDir "lovable-change-manifest.json"
if (-not (Test-Path $manifest)) {
  $manifest = Join-Path $CicdDir "lovable-change-manifest.json"
}
$env:DSF_CHANGE_MANIFEST = $manifest

Write-Host "=== BSF Backend Sync ===" -ForegroundColor Cyan
Write-Host "RunId: $RunId"
Write-Host "Lovable: $LovableDir"
Write-Host "WEB: $WebDir"
Write-Host "BACK: $BackDir"
Write-Host "Manifest: $manifest"

$args_py = @(
  (Join-Path $CicdDir "scripts\agents\run-backend-sync-orchestrator.py"),
  "--lovable-dir", $LovableDir,
  "--web-dir", $WebDir,
  "--back-dir", $BackDir,
  "--cicd-dir", $CicdDir,
  "--change-manifest", $manifest,
  "--run-id", $RunId
)
if ($DryRun) { $args_py += "--dry-run" }
if ($SkipDeploy) { $args_py += "--skip-deploy" }
if ($SkipImplement) { $args_py += "--skip-implement" }

python @args_py
exit $LASTEXITCODE
