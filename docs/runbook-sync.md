# Runbook — Sync Lovable → DoEventsWEB → DEV

Pipeline **DEV-only** (sa-east-1). QA deshabilitado en automatizacion.

## Arquitectura

```text
discover-joyful-feed (main)
  → DoEventsCICD: Lovable Sync to WEB (DEV)
    → prepare (validar reglas, manifiesto, ReglasAgente)
    → adapt (Cursor Agent — empalme en feature/lovable/adapt-{sha})
    → deploy-dev (S3 doevents-web-dev → dev.doeventsapp.com)
```

## Ramas

| Repo | Rama automatizacion | Prohibidas |
|------|---------------------|------------|
| DoEventsWEB | `feature/cicd/dev-automation` (base) + `feature/lovable/adapt-*` (agente) | main, develop, release/* |
| DoEventsBack | `feature/cicd/dev-automation` (solo fullstack) | main, develop, release/* |
| DoEventsCICD | `main` (workflows) | — |
| discover-joyful-feed | `main` (dispara sync) | — |

## Prerrequisitos

1. Secretos en **DoEventsCICD** → environment `dev` (ver `infrastructure/dev-sa-east-1/GITHUB_SECRETS_DEV.md`)
2. `DoEventsWEB/ReglasAgente/reglas-front.md` ≥ 500 bytes
3. Ramas `feature/cicd/dev-automation` existentes en WEB y Back

## Flujo automatico (GitHub Actions)

1. Push UI/reglas a `discover-joyful-feed` main (o workflow `Trigger DoEventsCICD Sync`)
2. **DoEventsCICD** → Actions → **Lovable Sync to WEB (DEV)**
   - `run_agent`: true
   - `deploy_dev_after`: true (default)
   - `web_cicd_branch`: `feature/cicd/dev-automation`
3. **guard**: valida rama feature/*
4. **prepare**: YAML, manifiesto, commit docs en rama feature
5. **adapt**: Cursor Agent → `feature/lovable/adapt-{sha}` (empalme, anti-mocks, build:devaws)
6. **deploy-dev**: S3 + CloudFront sa-east-1

## Agente Cursor — empalme (NO copy-paste)

El agente debe:

- Leer `ReglasAgente/reglas-front.md` y `REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md`
- Integrar cambios en componentes existentes y `lovable-bridge/*`
- Mantener `@doevents/shared` y APIs `api-dev.doeventsapp.com`
- **No** usar mockData de Lovable en runtime
- Documentar brechas backend en `impacto-backend.md`
- Validar con `npm run build:devaws`

## QA (solo manual)

Workflows QA requieren escribir `DEPLOY_QA_MANUAL`:

- `Deploy WEB QA (manual)`
- `Deploy Backend QA (manual)`
- `Deploy IA QA (manual)`

No forman parte del pipeline Lovable.

## Local (dry-run)

```bash
cd DoEventsCICD
pip install -r requirements.txt
export CICD_DIR=$(pwd)
export LOVABLE_DIR=../discover-joyful-feed
export WEB_DIR=../DoEventsWEB
python3 simulation/scripts/simulate-agent-dry-run.py
```

## Troubleshooting

| Error | Solución |
|-------|----------|
| Rama prohibida | Usar solo `feature/*` |
| Gate ReglasAgente | Bootstrap `templates/ReglasAgente/` |
| Cursor API 401 | Rotar `CURSOR_API_KEY` |
| Mocks detectados | Revisar salida `validate-no-mocks.sh` |
| Build devaws falla | Revisar rama agente antes de deploy |
