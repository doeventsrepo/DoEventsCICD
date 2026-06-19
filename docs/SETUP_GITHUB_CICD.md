# Activar pipeline CI/CD en GitHub (15 min)

Repo: [doeventsrepo/DoEventsCICD](https://github.com/doeventsrepo/DoEventsCICD)

---

## Paso 1 — Autenticarte en GitHub CLI (una vez)

En terminal:

```powershell
gh auth login
```

- Cuenta: `arodriguez@doeventsapp.com` (o la que administre `doeventsrepo`)
- Scopes: `repo`, `workflow`, `admin:org` (para secretos)

O pega un PAT:

```powershell
$env:GH_TOKEN = "ghp_..."
```

---

## Paso 2 — Crear secretos automáticamente

Desde la raíz del monorepo:

```powershell
cd DoEventsCICD
.\scripts\setup-github-secrets-dev.ps1
```

El script:
- Crea el environment **`dev`**
- Toma `VITE_GOOGLE_MAPS_API_KEY` de `DoEventsWEB/.env.devaws`
- Toma AWS de `$env:AWS_*_DEV` o `~/.aws/credentials` [default]
- Pide completar manualmente lo que falte (`DOEVENTS_WEB_PAT`, `CURSOR_API_KEY`)

### Secretos que debes tener listos

| Secreto | Dónde | Cómo obtenerlo |
|---------|-------|----------------|
| `DOEVENTS_WEB_PAT` | Repo CICD | GitHub → Settings → PAT classic → scopes **`repo`** |
| `CURSOR_API_KEY` | Repo CICD | [Cursor Dashboard](https://cursor.com) → API Keys |
| `AWS_ACCESS_KEY_ID_DEV` | Environment **dev** | IAM user con S3 `doevents-web-dev` + CloudFront invalidation sa-east-1 |
| `AWS_SECRET_ACCESS_KEY_DEV` | Environment **dev** | Par del access key |
| `CLOUDFRONT_DISTRIBUTION_ID_DEV` | Environment **dev** | `E1AIDTCT83PAW5` (ya conocido) |
| `VITE_GOOGLE_MAPS_API_KEY` | Environment **dev** | Mismo que en `.env.devaws` |
| `DOEVENTS_CICD_PAT` | Repo **discover-joyful-feed** | PAT con scope **`workflow`** |

Si faltan variables antes del script:

```powershell
$env:DOEVENTS_WEB_PAT = "ghp_..."
$env:CURSOR_API_KEY = "key_..."
.\scripts\setup-github-secrets-dev.ps1
```

---

## Paso 3 — Probar deploy DEV (sin agente Cursor)

```powershell
gh workflow run "lovable-sync-to-web.yml" `
  --repo doeventsrepo/DoEventsCICD `
  -f run_agent=false `
  -f deploy_dev_after=true `
  -f web_cicd_branch=feature/cicd/dev-automation
```

Ver progreso:

```powershell
gh run list --repo doeventsrepo/DoEventsCICD --limit 3
gh run watch --repo doeventsrepo/DoEventsCICD
```

Éxito = https://dev.doeventsapp.com actualizado desde `feature/cicd/dev-automation`.

---

## Paso 4 — Trigger automático desde Lovable

Ya está el archivo `discover-joyful-feed/.github/workflows/trigger-cicd-sync.yml` (local).

1. En **discover-joyful-feed** → Settings → Secrets → `DOEVENTS_CICD_PAT`
2. Push a `main` del workflow
3. Cada push a `src/` o `reglasActuacion/` dispara el pipeline DEV

---

## Paso 5 — Pipeline completo con agente Cursor

Cuando `CURSOR_API_KEY` y `DOEVENTS_WEB_PAT` estén OK:

```powershell
gh workflow run "lovable-sync-to-web.yml" `
  --repo doeventsrepo/DoEventsCICD `
  -f run_agent=true `
  -f agent_mode=frontend-only `
  -f deploy_dev_after=true
```

---

## Troubleshooting

| Error | Solución |
|-------|----------|
| Rama prohibida | Solo `feature/*` en WEB |
| 401 Cursor | Rotar `CURSOR_API_KEY` |
| S3 Access Denied | IAM user necesita `s3:*` en `doevents-web-dev` + `cloudfront:CreateInvalidation` |
| Checkout WEB falla | `DOEVENTS_WEB_PAT` debe poder leer/escribir `DoEventsWEB` ramas feature |

Más detalle: `docs/runbook-sync.md` y `infrastructure/dev-sa-east-1/GITHUB_SECRETS_DEV.md`
