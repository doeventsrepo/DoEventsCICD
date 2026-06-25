# BSF — Runner local Backend Sync Framework
param(
  [string]$LovableDir = "",
  [string]$WebDir = "",
  [string]$BackDir = "",
  [string]$CicdDir = "",
  [string]$RunId = "",
  [switch]$DryRun,
  [switch]$SkipDeploy,
  [switch]$SkipImplement
)

$ErrorActionPreference = "Stop"
$CicdDir = Split-Path $PSScriptRoot -Parent
$AppRoot = Split-Path $CicdDir -Parent

if (-not $PSBoundParameters.ContainsKey('CicdDir')) { $CicdDir = $CicdDir }
if (-not $LovableDir) { $LovableDir = Join-Path (Split-Path $AppRoot -Parent) "discover-joyful-feed" }
if (-not $WebDir) { $WebDir = Join-Path (Split-Path $AppRoot -Parent) "DoEventsWEB" }
if (-not $BackDir) { $BackDir = Join-Path (Split-Path $AppRoot -Parent) "DoEventsBack" }
if (-not $RunId) { $RunId = "local-bsf-$(Get-Date -Format 'yyyyMMdd-HHmmss')" }

$env:CICD_DIR = $CicdDir
$env:LOVABLE_DIR = $LovableDir
$env:WEB_DIR = $WebDir
$env:BACK_DIR = $BackDir
$env:DSF_LOCAL_RUN_ID = $RunId
$env:GITHUB_RUN_ID = $RunId

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
