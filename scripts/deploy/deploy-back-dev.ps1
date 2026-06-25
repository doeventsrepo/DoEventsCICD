# BSF — Despliegue selectivo de lambdas backend DEV (sa-east-1)
param(
  [Parameter(Mandatory = $true)]
  [string]$LambdaDirs,
  [string]$BackRoot = "",
  [string]$Region = "sa-east-1",
  [string]$Stage = "dev",
  [string]$RunId = "local",
  [string]$CicdRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $BackRoot) {
  $AppRoot = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
  $BackRoot = Join-Path $AppRoot "DoEventsBack"
}
if (-not $CicdRoot) {
  $CicdRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}

$LogDir = Join-Path $CicdRoot "artifacts\$RunId\backend-sync"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "deploy.log"
$JsonLog = Join-Path $LogDir "errors.jsonl"

function Write-BsfLog($event, $level, $message, $lambdaDir = $null, $error = $null) {
  $entry = @{
    ts = (Get-Date).ToUniversalTime().ToString("o")
    event = $event
    level = $level
    message = $message
    lambdaDir = $lambdaDir
    error = $error
    fixApplied = $false
  } | ConvertTo-Json -Compress
  Add-Content -Path $JsonLog -Value $entry
  $line = "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] [$level] $message"
  Write-Host $line
  Add-Content -Path $LogFile -Value $line
}

$dirs = $LambdaDirs -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if (-not $dirs) {
  Write-BsfLog "deploy_skip" "info" "Sin lambdas para desplegar"
  exit 0
}

$failed = @()
$deployed = @()

foreach ($dir in $dirs) {
  $servicePath = Join-Path $BackRoot $dir
  if (-not (Test-Path $servicePath)) {
    Write-BsfLog "deploy_skip" "warn" "Lambda dir no existe: $dir" $dir
    $failed += $dir
    continue
  }

  $config = Join-Path $servicePath "serverless.dev.yml"
  if (-not (Test-Path $config)) {
    Write-BsfLog "deploy_skip" "warn" "serverless.dev.yml no encontrado en $dir" $dir
    $failed += $dir
    continue
  }

  Write-BsfLog "deploy_start" "info" "Desplegando $dir en $Region/$Stage" $dir
  Push-Location $servicePath
  try {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    npx serverless deploy --config serverless.dev.yml --stage $Stage --region $Region 2>&1 | Tee-Object -FilePath $LogFile -Append
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) {
      Write-BsfLog "deploy_failed" "error" "Deploy falló para $dir (exit $code)" $dir "exit code $code"
      $failed += $dir
    } else {
      Write-BsfLog "deploy_success" "info" "Deploy OK: $dir" $dir
      $deployed += $dir
    }
  } catch {
    Write-BsfLog "deploy_failed" "error" "Excepción en deploy $dir" $dir $_.Exception.Message
    $failed += $dir
  } finally {
    Pop-Location
  }
}

Write-BsfLog "deploy_complete" "info" "Desplegados: $($deployed.Count) | Fallidos: $($failed.Count)"

if ($failed.Count -gt 0) {
  exit 1
}
exit 0
