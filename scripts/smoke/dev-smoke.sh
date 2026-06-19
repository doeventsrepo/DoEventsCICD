#!/usr/bin/env bash
# DSF Gate G6 — Smoke tests contra API DEV real (sin mocks)
set -euo pipefail

API_BASE="${API_BASE:-https://api-dev.doeventsapp.com}"
WEB_BASE="${WEB_BASE:-https://dev.doeventsapp.com}"
OUT_JSON="${1:-/tmp/dsf-smoke-result.json}"

passed=0
total=0
tests_json="["

record() {
  local name="$1"
  local ok="$2"
  local detail="$3"
  total=$((total + 1))
  if [ "$ok" = "true" ]; then passed=$((passed + 1)); fi
  if [ "$total" -gt 1 ]; then tests_json+=","; fi
  tests_json+=$(jq -n --arg n "$name" --argjson ok "$([ "$ok" = true ] && echo true || echo false)" --arg d "$detail" '{name:$n, ok:$ok, detail:$d}')
}

http_ok() {
  local url="$1"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 25 "$url" || echo "000")
  [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]
}

http_json_ok() {
  local url="$1"
  local body
  body=$(curl -sS --max-time 25 "$url" 2>/dev/null || echo "")
  [ -n "$body" ] && echo "$body" | jq -e . >/dev/null 2>&1
}

echo "=== DSF Smoke DEV ==="
echo "API: $API_BASE"
echo "WEB: $WEB_BASE"

if http_ok "$WEB_BASE/"; then
  record "web_root" true "HTTP 200/redirect"
else
  record "web_root" false "No responde $WEB_BASE"
fi

if http_ok "$WEB_BASE/mfe-auth/index.html"; then
  record "mfe_auth" true "mfe-auth accesible"
else
  record "mfe_auth" false "mfe-auth no accesible"
fi

token_code=$(curl -sS -o /tmp/dsf-token.json -w "%{http_code}" --max-time 25 \
  -X POST "$API_BASE/auth/generateToken" -H "Content-Type: application/json" -d '{}' || echo "000")
if [ "$token_code" = "200" ] && jq -e '.token // .accessToken' /tmp/dsf-token.json >/dev/null 2>&1; then
  record "auth_generate_token" true "Token obtenido"
  TOKEN=$(jq -r '.token // .accessToken' /tmp/dsf-token.json)
else
  record "auth_generate_token" false "HTTP $token_code"
  TOKEN=""
fi

auth_header() {
  if [ -n "$TOKEN" ]; then echo "Authorization: $TOKEN"; fi
}

events_code=$(curl -sS -o /tmp/dsf-events.json -w "%{http_code}" --max-time 25 \
  -H "$(auth_header)" -H "Content-Type: application/json" \
  "$API_BASE/events-feed/eventsFeed" 2>/dev/null || echo "000")
if [ "$events_code" = "200" ]; then
  record "events_feed" true "Feed responde"
else
  record "events_feed" false "HTTP $events_code"
fi

types_code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 25 \
  "$API_BASE/event-types/EventTypes" 2>/dev/null || echo "000")
if [ "$types_code" = "200" ]; then
  record "event_types" true "Tipos de evento OK"
else
  record "event_types" false "HTTP $types_code"
fi

images_code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 25 \
  -X POST "$API_BASE/images/createUploadUrls" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"dsf-smoke","files":[{"fileName":"t.jpg","contentType":"image/jpeg"}]}' 2>/dev/null || echo "000")
if [ "$images_code" = "200" ]; then
  record "images_create_upload_urls" true "Presigned URLs OK"
else
  record "images_create_upload_urls" false "HTTP $images_code"
fi

tests_json+="]"
result=$(jq -n --argjson passed "$passed" --argjson total "$total" --argjson tests "$tests_json" \
  '{passed:$passed, total:$total, ok:($passed == $total), tests:$tests}')
echo "$result" | tee "$OUT_JSON"
echo "Smoke: $passed/$total"

if [ "$passed" -eq "$total" ]; then
  exit 0
fi
exit 1
