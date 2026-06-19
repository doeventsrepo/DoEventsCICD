# Regla de comparación de diseño — Lovable vs DoEventsWEB

## Propósito

Es el **corazón de la automatización**: medir qué tan alineado está el diseño implementado en DoEventsWEB respecto al diseño fuente en Lovable, detectar gaps, y guiar al agente para **implementar lo faltante** mediante empalme (no copy-paste).

## Obligatorio en cada sync

1. Ejecutar `compare-design-similarity.py` antes y después del agente.
2. Registrar `overallSimilarityPercent` en `Reports/` y `ReglasAgente/cambios-lovable.json`.
3. Si similitud < **98%** o hay archivos `missing_in_web` → el agente **debe** actuar.

## Qué comparar

| Lovable | DoEventsWEB |
|---------|-------------|
| `src/components/**` (excepto `ui/`) | `packages/shell/src/lovable/components/**` |
| `src/pages/**` | `packages/shell/src/pages/**` |
| `src/hooks/**`, `src/contexts/**` | Rutas equivalentes en `lovable/` |

Mapeo: `.lovable-port-map.json`

## Qué debe hacer el agente con las diferencias

Para cada archivo con similitud baja o ausente:

1. **Leer** el componente Lovable como referencia de intención UX (layout, copy, flujo).
2. **Leer** el componente WEB/bridge actual.
3. **Empalmar**: ajustar el WEB existente para reflejar el diseño Lovable.
4. **Prohibido**: pegar el archivo Lovable entero; importar mocks; desconectar API real.
5. **Validar**: `npm run build:devaws` + anti-mocks.

## Métricas

| Métrica | Descripción |
|---------|-------------|
| `overallSimilarityPercent` | Promedio similitud textual normalizada (0–100) |
| `targetSimilarityPercent` | 98 — objetivo post-empalme |
| `alignmentGapPercent` | target − overall |
| `missingInWebCount` | Archivos Lovable sin contraparte WEB |

## Entregables

- `design-comparison.json` — detalle por archivo
- `Reports/*-design-comparison-*.md` — reporte legible
- Actualizar `decision-log.md` con % antes/después del agente

## Post-condición

Tras empalme exitoso, re-ejecutar comparación. El reporte debe mostrar incremento de similitud y reducción de `missingInWeb`.
