# Configura environment 'dev' y secretos del pipeline en doeventsrepo/DoEventsCICD
# Requiere: gh auth login O $env:GH_TOKEN con permisos admin:repo_hook / secrets
param(
  [string]$Repo = "doeventsrepo/DoEventsCICD",
  [string]$EnvName = "dev",
  [ValidateSet('envDevelop', 'envRelease', 'envMain')]
  [string]$EnvConfig = "envDevelop",
  [switch]$SkipAwsFromProfile,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Require-Gh {
  gh auth status 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "gh no autenticado. Ejecuta: gh auth login  o  `$env:GH_TOKEN = 'ghp_...'"
  }
}

function Set-GhSecret {
  param([string]$Name, [string]$Value, [switch]$Env)
  if (-not $Value) {
    Write-Host "  SKIP $Name (valor vacio)" -ForegroundColor Yellow
    return
  }
  if ($DryRun) {
    Write-Host "  [dry-run] secret $Name ($($Value.Length) chars)" -ForegroundColor Gray
    return
  }
  $Value | gh secret set $Name --repo $Repo @($(if ($Env) { @("--env", $EnvName) }))
  if ($LASTEXITCODE -ne 0) { throw "Fallo al guardar $Name" }
  Write-Host "  OK $Name" -ForegroundColor Green
}

Require-Gh

$envConfigRoot = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "envConfig"
$envConfigFile = Join-Path $envConfigRoot "$EnvConfig\environment.json"
$envCfg = $null
if (Test-Path $envConfigFile) {
  $envCfg = Get-Content $envConfigFile -Raw | ConvertFrom-Json
  if ($envCfg.cicd.githubEnvironment) { $EnvName = $envCfg.cicd.githubEnvironment }
  Write-Host "Config: $envConfigFile -> GitHub environment '$EnvName'" -ForegroundColor DarkGray
}

Write-Host "=== Crear environment '$EnvName' si no existe ===" -ForegroundColor Cyan
if (-not $DryRun) {
  '{}' | gh api -X PUT "repos/$Repo/environments/$EnvName" --input - 2>$null | Out-Null
}

# Valores desde envConfig, env local o defaults
$cfDev = $env:CLOUDFRONT_DISTRIBUTION_ID_DEV
if (-not $cfDev -and $envCfg) { $cfDev = $envCfg.web.cloudFrontDistributionId }
if (-not $cfDev) { $cfDev = "E1AIDTCT83PAW5" }
$s3Bucket = $env:S3_BUCKET_DEV
if (-not $s3Bucket -and $envCfg) { $s3Bucket = $envCfg.web.bucket }
if (-not $s3Bucket) { $s3Bucket = "doevents-web-dev" }
$mapsKey = $env:VITE_GOOGLE_MAPS_API_KEY
if (-not $mapsKey -and (Test-Path "c:\DoEvents\AplicacionWEB\DoEventsWEB\.env.devaws")) {
  $line = Get-Content "c:\DoEvents\AplicacionWEB\DoEventsWEB\.env.devaws" | Where-Object { $_ -match '^VITE_GOOGLE_MAPS_API_KEY=' } | Select-Object -First 1
  if ($line) { $mapsKey = ($line -split '=', 2)[1].Trim() }
}

$awsKeyId = $env:AWS_ACCESS_KEY_ID_DEV
$awsSecret = $env:AWS_SECRET_ACCESS_KEY_DEV
$credsFile = Join-Path $PSScriptRoot "..\infrastructure\dev-sa-east-1\cicd-github-dev-credentials.json"
if ((-not $awsKeyId -or -not $awsSecret) -and (Test-Path $credsFile)) {
  $fileCreds = Get-Content $credsFile -Raw | ConvertFrom-Json
  $awsKeyId = $fileCreds.accessKeyId
  $awsSecret = $fileCreds.secretAccessKey
}
if (-not $SkipAwsFromProfile -and (-not $awsKeyId -or -not $awsSecret)) {
  $credFile = Join-Path $env:USERPROFILE ".aws\credentials"
  if (Test-Path $credFile) {
    $ini = Get-Content $credFile -Raw
    if ($ini -match '(?ms)\[default\][^\[]*aws_access_key_id\s*=\s*(\S+)') { $awsKeyId = $matches[1] }
    if ($ini -match '(?ms)\[default\][^\[]*aws_secret_access_key\s*=\s*(\S+)') { $awsSecret = $matches[1] }
  }
}

$webPat = $env:DOEVENTS_WEB_PAT
if (-not $webPat) { $webPat = $env:GH_TOKEN }

$cursorKey = $env:CURSOR_API_KEY

Write-Host "`n=== Secretos REPO (adapt + prepare) ===" -ForegroundColor Cyan
Set-GhSecret -Name "DOEVENTS_WEB_PAT" -Value $webPat
Set-GhSecret -Name "CURSOR_API_KEY" -Value $cursorKey

Write-Host "`n=== Secretos ENVIRONMENT '$EnvName' (deploy DEV) ===" -ForegroundColor Cyan
Set-GhSecret -Name "AWS_ACCESS_KEY_ID_DEV" -Value $awsKeyId -Env
Set-GhSecret -Name "AWS_SECRET_ACCESS_KEY_DEV" -Value $awsSecret -Env
Set-GhSecret -Name "CLOUDFRONT_DISTRIBUTION_ID_DEV" -Value $cfDev -Env
Set-GhSecret -Name "VITE_GOOGLE_MAPS_API_KEY" -Value $mapsKey -Env
Set-GhSecret -Name "S3_BUCKET_DEV" -Value $s3Bucket -Env

Write-Host "`n=== Verificacion ===" -ForegroundColor Cyan
gh secret list --repo $Repo
gh secret list --repo $Repo --env $EnvName

$missing = @()
if (-not $webPat) { $missing += "DOEVENTS_WEB_PAT (PAT push feature/* en DoEventsWEB)" }
if (-not $cursorKey) { $missing += "CURSOR_API_KEY (Cursor API)" }
if (-not $awsKeyId -or -not $awsSecret) { $missing += "AWS_*_DEV (IAM S3+CloudFront sa-east-1)" }

if ($missing.Count) {
  Write-Host "`nFaltan secretos (configura env y re-ejecuta):" -ForegroundColor Yellow
  $missing | ForEach-Object { Write-Host "  - $_" }
} else {
  Write-Host "`nSecretos principales configurados." -ForegroundColor Green
  Write-Host "Prueba: gh workflow run lovable-sync-to-web.yml --repo $Repo -f run_agent=false -f deploy_dev_after=true"
}
