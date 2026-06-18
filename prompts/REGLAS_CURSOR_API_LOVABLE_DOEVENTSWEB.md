# REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md

# Reglas Operativas para Agente Cursor API Key
## Integración Lovable → DoEventsWEB → DoEventsBack

## 1. Propósito

Este documento define las reglas obligatorias que debe obedecer el agente ejecutado mediante Cursor API Key, Cursor CLI Headless, Cursor Cloud Agents o cualquier automatización equivalente.

El agente tiene como objetivo analizar cambios provenientes de Lovable, interpretarlos y acoplarlos correctamente en DoEventsWEB sin introducir mocks, sin copiar código literalmente, sin romper la integración con backend y sin alterar reglas críticas existentes.

Lovable es una fuente de diseño, UX y reglas de actuación frontend.

DoEventsWEB es la aplicación frontend real.

DoEventsBack es la fuente de verdad de reglas de negocio, persistencia, APIs, tickets, órdenes, usuarios, reservas, pagos y datos reales.

---

# 2. Ubicación recomendada

En el repositorio DoEventsWEB debe existir la siguiente estructura:

```text
DoEventsWEB/
├── .cursor/
│   └── rules/
│       └── lovable-doevents-agent.mdc
├── reglasActuacion/
│   ├── REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md
│   ├── cambios-lovable.json
│   ├── reglas-front.md
│   ├── impacto-backend.md
│   └── decision-log.md
```

En el repositorio DoEventsBack debe existir:

```text
DoEventsBack/
└── docs/
    └── changes/
        └── lovable-backend-impact.md
```

---

# 3. Regla maestra del agente

El agente NO debe implementar literalmente lo que genera Lovable.

El agente debe seguir este flujo obligatorio:

```text
1. Leer cambios provenientes de Lovable.
2. Leer reglasActuacion.
3. Comparar Lovable contra DoEventsWEB.
4. Identificar intención del cambio.
5. Clasificar el cambio.
6. Determinar si es visual, funcional, backend requerido o riesgoso.
7. Reutilizar arquitectura existente.
8. Implementar únicamente lo necesario.
9. No introducir mocks.
10. Validar build/test.
11. Documentar evidencia.
12. Crear commits separados.
```

Regla de oro:

```text
Lovable diseña.
DoEventsWEB interpreta.
DoEventsBack gobierna.
El agente adapta.
El agente nunca copia.
```

---

# 4. Configuración segura de Cursor API Key

## 4.1 Prohibición de exponer API Key

La Cursor API Key nunca debe escribirse en:

```text
.env versionado
README.md
archivos .md
código fuente
scripts públicos
logs
commits
GitHub Actions output
```

Debe almacenarse únicamente como secreto seguro:

```text
GitHub Actions Secrets: CURSOR_API_KEY
AWS Secrets Manager: /doevents/cursor/api-key
```

## 4.2 Uso recomendado en GitHub Actions

```yaml
name: Lovable to DoEventsWEB Agent

on:
  pull_request:
    branches:
      - develop
    paths:
      - 'lovable/**'
      - 'reglasActuacion/**'
      - '.cursor/rules/**'

jobs:
  cursor-agent:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - name: Checkout DoEventsWEB
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run Cursor Agent
        env:
          CURSOR_API_KEY: ${{ secrets.CURSOR_API_KEY }}
        run: |
          cursor-agent --print --force \
            --model auto \
            --prompt-file reglasActuacion/prompt-agente-lovable.md
```

## 4.3 Política de permisos

El agente debe tener permisos mínimos.

Permitido:

```text
leer repositorio
modificar rama feature o rama temporal
crear commit
crear Pull Request
actualizar documentación en reglasActuacion
```

Prohibido:

```text
desplegar producción
modificar secretos
borrar ramas principales
hacer force push a develop/main
ejecutar migraciones productivas
crear credenciales
modificar IAM
modificar DNS
modificar certificados
```

---

# 5. Prompt obligatorio para Cursor API

El agente debe ser invocado con un prompt equivalente al siguiente:

