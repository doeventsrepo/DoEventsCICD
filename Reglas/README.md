# Reglas — Agente Cursor API Key (Lovable → DoEventsWEB)

Directorio **fuente de verdad** en DoEventsCICD para las reglas que debe seguir el agente (Cursor API Key / Cloud Agents) al **empalmar** código de Lovable en DoEventsWEB.

## Estructura

```text
Reglas/
├── reglas.config.json          # Rutas, gates y artefactos (leído por scripts)
├── operativas/                 # Reglamento y prompts para la API del agente
│   ├── reglamento-cursor-api.md
│   ├── prompt-empalme-web.md
│   └── prompt-fullstack.md
├── artefactos-web/             # Plantillas → DoEventsWEB/ReglasAgente/
│   ├── reglas-front.md         # Gate obligatorio (≥500 bytes en WEB)
│   ├── cambios-lovable.json
│   ├── decision-log.md
│   └── impacto-backend.md
└── referencia/
    └── fuentes-reglas.md       # reglasActuacion vs Reglas vs ReglasAgente
```

## Cuatro capas de reglas (+ framework portable)

| Capa | Ubicación | Quién la edita |
|------|-----------|----------------|
| Negocio UX (YAML) | `discover-joyful-feed/reglasActuacion/` | Diseño Lovable |
| Diseño / empalme | `discover-joyful-feed/reglasDiseno/` | Diseño Lovable |
| Operativas agente | **`Reglas/`** (este repo) | Equipo CICD |
| Runtime por sync | `DoEventsWEB/ReglasAgente/` | Pipeline + agente |
| Framework portable | `templates/reglasFramework/` | Equipo CICD (multi-app) |

## Flujo en pipeline

1. **Validar** YAML en checkout Lovable (`reglasActuacion/` + `reglasDiseno/`).
2. **Orquestador** multi-agente (`scripts/agents/orchestrator.py`) — pre-adapt / adapt / post-adapt.
3. **Bootstrap** `Reglas/artefactos-web/` → `DoEventsWEB/ReglasAgente/` si falta.
4. **Gate** `reglas-front.md` en WEB (mín. 500 bytes).
5. **Invocar agente** empalme concatenando prompts operativos + ReglasAgente.

## Bootstrap en DoEventsWEB

```bash
bash scripts/bootstrap-web-reglas-agente.sh ../DoEventsWEB
```

## Configuración

Rutas centralizadas en `reglas.config.json` y `cicd.config.json` (`paths.cicdReglas`).
