# Elimina ramas huerfanas feature/lovable/adapt-* en DoEventsWEB.
# La automatizacion usa SOLO feature/cicd/dev-automation.
param(
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue

$branches = gh api repos/doeventsrepo/DoEventsWEB/branches --paginate -q '.[].name' |
  Where-Object { $_ -like 'feature/lovable/adapt-*' }

if (-not $branches) {
  Write-Host "No hay ramas feature/lovable/adapt-*" -ForegroundColor Green
  exit 0
}

Write-Host "Ramas adapt-* encontradas:" -ForegroundColor Yellow
$branches | ForEach-Object { Write-Host "  $_" }

foreach ($b in $branches) {
  if ($DryRun) {
    Write-Host "[dry-run] eliminaria $b" -ForegroundColor Cyan
  } else {
    gh api -X DELETE "repos/doeventsrepo/DoEventsWEB/git/refs/heads/$($b -replace '/','%2F')" 2>&1 | Out-Null
    Write-Host "Eliminada: $b" -ForegroundColor Green
  }
}
