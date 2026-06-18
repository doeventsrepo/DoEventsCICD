# Runbook — Sync Lovable → DoEventsWEB

## Prerrequisitos

1. Repos clonados: `discover-joyful-feed`, `DoEventsWEB`, `DoEventsCICD`
2. `DoEventsWEB/ReglasAgente/reglas-front.md` ≥ 500 bytes (bootstrap: `scripts/bootstrap-web-reglas-agente.sh`)
3. Secretos configurados (ver `docs/secrets.md`)

## Flujo manual (GitHub Actions)

1. Push cambios UI/reglas a `discover-joyful-feed` rama `main`
2. En **DoEventsCICD** → Actions → **Lovable Sync to WEB** → Run workflow
   - `run_agent`: true
   - `agent_mode`: `frontend-only` (recomendado) o `fullstack`
   - `lovable_ref`: SHA o `main`
3. Job **prepare**: valida YAML, genera manifiesto, actualiza `ReglasAgente/` en WEB
4. Job **adapt**: invoca Cursor Cloud Agent → rama `feature/lovable/adapt-{sha}`
5. Revisar rama del agente en DoEventsWEB (+ DoEventsBack si fullstack)
6. Merge manual a `develop` tras revisión

## Flujo automático (opcional)

Copiar `templates/workflows/trigger-cicd-sync.yml` a `discover-joyful-feed/.github/workflows/`.

## Local (sin GHA)

```bash
cd DoEventsCICD
pip install -r requirements.txt

# Bootstrap WEB
bash scripts/bootstrap-web-reglas-agente.sh ../DoEventsWEB

# Analizar diff
python3 scripts/lovable-sync/analyze-lovable-diff.py ../discover-joyful-feed __last_sync__ HEAD ../DoEventsWEB
python3 scripts/lovable-sync/build-agent-context.py ../discover-joyful-feed ../DoEventsWEB lovable-change-manifest.json

export CICD_DIR=$(pwd)
export CURSOR_API_KEY=...
export LOVABLE_DIR=../discover-joyful-feed
export WEB_DIR=../DoEventsWEB
python3 scripts/lovable-sync/run-port-agent-api.py
```

## Troubleshooting

| Error | Solución |
|-------|----------|
| Gate ReglasAgente bloqueado | Ejecutar bootstrap; completar `reglas-front.md` |
| Cursor API 401 | Rotar `CURSOR_API_KEY` |
| Push WEB falla | Verificar `DOEVENTS_WEB_PAT` |
| Mocks detectados | Revisar `validate-no-mocks.sh` output |
