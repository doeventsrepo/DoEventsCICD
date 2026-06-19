# Fuentes de reglas — mapa del ecosistema

## reglasActuacion (repo diseño)

- **Repo:** `doeventsrepo/discover-joyful-feed`
- **Formato:** YAML por dominio (`eventos/`, `pagos/`, `tickets/`, …)
- **Propósito:** Describir comportamiento funcional del frontend (validaciones, flujos, permisos).
- **Disparador CICD:** push en `src/` o `reglasActuacion/` → workflow en DoEventsCICD.

El agente **lee** estos YAML como referencia; **no** los copia a DoEventsWEB tal cual.

## Reglas (repo DoEventsCICD)

- **Ruta:** `DoEventsCICD/Reglas/`
- **Propósito:** Reglamento operativo del agente Cursor API Key, prompts de empalme y plantillas bootstrap.
- **Audiencia:** Scripts `scripts/lovable-sync/*`, workflows GitHub Actions, operadores CICD.

## ReglasAgente (repo DoEventsWEB)

- **Ruta:** `DoEventsWEB/ReglasAgente/`
- **Origen:** Copiado/actualizado desde `Reglas/artefactos-web/` en cada sync.
- **Propósito:** Artefactos **por ejecución** del pipeline (manifiesto, decision log, impacto backend).
- **Gate:** Sin `reglas-front.md` válido, el agente **no** modifica código.

## DoEventsBack

- Impacto documentado en `DoEventsWEB/ReglasAgente/impacto-backend.md` y espejo en `docs/changes/lovable-backend-impact.md`.
- Cambios de código Back solo en ramas `feature/*`, nunca deploy automático a prod.
