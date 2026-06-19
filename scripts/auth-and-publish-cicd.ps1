# Autentica en GitHub y publica DoEventsCICD (+ ramas feature en WEB/Back/IA).
# Uso:
#   $env:GH_TOKEN = "ghp_..."   # PAT con scope repo (+ workflow si creas repos)
#   .\scripts\auth-and-publish-cicd.ps1
# O:
#   .\scripts\auth-and-publish-cicd.ps1 -Token "ghp_..."

param(
  [string]$Token = $env:GH_TOKEN,
  [switch]$CicdOnly,
  [switch]$CreateRepoIfMissing
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$CicdDir = Join-Path $Root "DoEventsCICD"

if (-not $Token) {
  Write-Host "Falta token. Opciones:" -ForegroundColor Yellow
  Write-Host "  1) gh auth login --web  (navegador + codigo dispositivo)"
  Write-Host "  2) `$env:GH_TOKEN = 'ghp_...'; .\scripts\auth-and-publish-cicd.ps1"
  exit 1
}

$env:GH_TOKEN = $Token
$Token | gh auth login --with-token
gh auth setup-git
Write-Host "GitHub: $(gh api user -q .login)" -ForegroundColor Green

Push-Location $CicdDir
try {
  $repoExists = $false
  try {
    gh repo view doeventsrepo/DoEventsCICD --json name -q .name | Out-Null
    $repoExists = $true
    Write-Host "Repo doeventsrepo/DoEventsCICD existe." -ForegroundColor Green
  } catch {
    Write-Host "Repo doeventsrepo/DoEventsCICD no visible (no existe o sin acceso)." -ForegroundColor Yellow
  }

  if (-not $repoExists -and $CreateRepoIfMissing) {
    Write-Host "Creando repo privado en org doeventsrepo..." -ForegroundColor Cyan
    gh repo create doeventsrepo/DoEventsCICD --private `
      --description "Orquestacion CI/CD Lovable -> Cursor -> DoEventsWEB DEV" `
      --source . --remote origin --push
    Write-Host "DoEventsCICD publicado (repo nuevo)." -ForegroundColor Green
  } else {
    git push -u origin main 2>&1 | Write-Host
    Write-Host "DoEventsCICD main publicado." -ForegroundColor Green
  }
} finally {
  Pop-Location
}

if ($CicdOnly) { exit 0 }

$branch = "feature/cicd/dev-automation"
$others = @("DoEventsWEB", "DoEventsBack", "DoEventsIA")
foreach ($name in $others) {
  $repo = Join-Path $Root $name
  if (-not (Test-Path (Join-Path $repo ".git"))) { continue }
  Push-Location $repo
  try {
    Write-Host "`n=== $name -> origin/$branch ===" -ForegroundColor Cyan
    git push -u origin "HEAD:$branch" 2>&1 | Write-Host
  } catch {
    Write-Warning "Push fallo en ${name}: $_"
  } finally {
    Pop-Location
  }
}

Write-Host "`nSiguiente: secretos environment 'dev' en GitHub (GITHUB_SECRETS_DEV.md)" -ForegroundColor Yellow
