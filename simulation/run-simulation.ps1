# Ejecuta simulacion completa DoEventsCICD
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== 1/3 Preparar sandbox DoEventsWEB ===" -ForegroundColor Cyan
& "$PSScriptRoot\prepare-sandbox.ps1"

Write-Host "`n=== 2/3 Instalar dependencias Python ===" -ForegroundColor Cyan
pip install -q -r "..\requirements.txt"

Write-Host "`n=== 3/3 Ejecutar bateria de pruebas ===" -ForegroundColor Cyan
python "$PSScriptRoot\run-simulation.py"
$code = $LASTEXITCODE

Write-Host "`nInforme: $PSScriptRoot\REGISTRO_PRUEBAS.md" -ForegroundColor Green
Write-Host "JSON:    $PSScriptRoot\output\last-run.json" -ForegroundColor Green
exit $code
