# Runbook — Deploy QA

## Frontend (DoEventsWEB)

### Manual (desarrollador)

```powershell
cd DoEventsWEB
npm run deploy:qa
```

### GitHub Actions

DoEventsCICD → **Deploy WEB QA** (requiere secrets AWS + environment `qa`)

### CodeBuild

Usar `aws/codebuild/web-qa.yml` conectado a repo DoEventsWEB rama `develop`.

**Destino:** https://qa.doeventsapp.com — S3 `doevents-web-qa`, CloudFront `E3UV9NHXADGSAJ`

## Backend (DoEventsBack)

- Workflow: **Deploy Backend QA** (login lambda)
- Buildspec: `aws/codebuild/back-qa.yml`

## IA (DoEventsIA)

- Workflow: **Deploy IA QA**
- Buildspec: `aws/codebuild/ia-qa.yml`
- Requiere `CURSOR_API_KEY` en entorno Lambda (no en repo)

## Cadena post-sync

En **Lovable Sync to WEB**, activar input `deploy_qa_after=true` solo tras validar adaptación del agente.

**Producción:** siempre aprobación manual (`main` → prod). Ver `Automatizacion.html` §11.
