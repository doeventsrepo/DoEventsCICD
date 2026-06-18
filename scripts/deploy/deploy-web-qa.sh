#!/usr/bin/env bash
# Deploy DoEventsWEB QA — equivalente Linux a deploy-qa.ps1
set -euo pipefail

REGION="${AWS_REGION:-us-east-2}"
BUCKET="${S3_BUCKET:-doevents-web-qa}"
CF="${CLOUDFRONT_DISTRIBUTION_ID:-E3UV9NHXADGSAJ}"
ROOT="${WEB_ROOT:-.}"

cd "$ROOT"
echo "=== Build QA ==="
npm ci
npm run build:qa

echo "=== S3 sync shell ==="
aws s3 sync packages/shell/dist/ "s3://${BUCKET}/" --delete --region "$REGION" \
  --cache-control "public, max-age=0, must-revalidate"

echo "=== S3 sync mfe-auth ==="
aws s3 sync packages/mfe-auth/dist/ "s3://${BUCKET}/mfe-auth/" --delete --region "$REGION" \
  --cache-control "public, max-age=0, must-revalidate" \
  --exclude "index.html" --exclude ".dev-server/*" --exclude "@mf-types/*"
aws s3 cp packages/mfe-auth/dist/index.html "s3://${BUCKET}/mfe-auth/index.html" --region "$REGION"

aws s3 cp packages/shell/dist/index.html "s3://${BUCKET}/index.html" --region "$REGION" \
  --content-type "text/html" --cache-control "public, max-age=0, must-revalidate"

if [ -n "$CF" ]; then
  aws cloudfront create-invalidation --distribution-id "$CF" --paths "/*"
fi

echo "Deploy OK: https://qa.doeventsapp.com"
