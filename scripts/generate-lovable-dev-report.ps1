# Genera reporte MD en Reports/ a partir de un run de Lovable Sync
param(
  [Parameter(Mandatory = $true)]
  [string]$RunId,
  [string]$Repo = "doeventsrepo/DoEventsCICD",
  [string]$WebBranch = "feature/cicd/dev-automation",
  [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$CicdRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutDir) { $OutDir = Join-Path $CicdRoot "Reports" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "gh no autenticado" }

$run = gh run view $RunId --repo $Repo --json conclusion,createdAt,displayTitle,url,headSha | ConvertFrom-Json
$date = ([DateTime]$run.createdAt).ToString("yyyy-MM-dd")
$outFile = Join-Path $OutDir "$date-lovable-sync-dev-run-$RunId.md"

# Extraer SHA Lovable y manifiesto de logs
$log = gh run view $RunId --repo $Repo --log 2>$null
$lovableSha = ""
if ($log -match '"lovableSha":\s*"([a-f0-9]+)"') { $lovableSha = $Matches[1] }

$webHead = ""
try {
  $ref = gh api "repos/doeventsrepo/DoEventsWEB/git/ref/heads/$($WebBranch -replace '/','%2F')" --jq .object.sha 2>$null
  if ($ref) { $webHead = $ref.Substring(0, 8) }
} catch { $webHead = "(ver GitHub)" }

$deployOk = $log -match "Deploy DEV desde rama"
$deployLine = if ($deployOk) { ($log | Select-String "Deploy DEV desde rama" | Select-Object -Last 1).Line.Trim() } else { "No encontrado en logs" }

$content = @"
# Reporte — Sync Lovable → DoEventsWEB → DEV (auto)

| Campo | Valor |
|-------|-------|
| **Fecha** | $date |
| **Run CICD** | [$RunId]($($run.url)) |
| **Estado** | $($run.conclusion) |
| **Rama DoEventsWEB** | ``$WebBranch`` |
| **HEAD WEB (aprox)** | ``$webHead`` |
| **Rama develop** | **No modificada por CICD** |

## Lovable

- SHA detectado en logs: ``$lovableSha``
- Repo: ``doeventsrepo/discover-joyful-feed`` (main)

## Despliegue DEV

- $deployLine
- Entorno: DEV sa-east-1 — https://dev.doeventsapp.com
- Bucket: ``doevents-web-dev`` | CF: ``E1AIDTCT83PAW5``

## Política

Los cambios van solo a ramas ``feature/*``. Merge a ``develop`` es **manual** por el ingeniero.

## Detalle completo

Completar secciones de archivos/commits revisando:
- ``gh run view $RunId --repo $Repo --log``
- ``https://github.com/doeventsrepo/DoEventsWEB/commits/$WebBranch``

---
_Generado por generate-lovable-dev-report.ps1 — $(Get-Date -Format "yyyy-MM-dd HH:mm") UTC_
"@

Set-Content -Path $outFile -Value $content -Encoding UTF8
Write-Host "Reporte: $outFile"
