# Simulación DoEventsCICD

Entorno aislado para validar el pipeline **antes de implantar** en GitHub/AWS.

## Principios

- **No modifica** `DoEventsWEB` productivo.
- Trabaja sobre `sandbox/DoEventsWEB` (copia local).
- Usa versiones en `C:\DoEvents\AplicacionWEB\Lovable` y `discover-joyful-feed`.
- El agente Cursor se ejecuta en **modo dry-run** (sin API) salvo que definas `CURSOR_API_KEY` y `SIM_RUN_LIVE_AGENT=1`.

## Ejecutar

```powershell
cd c:\DoEvents\AplicacionWEB\DoEventsCICD\simulation
powershell -ExecutionPolicy Bypass -File .\run-simulation.ps1
```

Resultados en:

- `REGISTRO_PRUEBAS.md` — informe legible
- `output/last-run.json` — resultados machine-readable
- `output/<fixture-id>/` — manifiestos y contexto por fuente

## Preparar sandbox WEB (manual)

```powershell
.\prepare-sandbox.ps1
```

Copia `DoEventsWEB` excluyendo `node_modules`, `dist`, `.git`.
