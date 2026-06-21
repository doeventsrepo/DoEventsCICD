# Prompt — Configurar reglas DSF en Lovable (discover-joyful-feed)

Copia y pega el bloque **PROMPT COMPLETO** en Lovable (chat del proyecto) o en Cursor al editar `discover-joyful-feed`.  
Objetivo: dejar configuradas las **seis capas de reglas** que alimentan el pipeline DSF.

> **Actualización v3.2:** usar también `docs/PROMPT_ESTRUCTURAR_LOVABLE_DSF.md` para
> alinear Lovable con agentes Python + capas empalme (diseño, formulario, campos, lógica, navegación, backend).

---

## PROMPT COMPLETO (copiar desde aquí)

```
Eres el arquitecto de reglas del proyecto Do•events en Lovable. Debes crear y mantener
TODAS las capas de reglas que el Design Sync Framework (DSF) consume para empalmar
diseño → DoEventsWEB → deploy DEV automático.

## Contexto del pipeline

Flujo: Lovable DISEÑA → DSF DETECTA → Agentes EMPALMAN → Gates VALIDAN → AWS DEV DESPLIEGA

Repositorio diseño: discover-joyful-feed (este proyecto)
Repositorio destino: DoEventsWEB (packages/shell/src/lovable + lovable-bridge)
Orquestación: DoEventsCICD (GitHub Actions dsf-sync-dev.yml)

## CAPA 1 — Negocio UX (EXISTENTE): reglasActuacion/

Ubicación: `reglasActuacion/<dominio>/<nombre>.yml`

Propósito: describir QUÉ debe hacer la UI (flujos, validaciones, botones, workflows).

Reglas obligatorias por archivo YAML:
- id: string único (ej. eventos.crear-evento)
- domain: eventos | tickets | usuarios | pagos | servicios | lugares | invitados | publicaciones | notificaciones | chat | admin | acceso | bancarios | persistencia
- version: semver string
- description: resumen funcional
- source: lista de archivos src/ que implementan la regla
- campos, calculos, ui, acciones, workflow según convención en reglasActuacion/README.md

Acciones en Lovable:
1. Por cada formulario o flujo nuevo, crear/actualizar su YAML ANTES o JUNTO al cambio UI.
2. Mantener `source:` apuntando al componente real en src/.
3. Si la acción requiere backend real, marcar en acciones.<nombre>.backend con endpoint esperado.
4. NO usar mocks en runtime: documentar como simulado solo si Lovable aún no tiene API.

Dominios mínimos a cubrir:
- eventos/, tickets/, usuarios/, pagos/, servicios/, lugares/, invitados/, publicaciones/
- admin/, acceso/, chat/, bancarios/, persistencia/, notificaciones/

## CAPA 2 — Diseño / empalme (NUEVA): reglasDiseno/

Ubicación: `reglasDiseno/`

Propósito: tokens, breakpoints, convenciones de componentes para que el comparador de similitud
y el agente de empalme sepan CÓMO debe verse y nombrarse la UI.

Crear estos archivos:

### reglasDiseno/tokens.yml
```yaml
id: diseno.tokens
version: "1.0.0"
domain: diseno
description: Design tokens Do•events (colores, tipografía, spacing)
colors:
  primary: "#..."      # brand principal
  secondary: "#..."
  background: "#..."
  foreground: "#..."
  muted: "#..."
  destructive: "#..."
  success: "#..."
typography:
  fontFamily: "Inter, system-ui, sans-serif"
  scale:
    xs: "0.75rem"
    sm: "0.875rem"
    base: "1rem"
    lg: "1.125rem"
    xl: "1.25rem"
    "2xl": "1.5rem"
spacing:
  unit: 4          # px base (Tailwind 1 = 4px)
  pagePadding: "1rem"
  cardPadding: "1rem"
  sectionGap: "1.5rem"
radius:
  sm: "0.375rem"
  md: "0.5rem"
  lg: "0.75rem"
  full: "9999px"
shadows:
  card: "0 1px 3px rgba(0,0,0,0.1)"
  modal: "0 10px 25px rgba(0,0,0,0.15)"
```

### reglasDiseno/breakpoints.yml
```yaml
id: diseno.breakpoints
version: "1.0.0"
domain: diseno
description: Breakpoints responsive
breakpoints:
  sm: 640
  md: 768
  lg: 1024
  xl: 1280
  "2xl": 1536
