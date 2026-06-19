# Runbook — DSF Sync DEV

## Prerrequisitos

1. Secretos GH en environment `dev` (`GITHUB_SECRETS_DEV.md`)
2. `DoEventsWEB/ReglasAgente/reglas-front.md` ≥ 500 bytes
3. Rama `feature/cicd/dev-automation` en WEB y Back
4. `CURSOR_API_KEY` para empalme automático

## Flujo automático

```
discover-joyful-feed push main
  → trigger-cicd-sync.yml
  → DoEventsCICD: dsf-sync-dev.yml
      prepare (manifest, port-map, similitud)
      adapt (agente obligatorio si cambios o sim <98%)
      gap-loop (hasta 5 batches → 98%)
      custom-gates
      deploy-dev (S3 sa-east-1)
      smoke (API real)
      validate-and-report (bloqueante)
```

## Ejecución manual

```bash
gh workflow run dsf-sync-dev.yml \
  --repo doeventsrepo/DoEventsCICD \
  -f lovable_ref=main \
  -f run_agent=true \
  -f run_gap_loop=true \
  -f deploy_dev_after=true
```

## QA — INHABILITADO

`dsf-promote-qa.yml` falla siempre hasta `dsf.qaPromotion.enabled=true`.

No usar `deploy-web-qa.yml` en pipeline Lovable.

## Troubleshooting

| Error | Solución |
|-------|----------|
| Port-map sin cobertura | Añadir entrada en `.lovable-port-map.json` |
| Agente omitido | Verificar `requires_agent=true` y `CURSOR_API_KEY` |
| Similitud <98% | Gap-loop automático; revisar reporte en `Reports/` |
| Mocks detectados | Quitar imports mockData; usar `@doevents/shared` |
| Smoke falla | Verificar `api-dev.doeventsapp.com` y lambdas DEV |
| Build devaws falla | Revisar rama agente antes de deploy |

## Validación local

```bash
cd DoEventsCICD
pip install -r requirements.txt
./scripts/dsf validate --web-dir ../DoEventsWEB \
  --lovable-dir ../discover-joyful-feed --port-map-check
python3 scripts/lovable-sync/compare-design-similarity.py \
  ../discover-joyful-feed ../DoEventsWEB ../DoEventsWEB/.lovable-port-map.json /tmp/design.json
```

## Habilitar QA (futuro)

1. Validar 3+ syncs DEV consecutivos exitosos (sim ≥98%, smoke OK)
2. Editar `cicd.config.json`: `dsf.qaPromotion.enabled: true`
3. Editar `dsf.artifactPromotion.enabled: true`
4. Ejecutar `dsf-promote-qa.yml` con confirm `ENABLE_QA_PROMOTION`
