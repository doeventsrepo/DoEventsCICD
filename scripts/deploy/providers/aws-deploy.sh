#!/usr/bin/env bash
# DSF AWS deploy provider
set -euo pipefail

WEB_DIR="${1:-.}"
ENV="${2:-dev}"
REGION="${AWS_REGION:-sa-east-1}"
BUCKET="${S3_BUCKET_DEV:-doevents-web-dev}"
CF="${CLOUDFRONT_DISTRIBUTION_ID_DEV:-}"

if [ "$ENV" != "dev" ]; then
  echo "ERROR: AWS provider en CICD solo automatiza DEV. QA requiere dsf-promote-qa (inhabilitado)." >&2
  exit 1
fi

cd "$WEB_DIR"
npm ci
npm run build:devaws

bash "$(dirname "$0")/../../lovable-sync/validate-no-mocks.sh" .

aws s3 sync packages/shell/dist/ "s3://${BUCKET}/" --delete --region "$REGION" \
  --cache-control "public, max-age=0, must-revalidate"
aws s3 sync packages/mfe-auth/dist/ "s3://${BUCKET}/mfe-auth/" --delete --region "$REGION" \
  --cache-control "public, max-age=0, must-revalidate" \
  --exclude "index.html" --exclude ".dev-server/*" --exclude "@mf-types/*"
aws s3 cp packages/mfe-auth/dist/index.html "s3://${BUCKET}/mfe-auth/index.html" --region "$REGION"
aws s3 cp packages/shell/dist/index.html "s3://${BUCKET}/index.html" --region "$REGION" \
  --content-type "text/html" --cache-control "public, max-age=0, must-revalidate"

if [ -n "$CF" ]; then
  aws cloudfront create-invalidation --distribution-id "$CF" --paths "/*"
fi

echo "DSF AWS deploy DEV OK: https://dev.doeventsapp.com"
