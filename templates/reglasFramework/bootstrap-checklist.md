# Fase 0 — Bootstrap DSF checklist

## Repositorios

- [ ] Repo CICD (`DoEventsCICD`) con `cicd.config.json` y `dsfCore`
- [ ] Repo diseño Lovable conectado a GitHub
- [ ] Repo frontend destino con rama `feature/cicd/dev-automation`
- [ ] Repo backend (opcional fase 4+)

## Archivos obligatorios

- [ ] `.lovable-port-map.json` en frontend
- [ ] `ReglasAgente/` bootstrapped desde `Reglas/artefactos-web/`
- [ ] `reglasActuacion/` en repo diseño
- [ ] `reglasDiseno/` en repo diseño
- [ ] `Reglas/operativas/` en CICD

## Secretos GitHub

- [ ] `DOEVENTS_WEB_PAT` / `DOEVENTS_CICD_PAT`
- [ ] `CURSOR_API_KEY` (agentes empalme)
- [ ] AWS credentials DEV (deploy)

## Validación local

```powershell
cd DoEventsCICD/simulation
powershell -ExecutionPolicy Bypass -File .\run-simulation.ps1
python run-dsf-local.py all
python ../scripts/agents/orchestrator.py --dry-run --phase pre-adapt
```

## Deploy

- [ ] Solo DEV habilitado (`deployEnvironments.dev.enabled: true`)
- [ ] QA/prod manualOnly
