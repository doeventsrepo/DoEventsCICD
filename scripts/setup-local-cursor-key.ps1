# Configura la MISMA CURSOR_API_KEY que GitHub (no crear key nueva)
param(
  [string]$CicdRoot = "",
  [string]$Key = "",
  [switch]$FromClipboard,
  [switch]$SetUserEnv,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
if (-not $CicdRoot) { $CicdRoot = Split-Path $PSScriptRoot -Parent }
$localEnv = Join-Path $CicdRoot "simulation\local.env"
$example = Join-Path $CicdRoot "simulation\local.env.example"

Write-Host "=== Setup CURSOR_API_KEY local (misma que GitHub) ===" -ForegroundColor Cyan

# Verificar secret en GitHub
$ghOk = $false
try {
  gh auth status 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $meta = gh api repos/doeventsrepo/DoEventsCICD/actions/secrets/CURSOR_API_KEY 2>$null | ConvertFrom-Json
    if ($meta.name) {
      Write-Host "GitHub secret CURSOR_API_KEY: OK (desde $($meta.updated_at))" -ForegroundColor Green
      $ghOk = $true
    }
  }
} catch { Write-Host "GitHub CLI: no verificado" -ForegroundColor Yellow }

if (-not $Key -and $FromClipboard) {
  $Key = Get-Clipboard -ErrorAction SilentlyContinue
  if ($Key) { $Key = $Key.Trim() }
}

if (-not $Key) {
  Write-Host ""
  Write-Host "Pega la MISMA API key de Cursor que configuraste en GitHub (2026-06-19)." -ForegroundColor White
  Write-Host "Obtenerla en: https://cursor.com/settings -> API Keys" -ForegroundColor DarkGray
  $secure = Read-Host "CURSOR_API_KEY" -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { $Key = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  }
}

if (-not $Key -or $Key.Length -lt 10) {
  throw "CURSOR_API_KEY invalida o vacia"
}

if (-not (Test-Path $localEnv) -and (Test-Path $example)) {
  Copy-Item $example $localEnv
}

$lines = if (Test-Path $localEnv) { Get-Content $localEnv -Encoding UTF8 } else { @() }
$out = New-Object System.Collections.Generic.List[string]
$replaced = $false
foreach ($line in $lines) {
  if ($line -match '^\s*#?\s*CURSOR_API_KEY=') {
    if (-not $replaced) {
      $out.Add("CURSOR_API_KEY=$Key")
      $replaced = $true
    }
    continue
  }
  $out.Add($line)
}
if (-not $replaced) {
  $out.Insert(0, "CURSOR_API_KEY=$Key")
}
if (-not ($out -match 'Usar la MISMA CURSOR_API_KEY')) {
  $out.Insert(0, "# Usar la MISMA CURSOR_API_KEY que GitHub secret CURSOR_API_KEY (doeventsrepo/DoEventsCICD)")
}

if ($DryRun) {
  Write-Host "[dry-run] Se escribiria CURSOR_API_KEY en $localEnv (len=$($Key.Length))" -ForegroundColor Gray
  exit 0
}

Set-Content -Path $localEnv -Value ($out -join "`n") -Encoding UTF8
Write-Host "Escrito: $localEnv" -ForegroundColor Green

if ($SetUserEnv) {
  [Environment]::SetEnvironmentVariable("CURSOR_API_KEY", $Key, "User")
  Write-Host "Variable de usuario CURSOR_API_KEY persistida" -ForegroundColor Green
}

Write-Host ""
Write-Host "Probar:" -ForegroundColor Cyan
Write-Host "  cd DoEventsCICD; .\scripts\run-backend-sync-dev.ps1 -DryRun -SkipDeploy"
