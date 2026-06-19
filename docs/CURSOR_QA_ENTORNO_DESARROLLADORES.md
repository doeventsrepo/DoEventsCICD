# Cursor — entorno QA manual (DoEventsWEB + DoEventsBack)

Guía para que cada desarrollador configure **Cursor IDE** y trabaje ajustes en **QA** de forma **manual**, controlada y trazable.

**QA no usa pipeline automático.** DEV (sa-east-1) es automático vía DoEventsCICD; QA (us-east-2) lo ejecuta el desarrollador tras revisión.

**Relacionados:** [Prompt estándar QA](./PROMPT_ESTANDAR_DESARROLLO_QA.md) · [Runbook deploy QA](./runbook-deploy-qa.md) · [Manual configuración](./MANUAL_CONFIGURACION.md)

---

## 1. Mapa de entornos

| Entorno | Config | Región | Web | API | Deploy |
|---------|--------|--------|-----|-----|--------|
| DEV | `envConfig/envDevelop` | sa-east-1 | dev.doeventsapp.com | api-dev | Automático (CICD) |
| **QA** | **`envConfig/envRelease`** | **us-east-2** | **qa.doeventsapp.com** | **api-qa** | **Manual** |
| PROD | `envConfig/envMain` | us-east-1 | doeventsapp.com | api | Manual + aprobación |

Carga rápida en PowerShell (desde raíz del monorepo):

```powershell
. .\envConfig\load-env-config.ps1
$qa = Get-EnvConfig envRelease
$qa.web.baseUrl          # https://qa.doeventsapp.com
$qa.api.baseUrl          # https://api-qa.doeventsapp.com
$qa.aws.region           # us-east-2
$qa.aws.lambdaPrefix     # qa
$qa.build.command        # npm run build:qa
```

---

## 2. Estructura del monorepo (dónde abrir Cursor)

Recomendación: abrir la **carpeta raíz** `AplicacionWEB/` en Cursor para ver WEB, Back y CICD juntos.

```text
AplicacionWEB/
├── envConfig/
│   └── envRelease/          ← Verdad QA (URLs, build, AWS)
├── DoEventsWEB/             ← Frontend (rama develop para QA)
├── DoEventsBack/            ← Lambdas serverless (stage qa)
├── DoEventsCICD/            ← Reglas, docs, workflows manuales QA
└── discover-joyful-feed/    ← Solo referencia diseño (no deploy QA directo)
```

---

## 3. Configuración inicial de Cursor (una vez por máquina)

### 3.1 Reglas del proyecto (`.cursor/rules/`)

Copiar las plantillas de DoEventsCICD a cada repo donde trabajes:

| Origen | Destino |
|--------|---------|
| `DoEventsCICD/templates/cursor-rules/qa-doevents-web.mdc` | `DoEventsWEB/.cursor/rules/qa-doevents-web.mdc` |
| `DoEventsCICD/templates/cursor-rules/qa-doevents-back.mdc` | `DoEventsBack/.cursor/rules/qa-doevents-back.mdc` |

En Cursor: **Settings → Rules** debe mostrar reglas activas al abrir esos repos.

### 3.2 Variables de entorno local (sin commitear secretos)

**DoEventsWEB** — crear `.env.qa.local` (gitignored) a partir de:

```bash
# DoEventsWEB/.env.qa.local (NO commitear)
VITE_DOEVENTS_ENV=qa
VITE_GOOGLE_MAPS_API_KEY=<tu-clave-maps-qa>
```

Build local QA:

```powershell
cd DoEventsWEB
$env:VITE_DOEVENTS_ENV = "qa"
npm run build:qa
```

**DoEventsBack** — perfil AWS ya configurado por el equipo:

```powershell
$env:AWS_REGION = "us-east-2"
$env:AWS_PROFILE = "default"   # o el perfil que usen para QA
aws sts get-caller-identity    # verificar cuenta 519010577666
```

### 3.3 Rama de trabajo

| Repo | Rama integración QA | Rama de feature (tu trabajo) |
|------|---------------------|------------------------------|
| DoEventsWEB | `develop` | `feature/<tu-inicial>/<ticket>-descripcion` |
| DoEventsBack | `develop` | `feature/<tu-inicial>/<ticket>-descripcion` |

**Nunca** desplegar QA desde `main` sin proceso acordado. **No** usar ramas del pipeline DEV (`feature/cicd/dev-automation`) para deploy QA salvo acuerdo explícito del líder técnico.

---

## 4. Qué debe “saber” Cursor en QA

Al iniciar un chat en Cursor, el agente debe asumir:

