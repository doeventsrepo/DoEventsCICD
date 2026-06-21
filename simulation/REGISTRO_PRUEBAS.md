# Registro de pruebas — Simulación DoEventsCICD

**Ejecución:** 2026-06-21 10:10:58 UTC
**Sandbox WEB:** `C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation\sandbox\DoEventsWEB` (copia aislada, no productivo)
**DoEventsWEB productivo:** no modificado

## Resumen

| Métrica | Valor |
|---------|-------|
| Fixtures probados | 6 |
| Tests PASS | 45 |
| Tests FAIL | 0 |
| Tests SKIP | 15 |
| **Veredicto** | **LISTO PARA IMPLANTAR (simulacion local)** |

## Resultado por fuente Lovable

### [OK] discover-joyful-feed — Repo diseño conectado a Lovable (produccion futura)

- Ruta: `C:\DoEvents\AplicacionWEB\discover-joyful-feed`
- `src/`: True | reglas YAML: 25

| Test | Estado |
|------|--------|
| validate_rules | PASS |
| validate_design_rules | PASS |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

### [OK] lovable-v17 — Lovable version_17_06_2026/extracted

- Ruta: `C:\DoEvents\AplicacionWEB\Lovable\version_17_06_2026\extracted`
- `src/`: True | reglas YAML: 4

| Test | Estado |
|------|--------|
| validate_rules | PASS |
| validate_design_rules | SKIP |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

### [OK] lovable-v16 — Lovable version_16_06_2026/extracted

- Ruta: `C:\DoEvents\AplicacionWEB\Lovable\version_16_06_2026\extracted`
- `src/`: True | reglas YAML: 0

| Test | Estado |
|------|--------|
| validate_rules | SKIP |
| validate_design_rules | SKIP |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

### [OK] lovable-v15 — Lovable version_15_06_2026/extracted

- Ruta: `C:\DoEvents\AplicacionWEB\Lovable\version_15_06_2026\extracted`
- `src/`: True | reglas YAML: 0

| Test | Estado |
|------|--------|
| validate_rules | SKIP |
| validate_design_rules | SKIP |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

### [OK] lovable-v13 — Lovable version_13_06_2026/extracted

- Ruta: `C:\DoEvents\AplicacionWEB\Lovable\version_13_06_2026\extracted`
- `src/`: True | reglas YAML: 0

| Test | Estado |
|------|--------|
| validate_rules | SKIP |
| validate_design_rules | SKIP |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

### [OK] lovable-root-extracted — Lovable/extracted (raiz)

- Ruta: `C:\DoEvents\AplicacionWEB\Lovable\extracted`
- `src/`: True | reglas YAML: 0

| Test | Estado |
|------|--------|
| validate_rules | SKIP |
| validate_design_rules | SKIP |
| orchestrator_pre_adapt | PASS |
| validate_agent_gate | PASS |
| analyze_lovable_diff | PASS |
| build_agent_context | PASS |
| generate_agent_artifacts | PASS |
| validate_no_mocks | PASS |
| agent_dry_run | PASS |
| agent_live_api | SKIP |

## Criterios de implantación

- [x] Pipeline local sin FAIL (45 PASS / 0 FAIL)
- [x] discover-joyful-feed OK
- [x] lovable-v17 OK
- [x] Sandbox WEB aislado (no se modificó DoEventsWEB productivo)
- [ ] Revisión humana de `output/discover-joyful-feed/agent-sync-context.md`
- [ ] `npm run build:qa` en sandbox (prueba manual opcional)
- [ ] `agent_live_api` con CURSOR_API_KEY (prueba en rama de prueba)

## Notas

Fuentes sin reglasActuacion (v13-v16) tienen SKIP esperado en validate_rules. discover-joyful-feed (25 reglas) y v17 (4 reglas) son candidatos para producción. Corrección aplicada: catch-up valida que el SHA de sync exista en repo Lovable antes del diff.

*Generado automáticamente por `simulation/run-simulation.py`*