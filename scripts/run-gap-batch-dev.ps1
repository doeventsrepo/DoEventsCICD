# DSF - Cerrar gaps Lovable->WEB por lotes (Python-only, sin Cursor API)
# Siempre usa batch-index 1: tras cada lote, los gaps cerrados salen del manifiesto.
#
# Uso:
#   .\scripts\run-gap-batch-dev.ps1                    # 5 gaps, build, commit, deploy DEV
#   .\scripts\run-gap-batch-dev.ps1 -BatchSize 5 -DryRun
#   .\scripts\run-gap-batch-dev.ps1 -UntilDone -MaxBatches 20
#   .\scripts\run-gap-batch-dev.ps1 -NoDeploy -NoPush
#
param(
    [int]$BatchSize = 5,
    [int]$BatchIndex = 1,
    [double]$TargetSim = 98,
    [string]$WebBranch = "feature/cicd/dev-automation",
    [string]$WebDir = "",
    [string]$LovableDir = "",
    [string]$OutDir = "",
    [switch]$DryRun,
    [switch]$NoDeploy,
    [switch]$NoPush,
    [switch]$NoBuild,
    [switch]$UntilDone,
    [int]$MaxBatches = 30,
    [switch]$AllowDirty,
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
$CicdRoot = Split-Path -Parent $PSScriptRoot
$WebRoot = if ($WebDir) { $WebDir } else { Join-Path (Split-Path $CicdRoot -Parent) "DoEventsWEB" }
$LovableRoot = if ($LovableDir) { $LovableDir } else { Join-Path (Split-Path $CicdRoot -Parent) "discover-joyful-feed" }
$PortMap = Join-Path $WebRoot ".lovable-port-map.json"
$Artifacts = if ($OutDir) { $OutDir } else { Join-Path $CicdRoot "artifacts\gap-batch" }
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

$ComparePy = Join-Path $CicdRoot "scripts\lovable-sync\compare-design-similarity.py"
$ManifestPy = Join-Path $CicdRoot "scripts\lovable-sync\build-gap-manifest.py"
$EmpalmePy = Join-Path $CicdRoot "scripts\lovable-sync\run-gap-batch-empalme.py"
$ReportPy = Join-Path $CicdRoot "scripts\lovable-sync\generate-gap-empalme-report.py"
$FixStubsPy = Join-Path $CicdRoot "scripts\lovable-sync\fix-data-stubs-web.py"
$BootstrapPy = Join-Path $CicdRoot "scripts\lovable-sync\bootstrap-dsf-index.py"
$CompletePy = Join-Path $CicdRoot "scripts\lovable-sync\complete-dsf-lovable.py"
$DeployPs1 = Join-Path $WebRoot "infrastructure\aws\deploy-dev.ps1"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

function Sync-WebBranch {
    if (-not (Test-Path (Join-Path $WebRoot ".git"))) {
        Write-Warning "WEB sin .git - omitir checkout"
        return
    }
    Push-Location $WebRoot
    try {
        if (-not $AllowDirty) {
            $dirty = git status --porcelain 2>$null
            if ($dirty) {
                throw "DoEventsWEB tiene cambios sin commit. Usa -AllowDirty o commitea/stash primero."
            }
        }
        if (-not $SkipFetch) {
            git fetch origin $WebBranch 2>$null
            git checkout $WebBranch 2>$null
            git pull origin $WebBranch 2>$null
        }
    } finally { Pop-Location }
}

function Invoke-GapBatch {
    param([int]$Round)

    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $RunId = "local-b$Round-$ts"
    $ComparisonBefore = Join-Path $Artifacts "design-comparison-before-$RunId.json"
    $ComparisonAfter = Join-Path $Artifacts "design-comparison-after-$RunId.json"
    $GapManifest = Join-Path $Artifacts "gap-manifest-$RunId.json"
    $EmpalmeResult = Join-Path $Artifacts "gap-empalme-$RunId.json"
    $ReportMd = Join-Path $Artifacts "gap-report-$RunId.md"

    Write-Step "Bootstrap DSF (Lovable index)"
    python $BootstrapPy --lovable-dir $LovableRoot --web-dir $WebRoot
    if ($LASTEXITCODE -ne 0) { throw "bootstrap-dsf-index falló" }
    python $CompletePy --lovable-dir $LovableRoot --web-dir $WebRoot --skip-bootstrap
    if ($LASTEXITCODE -ne 0) { throw "complete-dsf-lovable falló" }

    Write-Step "Comparar diseño (baseline)"
    python $ComparePy $LovableRoot $WebRoot $PortMap $ComparisonBefore
    if ($LASTEXITCODE -ne 0) { throw "compare-design-similarity falló" }
    $before = Get-Content $ComparisonBefore -Raw | ConvertFrom-Json
    $simBefore = [double]$before.overallSimilarityPercent
    $pending = [int]$before.summary.needsAdaptation + [int]$before.missingInWebCount
    Write-Host ("Similitud: {0}% | gaps pendientes ~{1} | objetivo {2}%" -f $simBefore, $pending, $TargetSim)

    if ($simBefore -ge $TargetSim -and $pending -eq 0) {
        return @{ done = $true; simBefore = $simBefore; simAfter = $simBefore; pending = 0; applied = 0 }
    }

    Write-Step "Manifiesto batch $BatchSize (index $BatchIndex)"
    python $ManifestPy $ComparisonBefore $GapManifest `
        --batch-size $BatchSize --batch-index $BatchIndex --run-id $RunId
    if ($LASTEXITCODE -ne 0) { throw "build-gap-manifest falló" }
    $manifest = Get-Content $GapManifest -Raw | ConvertFrom-Json
    if ([int]$manifest.gapsInBatch -eq 0) {
        Write-Host "Sin gaps en este batch - fin." -ForegroundColor Yellow
        return @{ done = $true; simBefore = $simBefore; simAfter = $simBefore; pending = $manifest.totalPendingGaps; applied = 0 }
    }

    Write-Host "Batch: $($manifest.gapsInBatch) gaps / $($manifest.totalPendingGaps) total"
    $manifest.gaps | ForEach-Object { Write-Host ("  - {0} ({1}%)" -f $_.lovablePath, $_.similarityPercent) }

    if ($DryRun) {
        Write-Host "DRY-RUN - omitir empalme/build/deploy" -ForegroundColor Yellow
        return @{ done = $false; simBefore = $simBefore; dryRun = $true }
    }

    Write-Step "Empalme Python (sin Cursor)"
    $empArgs = @(
        $EmpalmePy,
        "--lovable-dir", $LovableRoot,
        "--web-dir", $WebRoot,
        "--port-map", $PortMap,
        "--gap-manifest", $GapManifest,
        "--comparison", $ComparisonBefore,
        "--run-id", $RunId,
        "--out", $EmpalmeResult
    )
    python @empArgs
    if ($LASTEXITCODE -ne 0) { throw "run-gap-batch-empalme falló" }
    $emp = Get-Content $EmpalmeResult -Raw | ConvertFrom-Json
    if ([int]$emp.appliedCount -eq 0 -and [int]$emp.cursorRequiredCount -gt 0) {
        Write-Warning "Ningun gap aplicado - revisar cursorRequired/manualRequired en $EmpalmeResult"
    }

    Write-Step "Fix data stubs (build)"
    python $FixStubsPy --web-dir $WebRoot

    if (-not $NoBuild) {
        Write-Step "Build DEV (gate)"
        Push-Location $WebRoot
        try {
            npm run build:devaws
            if ($LASTEXITCODE -ne 0) { throw "build:devaws falló" }
        } finally { Pop-Location }
    }

    Write-Step "Comparar diseño (después)"
    python $ComparePy $LovableRoot $WebRoot $PortMap $ComparisonAfter
    $after = Get-Content $ComparisonAfter -Raw | ConvertFrom-Json
    $simAfter = [double]$after.overallSimilarityPercent
    Write-Host ("Similitud: {0}% -> {1}% (delta {2}%)" -f $simBefore, $simAfter, [math]::Round($simAfter - $simBefore, 2))

    python $ReportPy `
        --before $ComparisonBefore --after $ComparisonAfter `
        --manifest $GapManifest --web-dir $WebRoot `
        --out $ReportMd --run-id $RunId

    if ([int]$emp.backendRequiredCount -gt 0) {
        Write-Host "`nBACKEND: $($emp.backendRequiredCount) gap(s) requieren DoEventsBack - ver $ReportMd" -ForegroundColor Yellow
    }

    if (-not $NoPush) {
        Write-Step "Commit + push WEB ($WebBranch)"
        Push-Location $WebRoot
        try {
            git add -A
            $msg = "feat(dsf): gap-batch $RunId applied=$($emp.appliedCount) sim=${simBefore}-${simAfter}"
            git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                git commit -m $msg
                git push origin "HEAD:$WebBranch"
            } else {
                Write-Host "Sin cambios para commit"
            }
        } finally { Pop-Location }
    }

    if (-not $NoDeploy -and (Test-Path $DeployPs1)) {
        Write-Step "Deploy DEV (AWS)"
        & $DeployPs1
    } elseif (-not $NoDeploy) {
        Write-Warning "No existe $DeployPs1 - omitir deploy"
    }

    $statusPath = Join-Path $Artifacts "gap-batch-status.json"
    @{
        lastRunId = $RunId
        round = $Round
        simBefore = $simBefore
        simAfter = $simAfter
        applied = $emp.appliedCount
        totalPending = $manifest.totalPendingGaps
        remainingAfterBatch = $manifest.remainingAfterBatch
        report = $ReportMd
        at = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json | Set-Content $statusPath -Encoding UTF8

    return @{
        done = ($simAfter -ge $TargetSim) -or ([int]$manifest.remainingAfterBatch -eq 0 -and [int]$manifest.gapsInBatch -eq 0)
        simBefore = $simBefore
        simAfter = $simAfter
        pending = $manifest.totalPendingGaps
        applied = $emp.appliedCount
    }
}

# --- Main ---
Write-Host "DSF Gap Batch (Python-only) - lote $BatchSize gaps" -ForegroundColor Green
Write-Host "WEB: $WebRoot"
Write-Host "Lovable: $LovableRoot"
Write-Host "Artifacts: $Artifacts"

if (-not (Test-Path $WebRoot)) { throw "No existe WEB: $WebRoot" }
if (-not (Test-Path $LovableRoot)) { throw "No existe Lovable: $LovableRoot" }
if (-not (Test-Path $PortMap)) { throw "No existe port-map: $PortMap" }

Sync-WebBranch

$round = 0
do {
    $round++
    $result = Invoke-GapBatch -Round $round
    if ($result.dryRun) { break }
    if ($result.done) {
        Write-Host "`nObjetivo alcanzado o sin gaps pendientes." -ForegroundColor Green
        break
    }
    if (-not $UntilDone) { break }
    if ($round -ge $MaxBatches) {
        Write-Warning "MaxBatches ($MaxBatches) alcanzado - continuar manualmente con el mismo comando."
        break
    }
    Write-Host "`n--- Siguiente lote ($round/$MaxBatches) ---" -ForegroundColor Magenta
    Start-Sleep -Seconds 2
} while ($UntilDone)

Write-Host "`nEstado guardado en $Artifacts\gap-batch-status.json" -ForegroundColor Green
