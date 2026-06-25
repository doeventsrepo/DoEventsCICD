# Validacion local pipeline multiagente DSF + BSF
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python run-multiagent-validation.py @args
exit $LASTEXITCODE
