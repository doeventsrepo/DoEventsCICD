# Carga GH_TOKEN desde Git Credential Manager (Windows).
# Uso manual: . .\scripts\gh-with-git-auth.ps1
function Sync-GhAuthFromGit {
    # GH_TOKEN invalido en el perfil provoca reintentos y rate limit secundario.
    if ($env:GH_TOKEN) {
        $check = gh auth status 2>&1
        if ($LASTEXITCODE -eq 0) { return $true }
        Remove-Item Env:GH_TOKEN -ErrorAction SilentlyContinue
    }
    try {
        $credRaw = (echo "protocol=https`nhost=github.com`n" | git credential fill 2>$null) -join "`n"
        if ($credRaw -match "password=(.+)") {
            $env:GH_TOKEN = $Matches[1].Trim()
            return $true
        }
    } catch { }
    return $false
}

if (Sync-GhAuthFromGit) {
    gh auth status
} else {
    Write-Error "Sin credenciales Git para github.com. Ejecuta: gh auth login"
}
