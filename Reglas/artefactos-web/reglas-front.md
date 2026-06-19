# Reglas Frontend — Agente Cursor (DoEventsWEB)

> Copiar este archivo a `DoEventsWEB/ReglasAgente/reglas-front.md` al bootstrap del repo.
> El pipeline **bloquea** la adaptación si este archivo no existe o tiene menos de 500 bytes.

## 1. Propósito

Define reglas obligatorias para el agente Cursor API que adapta cambios de Lovable (`discover-joyful-feed`) a DoEventsWEB sin mocks ni copia literal.

## 2. Regla maestra

```text
Lovable diseña. DoEventsWEB interpreta. DoEventsBack gobierna. El agente adapta. El agente nunca copia.
```

## 3. Flujo obligatorio del agente

1. Leer cambios Lovable y `reglasActuacion/`.
2. Comparar contra DoEventsWEB existente.
3. Clasificar: VISUAL, FRONTEND_LOGIC, BACKEND_REQUIRED, RISKY.
4. Reutilizar `lovable-bridge/` y `@doevents/shared`.
5. Implementar solo lo necesario.
6. Prohibir mocks en runtime.
7. Ejecutar `npm run build:devaws`.
8. Actualizar `ReglasAgente/` (4 archivos).
9. Documentar en `decision-log.md`.

## 4. Prohibición de mocks

No crear ni activar: `mock`, `fake`, `dummy`, `sampleData`, `hardcodedEvents`, `mockTickets`, `mockOrders`.

## 5. Clasificación VISUAL

Solo layout, estilos, copy, responsive. No tocar servicios ni APIs.

## 6. Clasificación FRONTEND_LOGIC

Validaciones, navegación, mensajes de error, estados de formulario. Respetar contratos API.

## 7. Clasificación BACKEND_REQUIRED

Nuevo campo persistente, endpoint, validación servidor. Documentar en `impacto-backend.md`. No desplegar automáticamente.

## 8. Clasificación RISKY

Login, pagos, tickets, órdenes, QR, permisos. Requiere revisión humana antes de merge.

## 9. Arquitectura de capas

| Capa | Ruta |
|------|------|
| UI referencia | `packages/shell/src/lovable/` |
| Integración | `packages/shell/src/lovable-bridge/` |
| Páginas | `packages/shell/src/pages/` |
| API | `packages/shared/src/` |

## 10. Formularios

Toda regla Lovable debe convertirse en validación real: bloqueo de submit, mensaje de error, manejo de error backend.

## 11. Redirecciones

Solo navegar tras respuesta exitosa de API. Nunca `navigate` inmediato sin persistencia.

## 12. Backend (DoEventsBack)

Solo modificar en rama separada si BACKEND_REQUIRED. Nunca deploy prod automático.

## 13. Validaciones de pipeline

- `npm run build:devaws` exitoso
- Sin mocks nuevos en `packages/shell/src/pages`
- Sin secretos en commits
- Artefactos `ReglasAgente/` actualizados

## 14. Reporte final

Generar resumen con: tipo de cambio, archivos WEB/Back, evidencia anti-mock, build/test, riesgos, decisión APPLIED | BLOCKED | REQUIRES_REVIEW.

## 15. Bloqueo

Si no hay certeza, clasificar REQUIRES_REVIEW, no inventar mocks, no copiar Lovable literalmente.

---

Reglamento completo: `DoEventsCICD/Reglas/operativas/reglamento-cursor-api.md`
