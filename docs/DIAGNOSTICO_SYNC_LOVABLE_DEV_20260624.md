# Diagnóstico — sync Lovable → DEV (jun 2026)

## Síntoma

Los triggers `lovable-sync` desde **discover-joyful-feed** fallan en **menos de 20 segundos**. No llegan a empalmar, buildear ni desplegar.

Ejemplo: run [28102433634](https://github.com/doeventsrepo/DoEventsCICD/actions/runs/28102433634) (2026-06-24).

---

## Causa raíz (bloqueante actual)

**Job `resolve` → `ModuleNotFoundError: No module named 'dsf'`**

El workflow ejecuta:

```bash
python3 cicd/dsf/resolve_app_github.py --app-id doevents --cicd-dir cicd
```

Ese script importa `from dsf.app_resolver import ...`, pero Python no tiene `DoEventsCICD/` en `PYTHONPATH` cuando se invoca como archivo suelto.

### Corrección aplicada (local, pendiente push a `main`)

1. `dsf/resolve_app_github.py` — inserta la raíz CICD en `sys.path` al arrancar.
2. `.github/workflows/dsf-sync-dev.yml` — `PYTHONPATH: ${{ github.workspace }}/cicd` en `env` global.

**Sin push a `DoEventsCICD/main`, GitHub sigue fallando.**

---

## Historial — última ejecución que pasó `prepare`

Run [27847959667](https://github.com/doeventsrepo/DoEventsCICD/actions/runs/27847959667) (2026-06-19):

| Job | Resultado |
|-----|-----------|
| prepare | OK |
| adapt (agente Cursor) | OK |
| gap-loop | **FAIL** (~27 min) |
| deploy-dev | **Skipped** |
| validate-and-report | **FAIL** |

Métricas del reporte:

- Similitud pre/post: **59.92%** (objetivo 98%)
- ~104 gaps pendientes
- Agente ejecutado pero **sin mejora de similitud**
- **No hubo deploy** a dev.doeventsapp.com

Errores de gates:

- Deploy DEV no se ejecutó
- Smoke tests no se ejecutaron
- Similitud &lt; 98%

---

## Estado local (sandbox DSF)

`simulation/output/dsf-local/local-final-20260620/LOCAL_VERDICT.json`:

| Campo | Valor |
|-------|-------|
| Similitud | 99.95% |
| gapClosed | true |
| buildStatus | **pending-fix-syntax** |

Build sandbox falla por imports faltantes tras empalme, p. ej.:

- `lovable/data/mockVenues` (importado desde `AIAssistantView.tsx`)

Hasta que `build:devaws` pase en sandbox/productivo, el gate G1 del pipeline también fallará aunque `resolve` esté corregido.

---

## Plan de recuperación (orden)

### 1. Desbloquear pipeline (CICD)

```powershell
# Commit + push solo DoEventsCICD (fix resolve)
git add DoEventsCICD/dsf/resolve_app_github.py DoEventsCICD/.github/workflows/dsf-sync-dev.yml
git commit -m "fix(cicd): PYTHONPATH para dsf resolve en DSF Sync DEV"
git push origin main
```

### 2. Re-ejecutar sync manual

```powershell
gh workflow run "DSF Sync DEV" --repo doeventsrepo/DoEventsCICD `
  -f run_agent=true `
  -f deploy_dev_after=true `
  -f web_cicd_branch=feature/cicd/dev-automation
```

### 3. Cerrar gap build local (antes de confiar en deploy)

En sandbox local (sin GitHub):

- Sincronizar assets Lovable faltantes (`sync-lovable-assets-local.py`)
- Corregir imports rotos post-empalme
- Verificar `npm run build:devaws` OK

### 4. Similitud / empalme

Si tras el fix el pipeline vuelve a quedarse en ~60%:

- Revisar `empalme-orchestrator.py` y port-map
- Confirmar `CURSOR_API_KEY` en secrets environment `dev`
- Revisar artefactos `design-comparison.json` del run

### 5. Reducir ruido de triggers

Cada push a Lovable dispara un run que falla. Opciones:

- Pausar `trigger-cicd-sync.yml` en discover-joyful-feed hasta fix en main
- O cancelar runs pendientes: `gh run list --repo doeventsrepo/DoEventsCICD --status in_progress`

---

## Checklist operador

- [ ] Fix `resolve` pusheado a `DoEventsCICD/main`
- [ ] Un run DSF Sync DEV completa job `resolve` + `prepare`
- [ ] `build:devaws` OK en rama `feature/cicd/dev-automation`
- [ ] Similitud ≥ 98% o empalme Python aplica diffs reales
- [ ] `deploy-dev` → https://dev.doeventsapp.com responde
- [ ] Smoke 6/6 OK

---

## Referencias

- Workflow: `.github/workflows/dsf-sync-dev.yml`
- Config: `cicd.config.json` → `dsf.lovableAutoSync`
- Runbook: `docs/runbook-dsf.md`
- Reporte jun-19: `output/run-27847959667-report/Reports/2026-06-19-dsf-sync-27847959667.md`
