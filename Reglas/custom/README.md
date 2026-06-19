# Reglas custom DSF

Coloca archivos `.yml` aquí para extender los gates del pipeline sin modificar workflows.

## Formato

```yaml
name: mi-regla
description: Descripción legible
gate: block | warn    # block = falla el pipeline
scanPath: packages/shell/src/pages
forbidPattern: regex-opcional
```

## Ejecución

- Automática en `dsf-sync-dev.yml` (job `custom-gates`)
- Local: `python3 scripts/rules/run-custom-gates.py Reglas/custom --web-dir ../DoEventsWEB`

## Reglas incluidas

| Archivo | Descripción |
|---------|-------------|
| `no-hardcoded-api-urls.yml` | Bloquea URLs API hardcodeadas en pages |
