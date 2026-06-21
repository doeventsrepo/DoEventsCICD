#!/usr/bin/env python3
"""
Bootstrap DSF v1.0 — genera component-index.yml y port-map.yml desde src/ + .lovable-port-map.json.
Ejecutar una vez y re-ejecutar cuando crezca src/ (CI prepare o manual).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from port_map_utils import is_excluded, load_port_map, load_port_map_data, map_lovable_to_web, mapping_for

DELEGATED = {
    "src/pages/Login.tsx", "src/pages/SignUp.tsx",
    "src/pages/ForgotPassword.tsx", "src/pages/ResetPassword.tsx",
}
CURSOR_PATHS = ("MapView", "GlobalSearchView", "AdminPanel", "KycCertification", "SeatingMap")
BACKEND_PATHS = ("banking", "Banking", "checkout", "Checkout", "Kyc", "kyc", "PaymentGateway", "Stripe", "PayPal")


def load_rules_by_source(lovable_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    rules_dir = lovable_root / "reglasActuacion"
    if not rules_dir.is_dir():
        return out
    for yml in rules_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        rid = data.get("id")
        if not rid:
            continue
        for src in data.get("source") or []:
            s = str(src).replace("\\", "/").lstrip("./")
            out[s] = rid
    return out


def infer_domain(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "src":
        if parts[1] == "pages":
            return "pages"
        if parts[1] in ("components", "hooks", "contexts"):
            return parts[2] if len(parts) > 2 else parts[1]
    return "general"


def infer_tier(rel: str, compare_mode: str) -> str:
    if rel in DELEGATED or compare_mode == "delegated":
        return "delegated"
    if any(p in rel for p in CURSOR_PATHS):
        return "cursor"
    if any(p in rel for p in BACKEND_PATHS):
        return "backend"
    if rel.startswith("src/contexts/") or rel.startswith("src/hooks/"):
        return "cursor"
    return "python"


def infer_layers(rel: str, tier: str) -> list[str]:
    if tier == "backend":
        return ["backend", "seguridad"]
    if tier == "cursor":
        return ["logica"]
    if "View.tsx" in rel or "Page.tsx" in rel:
        return ["diseno", "responsive"]
    return ["diseno"]


def infer_architecture_layer(rel: str) -> str:
    if rel.startswith("src/pages/"):
        return "page"
    if rel.startswith("src/hooks/"):
        return "hook"
    if rel.startswith("src/contexts/"):
        return "context"
    if rel.startswith("src/components/"):
        return "component"
    return "component"


def scan_ui_files(lovable_root: Path) -> list[str]:
    files: list[str] = []
    for ext in ("*.tsx", "*.ts", "*.css"):
        for p in (lovable_root / "src").rglob(ext):
            rel = p.relative_to(lovable_root).as_posix()
            if rel.endswith(".d.ts"):
                continue
            files.append(rel)
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap DSF component-index + port-map")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    port_map_path = web / ".lovable-port-map.json"
    if not port_map_path.is_file():
        print(f"ERROR: falta {port_map_path}", file=sys.stderr)
        return 1

    port_data = load_port_map_data(port_map_path)
    mapping = load_port_map(port_map_path)
    rules_by_source = load_rules_by_source(lovable)

    components: list[dict] = []
    port_entries: list[dict] = []

    for rel in scan_ui_files(lovable):
        if is_excluded(rel, port_data):
            continue
        web_path = map_lovable_to_web(rel, mapping)
        if not web_path:
            continue
        meta = mapping_for(rel, mapping) or {}
        compare_mode = meta.get("compareMode", "")
        tier = infer_tier(rel, compare_mode)
        domain = infer_domain(rel)
        rule_id = rules_by_source.get(rel, "")
        layers = infer_layers(rel, tier)
        status = "delegated" if tier == "delegated" else "mapped"

        components.append({
            "lovablePath": rel,
            "ruleId": rule_id,
            "webPath": web_path,
            "domain": domain,
            "architectureLayer": infer_architecture_layer(rel),
            "agentTier": tier,
            "complexity": "complex" if tier in ("cursor", "backend") else "simple",
            "riskLevel": "blocked" if tier == "delegated" else ("high" if tier == "backend" else "low"),
            "layers": layers,
            "owner": "mfe-auth" if tier == "delegated" else "frontend",
            "backendRequired": tier == "backend",
            "ownership": {
                "functionalOwner": "product",
                "frontendOwner": "doevents-web",
                "backendOwner": "doevents-back",
                "syncOwner": "dsf",
            },
            "lastChangeSummary": "",
        })

        port_entries.append({
            "lovablePath": rel,
            "webPath": web_path,
            "ruleId": rule_id,
            "domain": domain,
            "status": status,
            "duplicateCheck": "passed",
            "existingEquivalent": "",
        })

    idx_doc = {
        "id": "empalme.component-index",
        "version": "1.0.0",
        "domain": "empalme",
        "description": "Índice DSF v1.0 — generado/actualizado por bootstrap-dsf-index.py",
        "components": components,
    }
    pm_doc = {
        "id": "empalme.port-map",
        "version": "1.0.0",
        "domain": "empalme",
        "description": "Port-map Lovable → DoEventsWEB (DSF v1.0)",
        "portMap": port_entries,
    }

    idx_path = lovable / "reglasEmpalme" / "component-index.yml"
    pm_path = lovable / "reglasEmpalme" / "port-map.yml"

    if args.dry_run:
        print(f"Generaría {len(components)} entradas en component-index.yml")
        print(f"Generaría {len(port_entries)} entradas en port-map.yml")
        unmapped_rules = sum(1 for c in components if not c["ruleId"])
        print(f"Sin ruleId: {unmapped_rules}")
        return 0

    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(yaml.dump(idx_doc, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")
    pm_path.write_text(yaml.dump(pm_doc, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")
    print(f"OK: {idx_path} ({len(components)} componentes)")
    print(f"OK: {pm_path} ({len(port_entries)} rutas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
