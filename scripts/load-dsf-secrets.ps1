# Carga secretos DSF/BSF desde las mismas fuentes que el resto del pipeline.
# No duplica CURSOR_API_KEY — usa simulation/local.env o variables de entorno existentes.

function Import-DsfSecrets {
    param(
        [string]$CicdRoot = ""
    )

    if (-not $CicdRoot) {
        $CicdRoot = Split-Path -Parent $PSScriptRoot
    }

    $loaded = @()

    function Import-EnvFile([string]$Path) {
        if (-not (Test-Path $Path)) { return }
        Get-Content $Path -Encoding UTF8 | ForEach-Object {
            if ($_ -match '^\s*([^#=]+)=(.*)$') {
                $k = $matches[1].Trim()
                $v = $matches[2].Trim().Trim('"').Trim("'")
                if ($k -and $v -and [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($k))) {
                    Set-Item -Path "env:$k" -Value $v
                    if ($k -eq 'CURSOR_API_KEY') { $script:loaded += $Path }
                }
            }
        }
    }

    # 1 — Ya en sesión
    if ($env:CURSOR_API_KEY) {
        return @{ ok = $true; source = 'session'; path = $null }
    }

    # 2 — simulation/local.env (mismo que run-dsf-local.ps1)
    Import-EnvFile (Join-Path $CicdRoot "simulation\local.env")

    # 3 — ConfiguracionEntorno/.local/dsf-secrets.env (opcional, gitignored)
    $monoRoot = Split-Path $CicdRoot -Parent
    Import-EnvFile (Join-Path $monoRoot "ConfiguracionEntorno\.local\dsf-secrets.env")

    # 4 — Variables persistentes Windows
    if (-not $env:CURSOR_API_KEY) {
        $userKey = [Environment]::GetEnvironmentVariable('CURSOR_API_KEY', 'User')
        if ($userKey) { $env:CURSOR_API_KEY = $userKey; $loaded += 'User' }
    }
    if (-not $env:CURSOR_API_KEY) {
        $machineKey = [Environment]::GetEnvironmentVariable('CURSOR_API_KEY', 'Machine')
        if ($machineKey) { $env:CURSOR_API_KEY = $machineKey; $loaded += 'Machine' }
    }

    if ($env:CURSOR_API_KEY) {
        return @{ ok = $true; source = ($loaded -join ', '); path = $loaded[0] }
    }

    return @{
        ok = $false
        source = $null
        hint = @(
            "Configura la misma CURSOR_API_KEY que usa DSF (GitHub secret CURSOR_API_KEY):"
            "  1. Edita DoEventsCICD/simulation/local.env  ->  CURSOR_API_KEY=key_..."
            "  2. O en PowerShell:  `$env:CURSOR_API_KEY = 'key_...'"
            "  3. En CI: secrets.CURSOR_API_KEY (ya configurado en doeventsrepo/DoEventsCICD)"
        ) -join "`n"
    }
}
