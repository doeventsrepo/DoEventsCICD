#!/usr/bin/env bash
# DSF Gate G3 — Anti-mocks en runtime WEB (excluye lovable/ como referencia de diseño)
set -euo pipefail

WEB_DIR="${1:-.}"
SHELL_SRC="${WEB_DIR}/packages/shell/src"
SHARED_SRC="${WEB_DIR}/packages/shared/src"

PATTERNS='mockEvents|mockUsers|mockTickets|mockOrders|mockReservations|mockData|hardcodedEvents|hardcodedUsers|sampleData|dummyData|fakeData|placeholderEvents'

scan_dir() {
  local dir="$1"
  local label="$2"
  local exclude="$3"
  if [ ! -d "$dir" ]; then
    echo "SKIP: sin $label"
    return 0
  fi
  local hits
  hits=$(grep -RInE "$PATTERNS" "$dir" 2>/dev/null \
    | grep -vE '\.test\.|__tests__|/test/|/lovable/|mockServiceWorker|msw' \
    | grep -vE "$exclude" || true)
  if [ -n "$hits" ]; then
    echo "ERROR: mocks o datos hardcodeados en $label:" >&2
    echo "$hits" >&2
    return 1
  fi
  echo "OK: $label sin mocks prohibidos"
}

fail=0
scan_dir "$SHELL_SRC" "shell/src (excepto lovable/)" "lovable" || fail=1
scan_dir "${SHELL_SRC}/lovable-bridge" "lovable-bridge/" "" || fail=1
scan_dir "$SHARED_SRC/api" "shared/api/" "" || fail=1

# Prohibir import de valores mock; permitir import type (solo tipos, sin runtime)
if [ -d "$PAGES" ]; then
  value_import_hits=$(grep -RInE "import\s+[^t].*mock|import\s+\{[^}]*\}\s+from\s+['\"].*mock|from\s+['\"]@lovable/data/mock" "$PAGES" 2>/dev/null \
    | grep -vE '\.test\.|__tests__|import\s+type\s' || true)
  if [ -n "$value_import_hits" ]; then
    echo "ERROR: imports de valores mock en pages/:" >&2
    echo "$value_import_hits" >&2
    fail=1
  else
    type_only=$(grep -RIn "import type.*mock" "$PAGES" 2>/dev/null | grep -vE '\.test\.|__tests__' || true)
    if [ -n "$type_only" ]; then
      echo "AVISO: import type desde mock (permitido, sin runtime):" >&2
      echo "$type_only" | head -5 >&2
    fi
    echo "OK: pages/ sin imports de valores mock"
  fi
fi

exit $fail
