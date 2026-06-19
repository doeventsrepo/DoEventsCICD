# Prompt estándar — desarrollo, limpieza, revisión y deploy QA

Formato acordado para que el equipo envíe instrucciones a **Cursor** de forma repetible: implementación controlada, **clean** del código, **revisión** previa al deploy, y trazabilidad para el desarrollador.

**Audiencia:** ajustes manuales en **QA** (`envRelease`).  
**Setup:** [CURSOR_QA_ENTORNO_DESARROLLADORES.md](./CURSOR_QA_ENTORNO_DESARROLLADORES.md)

---

## 1. Anatomía del prompt (bloques obligatorios)

Cada solicitud a Cursor debe incluir **6 bloques** en este orden:

| Bloque | Propósito |
|--------|-----------|
| `CONTEXTO` | Ticket, entorno, repos, ramas |
| `OBJETIVO` | Qué funcionalidad se ajusta |
| `REGLAS` | Restricciones QA (no mocks, no prod, etc.) |
| `IMPLEMENTAR` | Tareas concretas de código |
| `LIMPIAR` | Refactor mínimo, dead code, imports |
| `REVISAR` | Checklist auto-revisión antes de deploy |
| `DESPLEGAR` | Solo si el dev lo autoriza explícitamente |
| `REGISTRAR` | Artefactos de trazabilidad |

El desarrollador **controla** el deploy: Cursor propone comandos; el humano ejecuta `npm run deploy:qa` o workflow manual.

---

## 2. Plantilla copiable

```markdown
## CONTEXTO
- Ticket: [JIRA-123 / descripción corta]
- Entorno: QA (envRelease) — us-east-2
- Web: https://qa.doeventsapp.com | API: https://api-qa.doeventsapp.com
- Rama: feature/[inicial]/[ticket]-[slug]
- Repos afectados: [ ] DoEventsWEB  [ ] DoEventsBack
- Referencia diseño/reglas: [opcional: ruta reglasActuacion o mockup]

## OBJETIVO
[Un párrafo: qué debe lograr el usuario final en QA]

## REGLAS (obligatorias)
- Entorno QA únicamente; build WEB: `npm run build:qa`
- Backend: `serverless.qa.yml`, stage `qa`, region `us-east-2`
- Prohibido: mocks runtime, secretos en repo, deploy PROD/DEV automático
- Reutilizar servicios/hooks existentes (@doevents/shared, lovable-bridge)
- Si falta endpoint: documentar en DoEventsWEB/docs/changes/ sin inventar datos

## IMPLEMENTAR
1. [Paso concreto — archivos esperados]
2. [Paso concreto]
3. [Tests o validación local]

## LIMPIAR (clean code)
- Eliminar imports/console.log/debug no usados
- Unificar estilo con archivos vecinos (naming, tipos)
- No abstraer en helpers de una sola línea
- Mantener diff mínimo al ticket

## REVISAR (antes de deploy — Cursor debe reportar)
Responder en tabla:

| Check | OK / FAIL | Notas |
|-------|-----------|-------|
| build:qa o serverless package | | |
| Sin secretos en diff | | |
| Sin mocks en pages/ | | |
| Contrato API coherente WEB↔Back | | |
| Tipos TypeScript sin `any` innecesario | | |
| Mensajes de error UX claros | | |

Si algún FAIL: **no proponer deploy**; corregir primero.

## DESPLEGAR
- Autorizado por desarrollador: [ ] NO  [ ] SÍ (solo si REVISAR todo OK)
- WEB: `npm run build:qa` → `npm run deploy:qa` (o listar lambdas)
- Back: listar `aws-lambda-*` y comando `npm run deploy:qa` por servicio
- Post-deploy smoke: [URLs o pasos]

## REGISTRAR
- Actualizar: `DoEventsWEB/docs/changes/[ticket]-qa.md` (resumen + archivos + riesgos)
- Commit message sugerido: `fix(qa): [ticket] descripción`
- PR hacia: `develop`
```

---

## 3. Ejemplo completo — validación stock en checkout (QA)