```text
Eres el agente de integración Lovable → DoEventsWEB.

Tu misión es interpretar los cambios de diseño y reglas de actuación frontend provenientes de Lovable y adaptarlos al código real de DoEventsWEB.

No debes copiar código literalmente desde Lovable.
No debes introducir mocks.
No debes reemplazar servicios reales por datos hardcodeados.
No debes romper hooks, servicios, rutas, autenticación, permisos ni contratos con backend.

Antes de modificar código debes:
1. Leer reglasActuacion/REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md.
2. Leer reglasActuacion/cambios-lovable.json.
3. Leer reglasActuacion/reglas-front.md.
4. Leer reglasActuacion/impacto-backend.md.
5. Leer reglasActuacion/decision-log.md.
6. Analizar el diff proveniente de Lovable.
7. Clasificar cada cambio como VISUAL, FRONTEND_LOGIC, BACKEND_REQUIRED o RISKY.

Durante la implementación debes:
1. Reutilizar componentes existentes.
2. Reutilizar servicios existentes.
3. Reutilizar hooks existentes.
4. Mantener consumo real de APIs.
5. Mantener integración con DoEventsBack.
6. Mantener validaciones existentes.
7. Implementar nuevas reglas frontend solo cuando estén descritas en reglasActuacion.
8. Si detectas que falta soporte backend, documentarlo en impacto-backend.md y preparar cambio en DoEventsBack solo si el flujo lo permite.

Está prohibido:
1. Crear mockEvents, mockUsers, mockTickets, mockOrders o equivalentes.
2. Crear arrays hardcodeados para simular backend.
3. Crear endpoints falsos.
4. Comentar validaciones existentes para que compile.
5. Desactivar autenticación o permisos.
6. Cambiar lógica de pagos, reservas, tickets, QR u órdenes sin clasificar como RISKY.
7. Desplegar backend automáticamente.

Al finalizar debes actualizar:
1. reglasActuacion/cambios-lovable.json
2. reglasActuacion/reglas-front.md
3. reglasActuacion/impacto-backend.md
4. reglasActuacion/decision-log.md

Y debes generar un reporte final con:
1. Resumen del cambio detectado.
2. Tipo de cambio.
3. Archivos modificados en DoEventsWEB.
4. Archivos modificados en DoEventsBack, si aplica.
5. Evidencia de que no se usaron mocks.
6. Resultado de build/test.
7. Riesgos pendientes.

Si no puedes garantizar una implementación segura, debes detenerte, documentar el bloqueo y no modificar lógica crítica.
```

---

# 6. Clasificación obligatoria de cambios

Todo cambio debe clasificarse antes de modificar código.

## 6.1 VISUAL

Cambio únicamente de:

```text
layout
estilos
componentes visuales
responsive design
copy visual
orden de secciones
colores
tipografía
espaciado
```

Acción permitida:

```text
Modificar componentes visuales sin tocar servicios ni lógica de negocio.
```

## 6.2 FRONTEND_LOGIC

Cambio de:

```text
validaciones de campos
navegación
redirecciones
habilitar o deshabilitar botones
mensajes de error
estados de formulario
flujo de usuario
```

Acción permitida:

```text
Implementar regla en formularios, rutas, hooks o componentes existentes respetando backend.
```

## 6.3 BACKEND_REQUIRED

Cambio que requiere:

```text
nuevo campo persistente
nuevo endpoint
nuevo filtro backend
nueva consulta DynamoDB
nuevo estado de negocio
nueva regla de tickets
nueva regla de pagos
nueva regla de órdenes
nueva validación servidor
```

Acción permitida:

```text
Documentar impacto backend.
Implementar cambio backend solo si el flujo autorizado lo permite.
No desplegar automáticamente.
```

## 6.4 RISKY

Cambio que afecta:

```text
login
registro
usuarios
permisos
roles
pagos
checkout
órdenes
reservas
tickets
QR
favoritos
seguridad
```

Acción obligatoria:

```text
Detener despliegue automático.
Crear documentación de riesgo.
Requerir revisión humana antes de merge.
```

---

# 7. Reglas contra mocks

## 7.1 Prohibición absoluta

El agente no puede crear, copiar ni activar:

