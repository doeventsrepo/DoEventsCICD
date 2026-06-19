# Reports — Lovable → DoEventsWEB → DEV

Informes de sincronización entre **discover-joyful-feed** (Lovable) y **DoEventsWEB**, con detalle de cambios y despliegues en **DEV** (sa-east-1).

## Política de ramas (DoEventsWEB)

| Rama | Pipeline CICD | Merge |
|------|---------------|-------|
| `feature/cicd/dev-automation` | Base DEV — **única rama que modifica el pipeline** | Manual por ingeniero |
| `feature/lovable/adapt-*` | Salida del agente Cursor (cuando `run_agent=true`) | Manual → PR |
| **`develop`** | **NUNCA tocada por CICD** | Procesos QA manuales del equipo |
| `main` / `release` | Prohibidas en automatización | Manual |

El merge de `feature/*` → `develop` lo hace **solo el ingeniero** cuando valida en DEV y decide integrar a QA.

## Índice de reportes

| Fecha | Archivo | Run CICD | Resultado |
|-------|---------|----------|-----------|
| 2026-06-19 | [2026-06-19-lovable-sync-dev.md](./2026-06-19-lovable-sync-dev.md) | [27824147397](https://github.com/doeventsrepo/DoEventsCICD/actions/runs/27824147397) | OK |

## Generar un reporte nuevo

```powershell
cd DoEventsCICD
.\scripts\generate-lovable-dev-report.ps1 -RunId 27824147397
```

Requiere `gh auth` y permisos lectura en repos `DoEventsCICD`, `DoEventsWEB`, `discover-joyful-feed`.

## Contenido esperado de cada reporte

1. Origen Lovable (SHA, reglas YAML, UI)
2. **Comparación diseño** — `% similitud` Lovable vs WEB (pre y post agente)
3. Ejecuciones GitHub Actions (prepare / adapt / deploy-dev)
4. Commits en **rama feature** (nunca `develop`)
5. Archivos modificados en DoEventsWEB
6. Despliegue DEV (S3, CloudFront, URL)
7. Pendientes (agente, merge a develop)

## Reportes de comparación de diseño

Generados automáticamente por el workflow `Lovable Sync to WEB (DEV)`:

| Patrón | Cuándo |
|--------|--------|
| `*-design-comparison-pre-{runId}.md` | Tras `prepare` (antes del agente) |
| `*-design-comparison-post-{runId}.md` | Tras `adapt` (después del empalme) |

Métrica clave: **`overallSimilarityPercent`** (objetivo ≥98%). También disponible como artefacto CI (`design-comparison-pre/post-{runId}`) y en `design-comparison.json`.
