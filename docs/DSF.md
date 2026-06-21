# Design Sync Framework (DSF) v3

Framework reutilizable para sincronizar **Lovable → DoEventsWEB** sin copy-paste, sin mocks en runtime, con gates bloqueantes y trazabilidad completa.

## Principio

```
Lovable DISEÑA → DSF DETECTA → Agente EMPALMA → Gates VALIDAN → Cloud DESPLIEGA → Reporte CERTIFICA
```

## Estado QA

**Promoción QA INHABILITADA** (`dsf.qaPromotion.enabled: false` en `cicd.config.json`).

Hasta validar el ciclo DEV completo (similitud ≥98%, smoke OK, sin mocks).

## Arquitectura

| Capa | Componente |
|------|------------|
| 0 Contrato | `.lovable-port-map.json`, `reglasActuacion/`, `ReglasAgente/` |
| 1 Detección | `analyze-lovable-diff.py`, `compare-design-similarity.py` |
| 2 Empalme | Cursor Agent API, `lovable-bridge/`, gap-loop |
| 3 Gates | G0 port-map, G1 build, G3 anti-mocks, G6 smoke, custom rules |
| 4 Deploy | AWS provider (DEV), Azure stub |
| 5 Reporte | `Reports/*-dsf-sync-*.md` + JSON |

## Gates bloqueantes

| Gate | Script | Falla si |
|------|--------|----------|
| G0 | `validate-port-map-coverage.py` | Archivo Lovable sin mapeo |
| G1 | `npm run build:devaws` | Build falla |
| G3 | `validate-no-mocks.sh` | Mocks en runtime |
| G6 | `scripts/smoke/dev-smoke.sh` | API DEV no responde |
| Custom | `run-custom-gates.py` | Regla `gate: block` en `Reglas/custom/` |
| Final | `validate-pipeline-sync.py` | Similitud <98%, agente omitido, deploy/smoke fallido |

## Workflow principal

**`.github/workflows/dsf-sync-dev.yml`**

Jobs: `guard` → `prepare` → `adapt` → `gap-loop` → `custom-gates` → `deploy-dev` → `smoke` → `validate-and-report`

Trigger desde Lovable:
```bash
gh workflow run dsf-sync-dev.yml --repo doeventsrepo/DoEventsCICD -f lovable_ref=main
```

## CLI local

```bash
cd DoEventsCICD
./scripts/dsf config
./scripts/dsf validate --web-dir ../DoEventsWEB --port-map-check
./scripts/dsf smoke
./scripts/dsf deploy --env dev --provider aws --web-dir ../DoEventsWEB
./scripts/dsf promote-qa   # falla — QA inhabilitado
```

## Entorno local (sin GitHub Actions)

Itera en `simulation/` con copia aislada de DoEventsWEB — **no toca repos productivos ni dispara pipelines DEV**.

```powershell
# Desde monorepo
cd C:\DoEvents\AplicacionWEB
.\run-dsf-local.ps1                    # ciclo: prepare → gap(dry) → build → validate
.\run-dsf-local.ps1 -Phase prepare     # solo comparación + gates G0
.\run-dsf-local.ps1 -Phase gap         # gap loop sin agente (o -LiveAgent con CURSOR_API_KEY)
.\run-dsf-local.ps1 -Phase build       # npm run build:devaws en sandbox

# Batería fixtures Lovable (v13–v17 + discover-joyful-feed)
cd DoEventsCICD\simulation
.\run-simulation.ps1
```

Config: `simulation/local.config.json` (rutas a discover-joyful-feed, DoEventsWEB, DoEventsBack).
Secretos opcionales: copiar `simulation/local.env.example` → `local.env`.

| Modo | Git push | Deploy AWS | Agente |
|------|----------|----------|--------|
| Local default | No | No | Dry-run |
| `--live-agent` | Sí (GitHub) | No | Cursor API |
| `--deploy` + credenciales | No | Sí | — |

Salida: `simulation/output/dsf-local/<run-id>/`

## Cloud providers

| Provider | Script | Entorno auto |
|----------|--------|--------------|
| AWS | `scripts/deploy/providers/aws-deploy.sh` | DEV |
| Azure | `scripts/deploy/providers/azure-deploy.sh` | Stub |

Config en `cicd.config.json` → `cloud.providers`.

## Reglas extensibles

Añadir `Reglas/custom/mi-regla.yml`:

```yaml
name: mi-regla
gate: block
scanPath: packages/shell/src/pages
forbidPattern: patron-regex
```

## Artefactos inmutables

Tras deploy DEV, `publish-artifact.sh` guarda build en `s3://doevents-cicd-artifacts-dev/builds/{sha}/`.

Promoción QA usará el mismo tarball cuando se habilite.

## Nueva aplicación

1. Copiar `DoEventsCICD/` como plantilla
2. Editar `cicd.config.json` (repos, cloud, paths)
3. Copiar `templates/.lovable-port-map.json` al repo WEB
4. Configurar `discover-joyful-feed` trigger
5. Bootstrap `ReglasAgente/` desde `Reglas/artefactos-web/`

## Documentación

- [Runbook DSF](docs/runbook-dsf.md)
- [Arquitectura](docs/ARQUITECTURA.md)
- [Reportes](Reports/README.md)
