# DOEVENTS DSF v1.0 — Governance

Marco organizacional del Design Synchronization Framework. Complementa el Prompt Maestro Lovable y las políticas YAML.

## Roles (RACI)

| Rol | Responsabilidad |
|-----|-----------------|
| **Product** | Intención funcional, feature flags, aprobación breaking changes |
| **Lovable / Design** | UI/UX, reglas en discover-joyful-feed, component-index |
| **DoEventsWEB** | Implementación frontend, lovable-bridge, @doevents/shared |
| **DoEventsBack** | Contratos en contratosBackend/endpoints.yml, APIs reales |
| **DSF / CI** | Pipeline agentes, bloqueos, DSF Score, deploy DEV |

## Fuentes de verdad

| Artefacto | Repo | Consumidor |
|-----------|------|------------|
| Prompt Maestro | DoEventsCICD/docs | Lovable (comportamiento) |
| reglasActuacion + empalme | discover-joyful-feed | Python empalme |
| component-index + port-map | discover-joyful-feed | sync-readiness-gate |
| reglasCalidad | discover-joyful-feed | quality-gate, empalme_engine |
| reglasRelease | discover-joyful-feed | release-guard |
| contratosBackend | discover-joyful-feed | backend-contract-check |
| .lovable-port-map.json | DoEventsWEB | port-map-resolver |

## Pipeline v1.0 (17 pasos)

0–14 agentes Python/Cursor → 12 deploy DEV → 13 smoke → 14 report + DSF Score

**Sin gap-loops.** Cursor: max 5 archivos, 1 escalado, 0 retries.

## DSF Score (por run)

| Métrica | Meta enterprise |
|---------|-----------------|
| syncEffectiveness | ≥ 95% |
| pythonCoverage | ≥ 90% cambios cosméticos |
| blockedCorrectly | 100% bloqueos justificados |
| cursorEscalations | ≤ 1 por run |
| similarityDelta | documentado |

## Criterios deploy DEV

- quality-gate OK
- backend-contract-check OK
- release-guard OK
- riskLevel ≠ blocked
- sync-readiness-gate OK

## Escalación humana obligatoria

auth, pagos, KYC, geolocalización, websocket, package.json, breaking change, feature flag nuevo

## Bootstrap índice

```bash
python DoEventsCICD/scripts/lovable-sync/bootstrap-dsf-index.py \
  --lovable-dir discover-joyful-feed --web-dir DoEventsWEB
```

Ejecutar tras crear componentes nuevos en src/ o actualizar .lovable-port-map.json en WEB.

## Mejoras futuras

Van a YAML (`reglasCalidad/`, `reglasRelease/`, `reglasObservabilidad/`), **no al prompt Lovable**.
