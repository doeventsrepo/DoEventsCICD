# Plantillas Cursor Rules — QA manual

Copiar a cada repositorio para que Cursor aplique reglas en chats locales.

## Instalación

```powershell
# Desde raíz monorepo AplicacionWEB
New-Item -ItemType Directory -Force -Path DoEventsWEB\.cursor\rules | Out-Null
New-Item -ItemType Directory -Force -Path DoEventsBack\.cursor\rules | Out-Null
Copy-Item DoEventsCICD\templates\cursor-rules\qa-doevents-web.mdc DoEventsWEB\.cursor\rules\
Copy-Item DoEventsCICD\templates\cursor-rules\qa-doevents-back.mdc DoEventsBack\.cursor\rules\
```

Reiniciar Cursor o recargar ventana. Verificar en **Cursor Settings → Rules**.

## Documentación asociada

- [CURSOR_QA_ENTORNO_DESARROLLADORES.md](../docs/CURSOR_QA_ENTORNO_DESARROLLADORES.md)
- [PROMPT_ESTANDAR_DESARROLLO_QA.md](../docs/PROMPT_ESTANDAR_DESARROLLO_QA.md)

## Notas

- `alwaysApply: false` — las reglas aplican cuando trabajas en los globs listados o mencionas `@qa-*`
- DEV automático (DoEventsCICD pipeline) usa `Reglas/operativas/*`, no estas plantillas
- No commitear `.env.qa.local` ni credenciales
