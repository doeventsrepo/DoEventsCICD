# Crea ramas CICD locales sin cambiar la rama actual ni modificar develop
param(
  [string]$Branch = "feature/cicd/dev-automation",
  [string]$BaseBranch = "develop"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$repos = @(
  (Join-Path $Root "DoEventsWEB"),
  (Join-Path $Root "DoEventsBack"),
  (Join-Path $Root "DoEventsIA")
)

foreach ($repo in $repos) {
  if (-not (Test-Path (Join-Path $repo ".git"))) {
    Write-Host "SKIP (no git): $repo" -ForegroundColor Yellow
    continue
  }
  Push-Location $repo
  try {
    $current = git branch --show-current
    $exists = git show-ref --verify --quiet "refs/heads/$Branch"; $hasLocal = ($LASTEXITCODE -eq 0)
    if ($hasLocal) {
      Write-Host "OK existe: $Branch en $(Split-Path $repo -Leaf)" -ForegroundColor DarkGray
    } else {
      git branch $Branch $BaseBranch
      Write-Host "Creada $Branch desde $BaseBranch en $(Split-Path $repo -Leaf) (sigue en $current)" -ForegroundColor Green
    }
  } finally {
    Pop-Location
  }
}

Write-Host "`nPublicar en remoto (una vez):" -ForegroundColor Cyan
Write-Host "  git -C DoEventsWEB push -u origin feature/cicd/dev-automation"
Write-Host "  git -C DoEventsBack push -u origin feature/cicd/dev-automation"
Write-Host "  git -C DoEventsIA push -u origin feature/cicd/dev-automation"