```text
mock
mocks
fake
faker
dummy
dummyData
sampleData
testData
hardcodedEvents
hardcodedUsers
hardcodedTickets
hardcodedOrders
mockEvents
mockTickets
mockOrders
mockReservations
```

## 7.2 Búsqueda obligatoria

Antes de finalizar debe ejecutar búsquedas equivalentes a:

```bash
grep -R "mock\|fake\|dummy\|sampleData\|testData\|hardcoded" src || true
```

## 7.3 Resultado esperado

Si se detecta mock nuevo, el agente debe:

```text
1. Revertir ese cambio.
2. Reemplazarlo por servicio real existente.
3. Si no existe servicio real, documentar brecha backend.
4. Bloquear el merge si no puede resolverlo.
```

---

# 8. Reglas de acoplamiento con DoEventsWEB

## 8.1 Reutilización primero

Antes de crear nuevo código, el agente debe buscar:

```text
componentes existentes
hooks existentes
servicios existentes
tipos existentes
rutas existentes
validadores existentes
contextos existentes
stores existentes
```

## 8.2 No duplicación

Está prohibido duplicar componentes o servicios si ya existe una implementación equivalente.

## 8.3 Mantener contratos API

El agente no puede cambiar nombres de campos, DTOs o respuestas esperadas sin validar DoEventsBack.

## 8.4 No romper rutas

El agente no puede cambiar rutas existentes sin registrar impacto.

---

# 9. Reglas para formularios

Toda regla de actuación de Lovable debe convertirse en regla real del formulario.

Ejemplos:

```text
fechaFin >= fechaInicio
precio >= 0
aforo > 0
cantidadTickets > 0
email válido
categoría obligatoria
ciudad obligatoria
usuario autenticado para comprar
```

El agente debe validar:

```text
validación frontend
mensaje de error
bloqueo de submit
manejo de error backend
redirección solo después de éxito real
```

---

# 10. Reglas para redirecciones

El agente no puede redirigir antes de confirmar persistencia real.

Incorrecto:

```text
click guardar → navigate inmediatamente
```

Correcto:

```text
click guardar → llamar API → respuesta exitosa → navigate
```

---

# 11. Reglas para backend

## 11.1 Cuándo tocar DoEventsBack

Solo si DoEventsWEB no puede cumplir la funcionalidad sin soporte backend.

Ejemplos:

```text
nuevo campo que debe persistirse
nuevo estado de ticket
nuevo filtro de eventos
nueva regla de reserva
nueva validación servidor
nuevo endpoint
```

## 11.2 Qué debe hacer el agente

```text
1. Documentar en impacto-backend.md.
2. Crear cambio en DoEventsBack en rama separada.
3. Versionar sin desplegar.
4. Crear registro técnico.
5. Dejar pendiente aprobación humana.
```

## 11.3 Qué no debe hacer

```text
desplegar backend automáticamente
modificar producción
ejecutar migraciones sin aprobación
modificar IAM
modificar secretos
```

---

# 12. Archivos obligatorios generados por ejecución

## 12.1 cambios-lovable.json

Formato obligatorio:

```json
{
  "executionId": "YYYYMMDD-HHMMSS",
  "fecha": "YYYY-MM-DD",
  "origen": "Lovable",
  "repositorio": "DoEventsWEB",
  "ramaOrigen": "feature/lovable-change",
  "ramaDestino": "develop",
  "resumenCambioDetectado": "",
  "tipoCambio": "VISUAL | FRONTEND_LOGIC | BACKEND_REQUIRED | RISKY",
  "modulosImpactados": [],
  "backendRequired": false,
  "riskLevel": "LOW | MEDIUM | HIGH | CRITICAL",
  "archivosLovableAnalizados": [],
  "archivosDoEventsWEBModificados": [],
  "archivosDoEventsBackModificados": [],
  "mocksDetectados": false,
  "buildStatus": "PENDING | SUCCESS | FAILED",
  "testStatus": "PENDING | SUCCESS | FAILED",
  "riesgosPendientes": [],
  "decision": "APPLIED | BLOCKED | PARTIAL | REQUIRES_REVIEW"
}
```

