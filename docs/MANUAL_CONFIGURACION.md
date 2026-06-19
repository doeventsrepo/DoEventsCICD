# Manual de configuración — DoEventsCICD

Guía paso a paso para operadores y desarrolladores que configuran el pipeline DEV.

**Relacionados:** [Arquitectura](./ARQUITECTURA.md) · [Setup GitHub](./SETUP_GITHUB_CICD.md) · [Diagramas](./DIAGRAMAS_SECUENCIA_ESPECIFICACION.md)

---

## 1. Prerrequisitos

| Requisito | Detalle |
|-----------|---------|
| Cuenta GitHub | Organización `doeventsrepo` con acceso admin a repos |
| GitHub CLI | `gh` instalado y autenticado |
| AWS CLI | Perfil con acceso DEV sa-east-1 (operadores infra) |
| Node.js 20 | Para builds locales de verificación |
| Python 3.11+ | Scripts `scripts/lovable-sync/` |

---

## 2. Autenticación GitHub CLI

```powershell
gh auth login
# o con PAT (scopes: repo, workflow, read:org)
$env:GH_TOKEN = "ghp_..."
gh auth status
```

Cuenta esperada: **`doeventsrepo`**.

---

## 3. Secretos GitHub

### 3.1 Script automático (recomendado)

```powershell
cd DoEventsCICD
$env:DOEVENTS_WEB_PAT = $env:GH_TOKEN   # PAT con scope repo
$env:CURSOR_API_KEY = "key_..."         # opcional hasta activar agente
.\scripts\setup-github-secrets-dev.ps1 -EnvConfig envDevelop
```

El script (desde monorepo con `envConfig/envDevelop`):

- Crea environment **`dev`** en `DoEventsCICD`
- Lee bucket/CloudFront desde `envConfig/envDevelop/environment.json` si existe
- Toma AWS de `infrastructure/dev-sa-east-1/cicd-github-dev-credentials.json` o variables de entorno

### 3.2 Tabla de secretos

| Secreto | Scope | Obligatorio | Descripción |
|---------|-------|-------------|-------------|
| `DOEVENTS_WEB_PAT` | Repo CICD | Sí | Push a ramas `feature/*` en DoEventsWEB |
| `CURSOR_API_KEY` | Repo CICD | Solo con agente | Cursor Cloud Agents API |
| `AWS_ACCESS_KEY_ID_DEV` | Env `dev` | Sí (deploy) | IAM `cicd-github-dev` |
| `AWS_SECRET_ACCESS_KEY_DEV` | Env `dev` | Sí (deploy) | Par del access key |
| `CLOUDFRONT_DISTRIBUTION_ID_DEV` | Env `dev` | Sí | `E1AIDTCT83PAW5` |
| `VITE_GOOGLE_MAPS_API_KEY` | Env `dev` | Sí (build) | Mismo que `.env.devaws` |
| `S3_BUCKET_DEV` | Env `dev` | Opcional | Default `doevents-web-dev` |
| `DOEVENTS_CICD_PAT` | Repo discover-joyful-feed | Trigger auto | PAT con scope `workflow` |

### 3.3 Verificar secretos

```powershell
gh secret list --repo doeventsrepo/DoEventsCICD
gh secret list --repo doeventsrepo/DoEventsCICD --env dev
```

---

## 4. Configuración de archivos

### 4.1 `cicd.config.json`

Parámetros clave:

```json
{
  "branches": {
    "cicdWeb": "feature/cicd/dev-automation",
    "protected": ["main", "develop", "release", "release/*"]
  },
  "awsDev": {
    "region": "sa-east-1",
    "web": { "domain": "dev.doeventsapp.com", "bucket": "doevents-web-dev" }
  },
  "pipeline": {
    "targetEnvironment": "dev",
    "forbidAutomaticQaDeploy": true
  }
}
```

### 4.2 `Reglas/reglas.config.json`

Define rutas de reglamento, prompts y plantillas bootstrap. No contiene secretos.

Validar:

```powershell
python scripts/lovable-sync/validate-reglas-cicd.py .
```

### 4.3 `envConfig/` (monorepo raíz)

| Carpeta | Entorno |
|---------|---------|
| `envDevelop` | DEV sa-east-1 |
| `envRelease` | QA us-east-2 (manual) |
| `envMain` | PROD (manual) |

Uso en scripts PowerShell:

```powershell
. ..\envConfig\load-env-config.ps1
$dev = Get-EnvConfig envDevelop
$dev.web.bucket
```