```markdown
## CONTEXTO
- Ticket: DE-442 — Validar stock de tickets antes de checkout en QA
- Entorno: QA (envRelease) — us-east-2
- Web: https://qa.doeventsapp.com | API: https://api-qa.doeventsapp.com
- Rama: feature/jp/de-442-checkout-stock-qa
- Repos: [x] DoEventsWEB  [x] DoEventsBack
- Referencia: discover-joyful-feed/reglasActuacion/tickets/validacion-stock.yml

## OBJETIVO
En QA, cuando el usuario confirma checkout, el front debe consultar stock real vía API y bloquear el submit si no hay disponibilidad, mostrando mensaje claro. El back debe validar stock en servidor (no confiar solo en el cliente).

## REGLAS (obligatorias)
- Solo QA; lambdas prefijo `qa-`, tablas `-qa`
- No usar arrays mock de tickets en MapPage/CheckoutPage
- Si el endpoint ya existe en api-qa, reutilizarlo; si no, proponer cambio mínimo en `aws-lambda-manageevents` y documentar
- Build WEB obligatorio: `npm run build:qa`

## IMPLEMENTAR

### DoEventsWEB
1. Revisar `packages/shell/src/pages/` flujo checkout existente
2. Integrar llamada a API real (shared service) antes de navegar a pago
3. Estados UI: loading, sin stock, error red
4. Mensajes alineados con regla YAML (validacion-stock)

### DoEventsBack (si aplica)
1. Revisar handler checkout/stock en `aws-lambda-manageevents` o servicio tickets
2. Validar DynamoDB tabla `*-qa` correcta en serverless.qa.yml
3. Respuesta HTTP 409 o 400 con código `INSUFFICIENT_STOCK` documentado

## LIMPIAR
- Quitar cualquier `mockTickets` o datos hardcoded introducidos en exploración
- Consolidar validación en un hook o servicio existente si ya hay patrón similar
- Imports ordenados; sin `console.log` de depuración

## REVISAR
Completar tabla y pegar resultado:

| Check | OK / FAIL | Notas |
|-------|-----------|-------|
| npm run build:qa | | |
| serverless package (lambdas tocadas) | | |
| Sin secretos en diff | | |
| Sin mocks en pages/ | | |
| API documentada si endpoint nuevo | | |
| Prueba manual descrita | | |

## DESPLEGAR
- Autorizado por desarrollador: [ ] NO  [x] SÍ — solo tras mi OK en chat
- WEB: desde `develop` tras merge PR — `npm run build:qa && npm run deploy:qa`
- Back: solo `aws-lambda-manageevents` — `npm run deploy:qa`
- Smoke QA:
  1. Login qa.doeventsapp.com
  2. Evento con tickets limitados → checkout → ver mensaje sin stock
  3. CloudWatch log lambda qa-manageevents sin errores 5xx

## REGISTRAR
- Crear `DoEventsWEB/docs/changes/DE-442-checkout-stock-qa.md` con:
  - Archivos WEB/Back modificados
  - Endpoint(s) usados
  - Evidencia build:qa OK
  - Riesgos / rollback (revert deploy lambda X)
- Commit: `fix(qa): DE-442 validar stock checkout QA`
- PR → develop, revisores: @nombre
```

---

## 4. Comandos cortos (alias de equipo)

Para chats rápidos, el dev puede prefijar:

| Prefijo | Acción |
|---------|--------|
| `@qa-implementar` | Solo bloques CONTEXTO + OBJETIVO + IMPLEMENTAR |
| `@qa-limpiar` | Re-ejecutar LIMPIAR sobre el diff actual |
| `@qa-revisar` | Solo tabla REVISAR (sin deploy) |
| `@qa-deploy-plan` | Generar DESPLEGAR sin ejecutar comandos |
| `@qa-registrar` | Generar/actualizar docs/changes |

Cursor debe reconocer estos prefijos si las reglas `.mdc` están instaladas.

---

## 5. Control y monitorización (responsabilidad humana)

```text
Cursor implementa → Dev revisa diff → Dev ejecuta REVISAR → Dev aprueba deploy
                                                      ↓
                              Deploy manual QA → Smoke → Ticket actualizado
```

| Artefacto | Quién | Dónde |
|-----------|-------|-------|
| Código | Dev + Cursor | rama `feature/*` |
| Revisión | Dev | PR GitHub |
| Deploy QA | Dev | CLI local o workflow manual |
| Evidencia | Dev | `docs/changes/`, ticket |
| Monitor | Dev | qa.doeventsapp.com + CloudWatch |

**Cursor no sustituye** la aprobación del PR ni el click de deploy.

---

## 6. Integración con envConfig

Antes de un prompt largo, el dev puede pegar contexto generado:

```powershell
. ..\envConfig\load-env-config.ps1
$q = Get-EnvConfig envRelease
@{
  web = $q.web.baseUrl
  api = $q.api.baseUrl
  region = $q.aws.region
  build = $q.build.command
} | ConvertTo-Json
```

Pegar el JSON en `CONTEXTO` ayuda a Cursor a no confundir DEV vs QA.

---

## 7. Diferencia con pipeline DEV (DoEventsCICD)

| | DEV (CICD) | QA (este doc) |
|---|------------|---------------|
| Trigger | GitHub Actions / Lovable | Desarrollador |
| Región | sa-east-1 | us-east-2 |
| Build | `build:devaws` | `build:qa` |
| Reglas | `Reglas/` pipeline | Prompt estándar + `.cursor/rules/` |
| Deploy | Automático feature/* | Manual post-revisión |

No mezclar prompts DEV (empalme Lovable) con prompts QA (features en develop).
