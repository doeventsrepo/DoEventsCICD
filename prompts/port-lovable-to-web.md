# Agente Cursor: adaptar Lovable → DoEventsWEB

> Orquestado por **DoEventsCICD**. Reglamento completo: `prompts/REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md`

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
2. Leer REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md
3. Leer manifiesto + agent-sync-context.md + reglas YAML Lovable (referencia)
4. Clasificar: VISUAL | FRONTEND_LOGIC | BACKEND_REQUIRED | RISKY
5. Adaptar en componentes EXISTENTES (pages/, lovable-bridge/) — no copia literal
6. npm run build:qa
7. Actualizar ReglasAgente/ (4 archivos)
8. Commits separados por tipo
```

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

`npm run build:qa` debe pasar. Ejecutar búsqueda anti-mock:

```bash
grep -R "mock\|fake\|dummy\|sampleData\|hardcoded" packages/shell/src/pages || true
```
