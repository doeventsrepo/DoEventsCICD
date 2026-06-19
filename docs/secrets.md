# Secretos GitHub — DoEventsCICD

| Secreto | Repositorio | Uso |
|---------|-------------|-----|
| `CURSOR_API_KEY` | DoEventsCICD | Cursor Cloud Agents API (`/v1/agents`) |
| `DOEVENTS_WEB_PAT` | DoEventsCICD | Push a `doeventsrepo/DoEventsWEB` ramas **`feature/*` únicamente** (NUNCA `develop`) |
| `DOEVENTS_CICD_PAT` | discover-joyful-feed | Disparar workflows en DoEventsCICD |
| `AWS_ACCESS_KEY_ID` | DoEventsCICD | Deploy QA S3/Serverless |
| `AWS_SECRET_ACCESS_KEY` | DoEventsCICD | Deploy QA |
| `CLOUDFRONT_DISTRIBUTION_ID` | DoEventsCICD | Invalidación CF (`E3UV9NHXADGSAJ` QA) |

## Prohibido versionar

- `.env` con claves reales
- PATs en URLs de `git remote`
- `CURSOR_API_KEY` en logs de Actions

## AWS (alternativa a secrets GHA)

- **Secrets Manager:** `/doevents/cursor/api-key`
- **SSM:** parámetros por entorno QA

## Permisos PAT `DOEVENTS_WEB_PAT`

- `contents: write` en DoEventsWEB
- `pull_requests: write` (si `AGENT_AUTO_PR=true`)

## Environment `qa` en GitHub

Proteger workflows `deploy-*-qa.yml` con revisores opcionales antes de deploy.
