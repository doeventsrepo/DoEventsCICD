# Agente Cursor: adaptar Lovable → DoEventsWEB

> Orquestado por **DoEventsCICD**. Reglamento completo: `Reglas/operativas/reglamento-cursor-api.md`

## BLOQUEO OBLIGATORIO

**Sin leer `ReglasAgente/reglas-front.md` en DoEventsWEB, el agente NO puede modificar código.**

## Regla de oro

```text
Lovable diseña. DoEventsWEB interpreta. DoEventsBack gobierna los datos.
El agente adapta, NO copia.
Diseño de Lovable sí. Mocks de Lovable no. Backend real siempre.
```

## Prohibiciones absolutas

1. **NO** copiar/pegar componentes Lovable sobre `packages/shell/src/lovable/` existentes.
2. **NO** activar mocks (`mockData`, `mockUsers`, arrays estáticos) en runtime de `pages/`.
3. **NO** reemplazar hooks/servicios de `@doevents/shared` o `lovable-bridge/*`.
4. **NO** romper login, pagos, tickets, checkout, permisos sin clasificar como RISKY.
5. **NO** secretos ni debilitar auth.
6. **NO** desplegar DoEventsBack/DoEventsIA automáticamente a producción.

## Proceso obligatorio

```text
1. Leer ReglasAgente/reglas-front.md (completo)
2. Leer reglamento + regla-comparacion-diseno.md
3. Ejecutar/revisar design-comparison.json (% similitud Lovable vs WEB)
4. Implementar TODAS las diferencias de diseño pendientes (empalme, no copy-paste)
5. Leer manifiesto + agent-sync-context.md + reglas YAML Lovable (referencia)
6. Clasificar: VISUAL | FRONTEND_LOGIC | BACKEND_REQUIRED | RISKY
7. Adaptar en componentes EXISTENTES (pages/, lovable-bridge/)
8. npm run build:devaws
9. Re-comparar diseño — objetivo ≥98% similitud
10. Actualizar ReglasAgente/ (4 archivos) + Reports/
11. Commits en rama **feature/cicd/dev-automation** (unica rama de automatizacion) — NO push a develop/main/release ni ramas feature/lovable/adapt-*
```

## Regla de comparación de diseño (obligatoria)

- Comparar **todo** diseño Lovable (`src/components`, `src/pages`) vs DoEventsWEB mapeado.
- Todo archivo con similitud <98% o ausente en WEB debe ser **ajustado** respetando empalme.
- **NO** copy-paste literal; **NO** mocks en runtime.
- Reportar `overallSimilarityPercent` antes y después en `Reports/` y `cambios-lovable.json`.

## Arquitectura

| Capa | Ruta |
|------|------|
| Diseño Lovable (solo lectura) | `doeventsrepo/discover-joyful-feed` `src/` |
| UI adaptada | `packages/shell/src/lovable/` |
| Integración real | `packages/shell/src/lovable-bridge/` |
| Páginas | `packages/shell/src/pages/` |
| API | `packages/shared/src/` |
| Reglas agente | `ReglasAgente/` |
| Reglas negocio YAML | `reglasActuacion/` (en repo diseño) |
| CI/CD | `doeventsrepo/DoEventsCICD` |

## Entregables obligatorios (ReglasAgente/)

- `cambios-lovable.json` — run con `mocksUsed: false`, `buildResult`, `agentStatus`
- `decision-log.md` — 7 secciones por ejecución
- `impacto-backend.md` — si hay brecha backend
- `reglas-front.md` — actualizar si hay reglas nuevas

## Validación final

`npm run build:devaws` debe pasar (entorno DEV sa-east-1). Ejecutar búsqueda anti-mock:

```bash
grep -R "mock\|fake\|dummy\|sampleData\|hardcoded" packages/shell/src/pages || true
```
