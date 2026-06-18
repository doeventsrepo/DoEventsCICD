# Publica ramas feature/cicd/dev-automation y DoEventsCICD main (sin tocar develop)
param(
  [string]$Branch = "feature/cicd/dev-automation",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

$repos = @(
  @{ Path = (Join-Path $Root "DoEventsWEB"); PushBranch = $Branch },
  @{ Path = (Join-Path $Root "DoEventsBack"); PushBranch = $Branch },
  @{ Path = (Join-Path $Root "DoEventsIA"); PushBranch = $Branch },
  @{ Path = (Join-Path $Root "DoEventsCICD"); PushBranch = "main" }
)

foreach ($r in $repos) {
  $repo = $r.Path
  $branch = $r.PushBranch
  if (-not (Test-Path (Join-Path $repo ".git"))) {
    Write-Host "SKIP (no git): $repo" -ForegroundColor Yellow
    continue
  }
  Push-Location $repo
  try {
    $current = git branch --show-current
    Write-Host "`n=== $(Split-Path $repo -Leaf) (actual: $current) -> origin/$branch ===" -ForegroundColor Cyan
    if ($DryRun) {
      git status -sb
      continue
    }
    git push -u origin "HEAD:$branch" 2>&1 | Write-Host
  } catch {
    Write-Warning "Push falló en $(Split-Path $repo -Leaf): $_"
  } finally {
    Pop-Location
  }
}

Write-Host "`nConfigura secretos en GitHub (ver GITHUB_SECRETS_DEV.md)." -ForegroundColor Yellow