1. **Entorno objetivo:** QA — `us-east-2`, sufijo `-qa`, prefijo lambda `qa-`.
2. **Frontend:** `npm run build:qa`, dominio `qa.doeventsapp.com`, config en `config/environments/index.ts` (`qa`).
3. **Backend:** `serverless.qa.yml`, `--stage qa --region us-east-2`, tablas DynamoDB `*-qa`.
4. **Prohibido:** mocks en runtime, secretos en commits, deploy a PROD, push force a `develop`/`main`.
5. **Obligatorio:** limpieza de código, auto-revisión, registro en `docs/changes/` antes de deploy.

Referencias de reglas CICD (solo lectura para el dev):

- `DoEventsCICD/Reglas/operativas/reglamento-cursor-api.md`
- `DoEventsCICD/docs/PROMPT_ESTANDAR_DESARROLLO_QA.md`

---

## 5. Flujo de trabajo recomendado

```text
1. Crear rama feature/* desde develop
2. Prompt estándar → IMPLEMENTAR (Cursor)
3. Prompt → LIMPIAR + REVISAR (Cursor)
4. Desarrollador: prueba local + diff en Git
5. PR → develop (revisión humana)
6. Tras merge: deploy manual QA (comandos abajo)
7. Verificación en https://qa.doeventsapp.com
8. Registrar en docs/changes/ o ticket
```

---

## 6. Deploy manual QA (después de revisión)

### Frontend

```powershell
cd DoEventsWEB
git checkout develop
git pull
npm ci
npm run build:qa
npm run deploy:qa
# o script: infrastructure/aws/deploy-qa.ps1
```

Workflow GitHub (alternativa): DoEventsCICD → **Deploy WEB QA** (`workflow_dispatch`).

### Backend (lambda concreta)

```powershell
cd DoEventsBack/aws-lambda-<servicio>
npm ci
npm run deploy:qa
# equivalente: npx serverless deploy --config serverless.qa.yml --stage qa --region us-east-2
```

Solo desplegar las lambdas que **cambió tu feature**; no hacer deploy masivo sin necesidad.

---

## 7. Checklist antes de cada deploy QA

El desarrollador confirma (Cursor puede ayudar a generar el checklist cumplido):

- [ ] Rama correcta y PR revisado/aprobado
- [ ] `npm run build:qa` OK (WEB) o `serverless package` OK (Back)
- [ ] Sin `.env`, tokens ni claves en el diff
- [ ] Sin mocks nuevos en `packages/shell/src/pages/`
- [ ] Cambios Back documentados si afectan API (`DoEventsWEB/docs/changes/`)
- [ ] AWS region `us-east-2` verificada
- [ ] Smoke test post-deploy: login, flujo tocado, consola sin errores críticos

---

## 8. Monitorización post-deploy

| Qué verificar | Cómo |
|---------------|------|
| Web QA | https://qa.doeventsapp.com |
| API | https://api-qa.doeventsapp.com/health o endpoint del feature |
| CloudFront | Invalidación si el deploy WEB no refresca (script deploy) |
| Lambdas | AWS Console → us-east-2 → Functions `qa-*` |
| Logs | CloudWatch `/aws/lambda/qa-<servicio>` |

Registrar resultado en el ticket (OK / rollback / hotfix).

---

## 9. Mensaje inicial sugerido para Cursor (copiar al abrir sesión QA)

```markdown
Modo: QA manual DoEvents.
Entorno: envRelease — us-east-2, qa.doeventsapp.com, api-qa.doeventsapp.com.
Repos: DoEventsWEB + DoEventsBack en rama feature actual.
Reglas: DoEventsCICD/templates/cursor-rules/qa-doevents-*.mdc y PROMPT_ESTANDAR_DESARROLLO_QA.md.
No desplegar sin fase REVISAR completada. No commitear secretos.
```

---

## 10. Lo que Cursor NO debe hacer en QA

- Desplegar automáticamente al terminar un prompt
- Modificar `main`, pipelines DEV, o `DoEventsCICD` sin pedido explícito
- Copiar código literal de Lovable/discover-joyful-feed sin empalme
- Introducir datos mock en producción/QA runtime
- Cambiar IAM, Cognito prod, o tablas DynamoDB fuera del scope del ticket

---

## 11. Soporte

- Dudas de infra QA: `DoEventsCICD/docs/runbook-deploy-qa.md`
- Config entorno: `envConfig/envRelease/environment.json`
- Conflictos DEV vs QA: DEV es sa-east-1 automático; QA siempre us-east-2 manual
