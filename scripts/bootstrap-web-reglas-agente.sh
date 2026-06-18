#!/usr/bin/env bash
# Bootstrap ReglasAgente en DoEventsWEB desde plantillas DoEventsCICD
set -euo pipefail

CICD_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
WEB_DIR="${1:-../DoEventsWEB}"

mkdir -p "$WEB_DIR/ReglasAgente" "$WEB_DIR/docs/changes"

for f in reglas-front.md cambios-lovable.json decision-log.md impacto-backend.md; do
  dest="$WEB_DIR/ReglasAgente/$f"
  if [ ! -f "$dest" ]; then
    cp "$CICD_DIR/templates/ReglasAgente/$f" "$dest"
    echo "Creado $dest"
  fi
done

if [ ! -f "$WEB_DIR/.lovable-port-map.json" ]; then
  cp "$CICD_DIR/templates/.lovable-port-map.json" "$WEB_DIR/.lovable-port-map.json"
  echo "Creado .lovable-port-map.json"
fi

if [ ! -f "$WEB_DIR/docs/changes/lovable-backend-impact.md" ]; then
  cp "$WEB_DIR/ReglasAgente/impacto-backend.md" "$WEB_DIR/docs/changes/lovable-backend-impact.md"
fi

echo "Bootstrap OK en $WEB_DIR"
