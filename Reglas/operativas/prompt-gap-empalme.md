# Agente Cursor: cierre de gaps Lovable → DoEventsWEB

> Flujo **lovable-gap-empalme** — empalme focalizado en ítems pendientes del manifiesto `gap-manifest.json`.

## Objetivo

Implementar **solo** los gaps del batch actual (similitud <98% o ausentes en WEB) hasta dejarlos alineados con Lovable, sin copy-paste literal ni mocks en runtime.

## Regla de oro

```text
Cada gap del manifiesto debe quedar en estado DONE (frontend) o BACKEND_REQUIRED (documentado).
Nunca inventar datos ni endpoints.
Fidelidad visual: preservar diseño Lovable (colores, toggles, CSS vars, copy) — solo adaptar imports y quitar mocks.
```

## Proceso obligatorio por gap

1. Leer `ReglasAgente/reglas-front.md` completo.
2. Para cada ítem en `gap-manifest.json` → `gaps[]`:
   - Abrir componente Lovable (referencia UX).
   - Localizar o crear equivalente en WEB (`lovable-bridge/*`, `pages/`, `mfe-auth`).
   - Empalmar diseño y comportamiento con APIs reales (`@doevents/shared`).
   - Si el gap **no puede** cerrarse sin backend nuevo: marcar `BACKEND_REQUIRED` y documentar contrato.
3. `npm run build:devaws` exitoso.
4. Actualizar artefactos (ver sección Salida obligatoria).

## Salida obligatoria — archivos a actualizar

### `ReglasAgente/decision-log.md`

Añadir entrada `gap-empalme-{runId}` con:

1. Resumen del empalme (qué gaps se atacaron y resultado).
2. Tabla: Feature | Archivo WEB | Estado (`DONE` | `BACKEND_REQUIRED` | `BLOCKED`).
3. Similitud antes/después (%).
4. Build: `npm run build:devaws` OK/FAIL.

### `ReglasAgente/cambios-lovable.json`

Añadir run con:

- `id`: `gap-empalme-{runId}`
- `gapBatch`: número de ítems del manifiesto
- `webFilesModified`: lista real de archivos tocados
- `gapsClosed`: lista de `lovablePath` cerrados en frontend
- `gapsBackendRequired`: lista de gaps que requieren backend
- `designSimilarityPercentBefore` / `After`
- `agentStatus`: `finished`

### `ReglasAgente/impacto-backend.md`

Reemplazar sección **Backend pendiente para 100%** con tabla:

| Gap / Feature | lovablePath | webPath | Motivo | Endpoint / Lambda | Tabla DynamoDB | Acción | Prioridad |
|---------------|-------------|---------|--------|-------------------|----------------|--------|-----------|

Y sección **Empalme realizado (última ejecución)** con lo implementado en frontend.

### `docs/changes/gap-empalme-latest.md`

Resumen ejecutivo en español para el equipo (empalme hecho + backend pendiente + gaps restantes).

## Prohibido

- Copy-paste literal de archivos Lovable.
- Mocks en `pages/` o runtime.
- Push a `main`, `develop`, `release` o ramas `feature/lovable/adapt-*`.
- Marcar `DONE` un gap que sigue usando datos falsos.

## Rama de salida

Push únicamente a **`feature/cicd/dev-automation`**.
