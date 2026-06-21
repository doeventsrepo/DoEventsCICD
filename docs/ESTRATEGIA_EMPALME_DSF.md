# Estrategia de empalme DSF — Python-first (v4)

## Pipeline v4 (15 agentes)

```text
0 diff-intelligence → 1 rules-validation → 2 port-map-resolver → 3 rules-refinement
→ 4 python-empalme → 5 dependency-guard → 6 backend-contract-check
→ 7 cursor-escalation (1×) → 8 quality-gate → 9 visual-regression
→ 10 premerge-review → 11 backend-analysis → 12 deploy DEV → 13 smoke → 14 report-generator
```

Gap-loops: **prohibidos**. Cursor: solo refuerzo puntual (max 5 archivos, 1×).

---

# Estrategia de empalme DSF — Python-first (empresa)

Documento operativo para sincronizar diseño Lovable → DoEventsWEB **sin loops** y **sin consumo excesivo de tokens Cursor**.

---

## Principio

```text
Lovable diseña  →  Python empalma (determinista, $0)  →  Reporte
                         ↓
              [Opcional] Cursor refuerzo puntual (max 5 archivos, 1 vez)
                         ↓
                    Deploy DEV + smoke
```

| Capa | Herramienta | Costo tokens |
|------|-------------|--------------|
| Detección diff | `analyze-lovable-diff.py` | 0 |
| Comparación | `compare-design-similarity.py` | 0 |
| Empalme | `run-python-empalme.py` + `empalme_engine.py` | 0 |
| Orquestación | `empalme-orchestrator.py` | 0 |
| Refuerzo | `run-gap-empalme-agent.py` (1 batch, desactivado por defecto) | Cursor API |
| Loop gap | **DESACTIVADO** (`maxGapBatches: 0`) | — |

---

## Qué hace el agente Python (sin IA)

Para cada archivo **cambiado en Lovable** (scope `diff-only`):

1. Elimina bloques `MOCK_*` y datos fake
2. Reescribe imports `@/` → `@lovable/`
3. Aplica fixes de tokens (`text-white` → `text-primary-foreground`, etc.)
4. Escribe en la ruta WEB del `.lovable-port-map.json`
5. Clasifica el resto:
   - **cursor** — componente grande o lógica bridge compleja
   - **manual** — drift menor o revisión humana
   - **backend** — integraciones API/pagos/KYC

---

## Configuración (`cicd.config.json`)

```json
"empalmeStrategy": {
  "mode": "python-first",
  "disableGapLoop": true,
  "scope": "diff-only",
  "cursorFallbackEnabled": false,
  "maxCursorEscalations": 1,
  "maxCursorFilesPerRun": 5
}
```

---

## Flujo en producción

1. Diseñador ajusta UI en Lovable → push a `discover-joyful-feed/main`
2. `trigger-cicd-sync.yml` dispara `dsf-sync-dev.yml` con `run_gap_loop=false`
3. **prepare**: valida reglas, genera manifiesto diff, comparación diseño
4. **adapt**: `empalme-orchestrator.py` (Python) → commit en `feature/cicd/dev-automation`
5. **deploy-dev**: build + S3 + smoke 6/6
6. Artefactos: `empalme-report-{runId}.json` + `Reports/*-empalme-*.md`

### Activar Cursor (solo con aprobación)

En workflow dispatch:

```bash
gh workflow run dsf-sync-dev.yml -f cursor_fallback=true
```

Requiere `cursorFallbackEnabled: true` en config **o** flag explícito en CI.

---

## Simulación local (sin API, sin loop)

```powershell
cd DoEventsCICD

# Dry-run — solo reporte
python simulation/scripts/run-empalme-simulation.py `
  --file src/components/feed/FeedBanner.tsx

# Aplicar en sandbox
python simulation/scripts/run-empalme-simulation.py --apply `
  --file src/components/feed/FeedBanner.tsx
```

Orquestador directo:

```powershell
python scripts/lovable-sync/empalme-orchestrator.py `
  --lovable-dir ../discover-joyful-feed `
  --web-dir ../DoEventsWEB `
  --port-map ../DoEventsWEB/.lovable-port-map.json `
  --change-manifest artifacts/test-manifest.json `
  --run-id local-test `
  --dry-run
```

---

## Qué ajustar en Lovable para acople perfecto

Ver prompt Lovable: **`docs/PROMPT_ESTRUCTURAR_LOVABLE_DSF.md`**

### 0. `reglasEmpalme/` (routing agentes — NUEVO)

| Archivo | Propósito |
|---------|-----------|
| `schema-capas.yml` | Definición capas: diseño, formulario, campos, lógica, navegación, backend |
| `routing-agentes.yml` | Python vs Cursor vs manual vs backend |
| `component-index.yml` | Índice src → ruleId → webPath → agentTier (Lovable lo mantiene) |

Cada YAML en `reglasActuacion/` debe incluir bloque `empalme:` con `layers.*.impact` y `agentTier`.

### 1. `reglasDiseno/` (obligatorio)

| Archivo | Propósito |
|---------|-----------|
| `tokens.yml` | Colores, tipografía, radius — el agente Python corrige hardcoded |
| `breakpoints.yml` | Responsive consistente |
| `component-conventions.yml` | Nombres, estructura carpetas |

**Regla:** usar clases semánticas (`bg-primary`, `text-foreground`) — nunca `text-white`, `bg-[#xxx]`.

### 2. `reglasActuacion/` (por flujo)

Un YAML por pantalla/flujo crítico. El pipeline los lee como contexto; sin YAML el empalme es ciego al comportamiento esperado.

Pendientes prioritarios: MapView, ProfileView, GlobalSearch, sheets PRO, asistente IA, EventPublished, VenueDetail.

### 3. Estructura de archivos

- Componentes en `src/components/{dominio}/NombreView.tsx`
- Páginas en `src/pages/` solo cuando son rutas
- Evitar lógica Supabase/mock en componentes UI — usar datos de ejemplo solo en Lovable, el empalme los elimina

### 4. Port-map (DoEventsWEB)

Cada archivo UI debe tener entrada en `.lovable-port-map.json`:

- Reescrituras estructurales → `"compareMode": "delegated"` (MapView→MapPage, auth MFE)
- `exclude` para páginas ya en mfe-auth

### 5. Convención de commits

Tras cada sync exitoso el commit WEB incluye `[lovable:{sha}]` para catch-up diff.

---

## Reporte empalme

Cada run genera:

| Artefacto | Contenido |
|-----------|-----------|
| `empalme-python-result-{runId}.json` | applied / cursorRequired / manualRequired / backendRequired |
| `empalme-summary-{runId}.json` | sim before/after, delta, flags |
| `Reports/{date}-empalme-{runId}.md` | Tablas legibles para el equipo |

Secciones del MD:

- **Ajustes aplicados (Python)**
- **Escalar a Cursor** (si aplica)
- **Ajustar a mano**
- **Backend requerido**
- **Delta por archivo**

---

## Objetivo de similitud realista

| Métrica | Meta operativa |
|---------|----------------|
| Archivos del **diff** tocados | ≥95% empalme Python |
| Similitud global (169 archivos) | Subir gradualmente con empalme inicial manual de core |
| Cursor API | ≤5 archivos por sync, solo con `cursor_fallback=true` |

La similitud global al 98% requiere empalme base de flujos críticos (no loops automáticos).

---

## Checklist implantación empresa

- [ ] `autoChainGapEmpalme: false` en `cicd.config.json`
- [ ] Trigger Lovable con `run_gap_loop=false`
- [ ] Completar `reglasDiseno/` + YAML faltantes en Lovable
- [ ] Corregir port-map (index.css, delegated auth/map/search)
- [ ] Probar simulación local por flujo antes de activar CI
- [ ] Cursor API solo con presupuesto y flag `cursor_fallback=true`
- [ ] Revisar `Reports/*-empalme-*.md` tras cada sync