layout:
  maxContentWidth: "1280px"
  sidebarWidth: "280px"
  mobileNavHeight: "56px"
```

### reglasDiseno/component-conventions.yml
```yaml
id: diseno.component-conventions
version: "1.0.0"
domain: diseno
description: Convenciones de nombres y estructura de componentes Lovable
naming:
  pages: "*Page.tsx o *View.tsx en src/pages/"
  panels: "*Panel.tsx en src/components/admin/"
  modals: "*Modal.tsx o *Sheet.tsx"
  hooks: "use*.ts en src/hooks/"
  contexts: "*Context.tsx en src/contexts/"
structure:
  - "Un componente = una responsabilidad"
  - "Estados loading/error/empty obligatorios en listas y detalle"
  - "Props tipadas; evitar any"
  - "Sin mockData en export default de págenes de producción"
forbidden:
  - "src/integrations/supabase/ en runtime destino"
  - "src/data/ con fixtures hardcodeados en pages/"
  - "Copy-paste de MapView/ProfileView sin adaptación"
empalmeHints:
  bridgePattern: "Lovable*Bridge.tsx en destino WEB conecta a @doevents/shared"
  authPages: "Login/SignUp delegados a packages/mfe-auth (compareMode: delegated)"
```

### reglasDiseno/README.md
Documentar que estos archivos alimentan compare-design-similarity.py y el agente de empalme.

## CAPA 3 — Port-map (ampliación)

Verificar que `.lovable-port-map.json` en DoEventsWEB incluya:
- src/components/ → packages/shell/src/lovable/components/
- src/pages/ → packages/shell/src/pages/ (con excepciones auth MFE)
- reglasActuacion/ → referencia (no copia literal)
- reglasDiseno/ → referencia para agente

Por cada página o componente NUEVO en src/, añadir entrada explícita al port-map antes del merge.

## CAPA 4 — Trigger CICD

Asegurar que push a main dispare sync cuando cambien:
- src/**
- public/**
- reglasActuacion/**
- reglasDiseno/**
- tailwind.config.ts, index.html, package.json

## Reglas de calidad Lovable (OBLIGATORIAS)

1. Cada cambio UI con lógica de negocio → YAML en reglasActuacion/.
2. Cada cambio visual global → actualizar reglasDiseno/tokens.yml o breakpoints.yml.
3. Componentes nuevos → seguir component-conventions.yml.
4. Sin supabase/mocks en flujos que irán a producción DEV.
5. Commits descriptivos: feat(ui): ... / feat(rules): ...
6. Probar build local: npm run build antes de push.

## Entregables que debes generar ahora

1. Crear carpeta reglasDiseno/ con tokens.yml, breakpoints.yml, component-conventions.yml, README.md
2. Auditar reglasActuacion/ — completar YAML faltantes para pantallas en src/pages/
3. Listar componentes src/ sin regla asociada → proponer borradores YAML
4. Verificar coherencia tokens ↔ tailwind.config.ts
5. Resumen markdown: reglas creadas, gaps pendientes, componentes sin regla

Responde en español. Al terminar, indica qué archivos creaste/modificaste y qué falta para 100% cobertura.
```

---

## Uso recomendado

| Paso | Acción |
|------|--------|
| 1 | Abrir Lovable → proyecto discover-joyful-feed |
| 2 | Pegar el PROMPT COMPLETO en el chat |
| 3 | Revisar archivos generados en reglasDiseno/ y reglasActuacion/ |
| 4 | Commit + push a main → dispara DSF Sync DEV automáticamente |
| 5 | Verificar reporte en DoEventsCICD/Reports/ y dev.doeventsapp.com |

## Validación local (antes de push)

```powershell
cd c:\DoEvents\AplicacionWEB\DoEventsCICD
python scripts/lovable-sync/validate-rules.py ..\discover-joyful-feed\reglasActuacion
python scripts/lovable-sync/validate-design-rules.py ..\discover-joyful-feed\reglasDiseno
python -m dsf.cli validate --port-map-check --lovable-dir ..\discover-joyful-feed --web-dir ..\DoEventsWEB
```

## Referencias

- Convención reglasActuacion: `discover-joyful-feed/reglasActuacion/README.md`
- Reglas agente: `DoEventsCICD/Reglas/README.md`
- Framework portable: `DoEventsCICD/templates/reglasFramework/README.md`
- Pipeline: `DoEventsCICD/docs/DSF.md`
