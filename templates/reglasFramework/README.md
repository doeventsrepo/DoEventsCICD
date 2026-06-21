# reglasFramework — DSF portable rules

Reglas **reutilizables** del Design Sync Framework para cualquier aplicación web.

Al bootstrap de un nuevo proyecto, copiar este directorio y parametrizar `dsf-core.json`.

## Uso

```bash
# Bootstrap nuevo proyecto
cp templates/reglasFramework/dsf-core.template.json cicd.config.json
# Editar designRepo, appRepo, bridgeDir, cloudProvider
bash scripts/bootstrap-dsf-app.sh
```

## Contenido

| Archivo | Propósito |
|---------|-----------|
| `dsf-core.template.json` | Núcleo parametrizable DSF |
| `phases.template.json` | Fases 0–6 del playbook |
| `agents.template.json` | Cadena de agentes IA |
| `gates.template.yml` | Gates G0–G6 estándar |
| `bootstrap-checklist.md` | Checklist Fase 0 |

## Proyecto actual (DoEvents)

Configuración activa en `DoEventsCICD/cicd.config.json` — instancia de este template.
