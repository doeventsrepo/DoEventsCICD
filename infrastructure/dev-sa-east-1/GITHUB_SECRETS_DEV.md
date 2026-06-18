# Secretos GitHub — pipeline DEV (sa-east-1)

Configurar en **doeventsrepo/DoEventsCICD** → Settings → Environments → **dev**.

## Secretos obligatorios (environment `dev`)

| Secreto | Descripción |
|---------|-------------|
| `AWS_ACCESS_KEY_ID_DEV` | IAM S3 `doevents-web-dev`, CloudFront, sa-east-1 |
| `AWS_SECRET_ACCESS_KEY_DEV` | Par del anterior |
| `CLOUDFRONT_DISTRIBUTION_ID_DEV` | `E1AIDTCT83PAW5` |
| `DOEVENTS_WEB_PAT` | PAT push a ramas **`feature/*`** en DoEventsWEB (NO develop/main) |
| `CURSOR_API_KEY` | Cursor Cloud Agents API |
| `VITE_GOOGLE_MAPS_API_KEY` | Build `devaws` |

Opcional: `S3_BUCKET_DEV` = `doevents-web-dev`

## Repo discover-joyful-feed (trigger automatico)

| Secreto | Descripción |
|---------|-------------|
| `DOEVENTS_CICD_PAT` | PAT con `workflow` scope en DoEventsCICD |

Copiar workflow: `templates/workflows/trigger-cicd-sync.yml` → `.github/workflows/`

## Workflow Lovable Sync to WEB (DEV)

Defaults correctos (NO tocar QA):

| Input | Valor |
|-------|-------|
| `run_agent` | `true` |
| `agent_mode` | `frontend-only` |
| `deploy_dev_after` | `true` |
| `web_cicd_branch` | `feature/cicd/dev-automation` |

**No existe** `deploy_qa_after` en el pipeline automatico.

## QA (manual, fuera del pipeline)

Secretos en environment `qa` solo para workflows manuales con confirmacion `DEPLOY_QA_MANUAL`:

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `CLOUDFRONT_DISTRIBUTION_ID`

## Ramas protegidas

La automatizacion **rechaza** push/deploy desde: `main`, `develop`, `release`, `release/*`.

Solo permite prefijo `feature/`.
