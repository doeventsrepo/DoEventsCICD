#!/usr/bin/env bash
# Orquestador Cursor CLI headless (Automatizacion.html §15)
# Requiere: cursor-agent en PATH, CURSOR_API_KEY, CICD_DIR
set -euo pipefail

MODE="${MODE:-frontend-only}"
BRANCH_NAME="${BRANCH_NAME:-feature/ai/apply-lovable-rules-${GITHUB_RUN_ID:-local}}"
CICD_DIR="${CICD_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
WEB_DIR="${WEB_DIR:-./DoEventsWEB}"

if [ -z "${CURSOR_API_KEY:-}" ]; then
  echo "ERROR: CURSOR_API_KEY requerido" >&2
  exit 1
fi

PROMPT_FILE="${CICD_DIR}/prompts/lovable-fullstack-agent.md"
RULES_FILE="${CICD_DIR}/prompts/REGLAS_CURSOR_API_LOVABLE_DOEVENTSWEB.md"

if ! command -v cursor-agent >/dev/null 2>&1; then
  echo "cursor-agent no instalado; usando run-port-agent-api.py (Cloud Agents API)"
  export LOVABLE_DIR="${LOVABLE_DIR:-.}"
  export WEB_DIR
  export CICD_DIR
  exec python3 "${CICD_DIR}/scripts/lovable-sync/run-port-agent-api.py"
fi

git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"

cursor-agent --print --force --model auto "
Eres un agente de desarrollo para DoEvents.
Modo: ${MODE}.
Lee: ${PROMPT_FILE} y ${RULES_FILE} y ReglasAgente/reglas-front.md en ${WEB_DIR}.
Aplica reglasActuacion sin copiar Lovable literalmente.
No mocks. No producción. Documenta en ReglasAgente/.
"

cd "$WEB_DIR" 2>/dev/null || true
npm install
npm run lint 2>/dev/null || true
npm run build:qa

bash "${CICD_DIR}/scripts/lovable-sync/validate-no-mocks.sh" "$WEB_DIR"

git add -A
git commit -m "feat(ai): apply Lovable reglasActuacion changes" || echo "Sin cambios"
git push origin "$BRANCH_NAME" || true

if command -v gh >/dev/null 2>&1; then
  gh pr create --base develop --head "$BRANCH_NAME" \
    --title "feat(ai): apply Lovable reglasActuacion changes" \
    --body-file "${WEB_DIR}/ReglasAgente/decision-log.md" 2>/dev/null || true
fi
