#!/usr/bin/env bash
# DSF Azure deploy provider (stub — configurar storageAccount y cdnEndpoint en cicd.config.json)
set -euo pipefail

WEB_DIR="${1:-.}"
ENV="${2:-dev}"

echo "DSF Azure provider — stub"
echo "WEB_DIR=$WEB_DIR ENV=$ENV"

if ! command -v az >/dev/null 2>&1; then
  echo "ERROR: Azure CLI (az) no instalado" >&2
  exit 1
fi

STORAGE="${AZURE_STORAGE_ACCOUNT:-CONFIGURE_AZURE_STORAGE}"
CONTAINER="${AZURE_CONTAINER:-\$web}"

cd "$WEB_DIR"
npm ci
npm run build:devaws

bash "$(dirname "$0")/../../lovable-sync/validate-no-mocks.sh" .

echo "Subiendo a Azure Storage: $STORAGE / $CONTAINER"
az storage blob upload-batch \
  --account-name "$STORAGE" \
  --destination "$CONTAINER" \
  --source packages/shell/dist \
  --overwrite 2>/dev/null || {
  echo "AVISO: Configure AZURE_STORAGE_ACCOUNT y credenciales az login" >&2
  exit 1
}

echo "DSF Azure deploy DEV OK (stub completado)"