## 12.2 reglas-front.md

Formato obligatorio:

```md
# Reglas Frontend Detectadas

## Ejecución
- Fecha:
- Rama:
- Módulo:

## Reglas nuevas o modificadas

| Regla | Tipo | Implementada | Archivo | Observación |
|---|---|---|---|---|
| fechaFin >= fechaInicio | Validación | Sí | src/... | Regla aplicada al formulario real |

## Validaciones

- [ ] Validación frontend implementada
- [ ] Mensaje de error implementado
- [ ] Submit bloqueado si la regla falla
- [ ] Error backend manejado
- [ ] Redirección posterior al éxito real
```

## 12.3 impacto-backend.md

Formato obligatorio:

```md
# Impacto Backend

## Resumen

## ¿Requiere backend?
Sí / No

## Motivo

## Contrato actual encontrado

## Brecha detectada

## Acción realizada

## Archivos modificados en DoEventsBack

## Despliegue
NO DESPLEGADO

## Riesgos

## Pendientes
```

## 12.4 decision-log.md

Formato obligatorio:

```md
# Decision Log

## YYYY-MM-DD HH:mm:ss

### Cambio detectado

### Clasificación
VISUAL / FRONTEND_LOGIC / BACKEND_REQUIRED / RISKY

### Decisión
APPLIED / BLOCKED / PARTIAL / REQUIRES_REVIEW

### Justificación

### Archivos modificados

### Evidencia no mocks

### Resultado build/test

### Riesgos pendientes
```

---

# 13. Validaciones obligatorias de pipeline

El pipeline debe fallar si ocurre cualquiera de estos casos:

```text
se detectan mocks nuevos
se detectan endpoints inventados
fallan tests
falla build
se modifican archivos de secretos
se modifica autenticación sin clasificación RISKY
se modifica checkout/pagos/tickets/reservas sin revisión
se modifica backend y se intenta desplegar automáticamente
```

Comandos mínimos:

```bash
npm install
npm run lint
npm run build
npm test -- --watch=false
npm audit --audit-level=high
```

Búsqueda de mocks:

```bash
grep -R "mock\|fake\|dummy\|sampleData\|testData\|hardcoded" src || true
```

Búsqueda de secretos:

```bash
grep -R "AWS_SECRET\|AWS_ACCESS\|CURSOR_API_KEY\|PRIVATE_KEY\|TOKEN" . || true
```

---

# 14. Reporte final obligatorio del agente

Cada ejecución debe producir exactamente este reporte:

```md
# Reporte de Ejecución Agente Lovable → DoEventsWEB

## 1. Resumen del cambio detectado

## 2. Tipo de cambio
VISUAL / FRONTEND_LOGIC / BACKEND_REQUIRED / RISKY

## 3. Archivos modificados en DoEventsWEB

## 4. Archivos modificados en DoEventsBack

## 5. Evidencia de que no se usaron mocks

## 6. Resultado de build/test

## 7. Riesgos pendientes

## 8. Decisión final
APPLIED / BLOCKED / PARTIAL / REQUIRES_REVIEW
```

---

# 15. Regla final de bloqueo

Si el agente no puede determinar con seguridad si un cambio debe ir en frontend o backend, debe:

```text
1. No inventar solución.
2. No introducir mocks.
3. No copiar Lovable literalmente.
4. Documentar la duda.
5. Clasificar como REQUIRES_REVIEW.
6. Bloquear el merge automático.
```

---

# 16. Definición de éxito

Una ejecución es exitosa solo si:

```text
El cambio visual fue adaptado.
La lógica frontend fue alineada.
No se introdujeron mocks.
No se rompió backend.
No se inventaron endpoints.
No se desactivó seguridad.
Build pasó.
Tests pasaron.
Artefactos fueron actualizados.
Reporte fue generado.
```

---

# 17. Resumen ejecutivo

Este agente debe comportarse como un arquitecto de integración, no como un copiador de código.

Debe proteger DoEventsWEB, preservar DoEventsBack y convertir Lovable en una fuente controlada de diseño y reglas frontend.

