# Prepara copia sandbox de DoEventsWEB (no toca el repo productivo)
param(
    [string]$SourceWeb = "..\..\DoEventsWEB",
    [string]$DestWeb = ".\sandbox\DoEventsWEB",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$SourceWeb = Resolve-Path $SourceWeb
$DestRoot = Join-Path $PSScriptRoot "sandbox\DoEventsWEB"

if ((Test-Path $DestRoot) -and -not $Force) {
    Write-Host "Sandbox ya existe: $DestRoot (usa -Force para recrear)"
} else {
    if (Test-Path $DestRoot) { Remove-Item -Recurse -Force $DestRoot }
    New-Item -ItemType Directory -Force -Path (Split-Path $DestRoot) | Out-Null
    Write-Host "Copiando DoEventsWEB -> sandbox (sin node_modules/dist/.git)..."
    robocopy $SourceWeb $DestRoot /E /XD node_modules dist .git .vite coverage packages\shell\@mf-types /XF *.log /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy fallo con codigo $LASTEXITCODE" }
}

# Bootstrap ReglasAgente desde plantillas CICD (solo en sandbox)
$CicdTemplates = Resolve-Path "..\templates\ReglasAgente"
$AgentDir = Join-Path $DestRoot "ReglasAgente"
New-Item -ItemType Directory -Force -Path $AgentDir, (Join-Path $DestRoot "docs\changes") | Out-Null
Get-ChildItem $CicdTemplates | ForEach-Object {
    $d = Join-Path $AgentDir $_.Name
    Copy-Item $_.FullName $d -Force
}
Copy-Item (Resolve-Path "..\templates\.lovable-port-map.json") (Join-Path $DestRoot ".lovable-port-map.json") -Force
Copy-Item (Join-Path $AgentDir "impacto-backend.md") (Join-Path $DestRoot "docs\changes\lovable-backend-impact.md") -Force

Write-Host "Sandbox listo: $DestRoot"
Write-Host "ReglasAgente bootstrap desde templates (aislado del WEB productivo)."
