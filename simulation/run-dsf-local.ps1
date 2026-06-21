# Pipeline DSF local — sin GitHub Actions ni deploy DEV remoto (por defecto)
# Uso desde monorepo:
#   cd C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation
#   .\run-dsf-local.ps1              # ciclo completo
#   .\run-dsf-local.ps1 -Phase prepare
#   .\run-dsf-local.ps1 -Phase gap
param(
    [ValidateSet("init", "prepare", "empalme", "gap", "agent-dry", "build", "gates", "smoke", "validate", "report", "all")]
    [string]$Phase = "all",
    [switch]$LiveAgent  # IGNORADO — local bloquea GitHub
    [switch]$Deploy,
    [switch]$RemoteSmoke
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (Test-Path ".\local.env") {
    Get-Content ".\local.env" | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim()
            if (-not [string]::IsNullOrEmpty($k) -and -not $env:$k) { Set-Item -Path "env:$k" -Value $v }
        }
    }
}

pip install -q -r "..\requirements.txt" 2>$null

$argsList = @("run-dsf-local.py", $Phase)
if ($LiveAgent) {
    Write-Warning "LiveAgent ignorado: modo local no contacta GitHub ni Cursor API."
}
if ($Deploy) { $argsList += "--deploy" }
if ($RemoteSmoke) { $argsList += "--remote-smoke" }

python @argsList
exit $LASTEXITCODE
