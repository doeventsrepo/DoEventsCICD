# Reports — DSF Sync DEV

Informes generados por **DSF Sync DEV** (`dsf-sync-dev.yml`).

## Patrones de archivo

| Patrón | Contenido |
|--------|-----------|
| `*-dsf-sync-{runId}.md` | Reporte consolidado (estado, similitud, smoke, errores) |
| `*-dsf-sync-{runId}.json` | Mismo reporte en JSON (historial/dashboard) |
| `*-design-pre-{runId}.md` | Comparación diseño pre-agente |
| `*-gap-empalme-{runId}.md` | Reporte batch gap-empalme |

## Métricas clave

- **overallSimilarityPercent** — objetivo ≥ **98%** (gate bloqueante)
- **smoke** — API DEV real, sin mocks
- **qaPromotionEnabled** — siempre `false` hasta habilitar en `cicd.config.json`

## QA

Promoción QA **inhabilitada**. Los reportes indican `QA promoción: INHABILITADA`.

## Artefactos CI

Descargar desde GitHub Actions → `dsf-report-{runId}`
