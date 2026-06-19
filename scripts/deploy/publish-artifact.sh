#!/usr/bin/env bash
# DSF — Publica artefacto de build inmutable para promoción futura (QA deshabilitado por config)
set -euo pipefail

WEB_DIR="${1:-.}"
ARTIFACT_NAME="${2:-build-artifact}"
BUCKET="${DSF_ARTIFACT_BUCKET:-doevents-cicd-artifacts-dev}"
REGION="${DSF_ARTIFACT_REGION:-sa-east-1}"
SHA="${3:-unknown}"
RUN_ID="${4:-local}"

DIST_TAR="/tmp/${ARTIFACT_NAME}-${SHA}.tar.gz"
mkdir -p "$(dirname "$DIST_TAR")"

echo "Empaquetando build..."
tar -czf "$DIST_TAR" \
  -C "$WEB_DIR" \
  packages/shell/dist \
  packages/mfe-auth/dist \
  build-manifest.json 2>/dev/null || \
tar -czf "$DIST_TAR" \
  -C "$WEB_DIR" \
  packages/shell/dist \
  packages/mfe-auth/dist

MANIFEST=$(jq -n \
  --arg sha "$SHA" \
  --arg runId "$RUN_ID" \
  --arg created "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg tar "$(basename "$DIST_TAR")" \
  '{lovableSha:$sha, runId:$runId, createdAt:$created, artifact:$tar, qaPromotionEnabled:false}')

echo "$MANIFEST" > "/tmp/${ARTIFACT_NAME}-${SHA}.json"

if command -v aws >/dev/null 2>&1 && [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
  aws s3 mb "s3://${BUCKET}" --region "$REGION" 2>/dev/null || true
  aws s3 cp "$DIST_TAR" "s3://${BUCKET}/builds/${SHA}/${ARTIFACT_NAME}.tar.gz" --region "$REGION"
  aws s3 cp "/tmp/${ARTIFACT_NAME}-${SHA}.json" "s3://${BUCKET}/builds/${SHA}/manifest.json" --region "$REGION"
  echo "Artefacto publicado: s3://${BUCKET}/builds/${SHA}/"
else
  echo "AVISO: AWS no configurado — artefacto local: $DIST_TAR"
fi

echo "s3://${BUCKET}/builds/${SHA}/${ARTIFACT_NAME}.tar.gz"
