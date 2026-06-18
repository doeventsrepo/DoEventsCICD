#!/usr/bin/env bash
# Valida que no haya mocks nuevos en runtime (REGLAS §7)
set -euo pipefail

WEB_DIR="${1:-.}"
PAGES="${WEB_DIR}/packages/shell/src/pages"

if [ ! -d "$PAGES" ]; then
  echo "Sin directorio pages/ — skip"
  exit 0
fi

PATTERNS='mockEvents|mockUsers|mockTickets|mockOrders|mockReservations|hardcodedEvents|hardcodedUsers|sampleData|dummyData'

if grep -RInE "$PATTERNS" "$PAGES" 2>/dev/null | grep -vE '\.test\.|__tests__|/test/'; then
  echo "ERROR: mocks o datos hardcodeados detectados en pages/" >&2
  exit 1
fi

echo "OK: sin mocks prohibidos en pages/"
exit 0