---

## 5. Bootstrap DoEventsWEB

Inicializa `ReglasAgente/` desde plantillas CICD:

```bash
bash scripts/bootstrap-web-reglas-agente.sh ../DoEventsWEB
```

Copia desde `Reglas/artefactos-web/`:

- `reglas-front.md` (gate ≥ 500 bytes)
- `cambios-lovable.json`
- `decision-log.md`
- `impacto-backend.md`

---

## 6. Ramas requeridas en GitHub

| Repo | Rama | Propósito |
|------|------|-----------|
| DoEventsWEB | `feature/cicd/dev-automation` | Base del pipeline (NO `develop`) |
| DoEventsBack | `feature/cicd/dev-automation` | Fullstack agent (opcional) |
| DoEventsCICD | `main` | Workflows activos |
| discover-joyful-feed | `main` | Diseño + trigger |

Crear ramas si no existen:

```powershell
.\scripts\create-cicd-branches.ps1
```

---

## 7. Ejecución del pipeline

### 7.1 Deploy DEV sin agente (prueba rápida)

```powershell
gh workflow run "Lovable Sync to WEB (DEV)" `
  --repo doeventsrepo/DoEventsCICD `
  -f run_agent=false `
  -f deploy_dev_after=true `
  -f web_cicd_branch=feature/cicd/dev-automation
```

### 7.2 Solo deploy (workflow hijo)

```powershell
gh workflow run deploy-web-dev.yml `
  --repo doeventsrepo/DoEventsCICD `
  -f web_ref=feature/cicd/dev-automation
```

### 7.3 Pipeline completo con agente

```powershell
gh workflow run "Lovable Sync to WEB (DEV)" `
  --repo doeventsrepo/DoEventsCICD `
  -f run_agent=true `
  -f agent_mode=frontend-only `
  -f deploy_dev_after=true
```

### 7.4 Monitoreo

```powershell
gh run list --repo doeventsrepo/DoEventsCICD --limit 5
gh run watch --repo doeventsrepo/DoEventsCICD
gh run view <RUN_ID> --repo doeventsrepo/DoEventsCICD --log-failed
```

Verificación HTTP:

```powershell
curl -I https://dev.doeventsapp.com
```

---

## 8. Trigger automático desde Lovable

1. Secret `DOEVENTS_CICD_PAT` en **discover-joyful-feed**
2. Workflow `trigger-cicd-sync.yml` en `main`
3. Push a `src/` o `reglasActuacion/` dispara `repository_dispatch` → DoEventsCICD

---

## 9. IAM AWS DEV (CI/CD)

Usuario IAM: **`cicd-github-dev`**

Permisos mínimos:

- `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket` → `doevents-web-dev`
- `cloudfront:CreateInvalidation` → distribución `E1AIDTCT83PAW5`

Crear/rotar:

```powershell
.\infrastructure\dev-sa-east-1\create-cicd-github-dev-iam.ps1
```

Credenciales locales (gitignored): `infrastructure/dev-sa-east-1/cicd-github-dev-credentials.json`

---

## 10. Troubleshooting

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| `workflow_dispatch` HTTP 422 | Error YAML en workflow | Revisar `deploy-web-dev.yml`, push fix |
| Gate ReglasAgente falla | `reglas-front.md` < 500 bytes | Bootstrap desde `Reglas/artefactos-web/` |
| Build falla Maps | Falta `VITE_GOOGLE_MAPS_API_KEY` | Secret env `dev` |
| S3 AccessDenied | IAM o secret incorrecto | Rotar credenciales `cicd-github-dev` |
| Rama prohibida | Input apunta a `develop` | Usar `feature/cicd/dev-automation` |
| Agente bloqueado | Sin `CURSOR_API_KEY` | Configurar secret o `run_agent=false` |

---

## 11. Checklist operativo

- [ ] `gh auth status` → cuenta `doeventsrepo`
- [ ] Secretos repo + environment `dev` configurados
- [ ] Rama `feature/cicd/dev-automation` existe en DoEventsWEB
- [ ] `Reglas/` validado (`validate-reglas-cicd.py`)
- [ ] `DoEventsWEB/ReglasAgente/reglas-front.md` presente
- [ ] Prueba deploy DEV exitosa → https://dev.doeventsapp.com
- [ ] (Opcional) `CURSOR_API_KEY` + prueba con agente
- [ ] (Opcional) Trigger en discover-joyful-feed
