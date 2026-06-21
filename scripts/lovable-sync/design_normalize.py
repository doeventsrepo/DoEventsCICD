"""Normalización de fuentes para comparar empalme Lovable ↔ WEB (no copy-paste literal)."""
from __future__ import annotations

import re
from pathlib import Path

MOCK_CONST = re.compile(
    r"^\s*(?:const|let)\s+(?:MOCK_|mock|sample|fake|dummy|hardcoded)",
    re.I,
)
MOCK_MARKERS = re.compile(
    r"mock(?:Data|Users|Events|Tickets|Orders|Access)?|sampleData|hardcodedEvents|fakeData",
    re.I,
)
IMPORT_FROM = re.compile(r"from\s+['\"]([^'\"]+)['\"]")
RE_EXPORT_ONLY = re.compile(r"^export\s+")
PATH_ALIASES = (
    (re.compile(r"@/components/"), "__UI__/"),
    (re.compile(r"@lovable/components/"), "__UI__/"),
    (re.compile(r"@/lib/"), "__LIB__/"),
    (re.compile(r"@lovable/lib/"), "__LIB__/"),
    (re.compile(r"@/hooks/"), "__HOOK__/"),
    (re.compile(r"@lovable/hooks/"), "__HOOK__/"),
    (re.compile(r"@/contexts/"), "__CTX__/"),
    (re.compile(r"@lovable/contexts/"), "__CTX__/"),
    (re.compile(r"@doevents/shared"), "__SHARED__"),
    (re.compile(r"sonner"), "__TOAST__"),
)


def strip_mock_blocks(text: str) -> str:
    """Elimina bloques const MOCK_* y arrays de datos de prueba en Lovable."""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if MOCK_CONST.search(line) or (
            MOCK_MARKERS.search(line) and ("=[" in line.replace(" ", "") or "= [" in line)
        ):
            depth = 0
            started = False
            start = i
            while i < len(lines) and (i - start) < 10_000:
                chunk = lines[i]
                if "[" in chunk or "{" in chunk:
                    started = True
                depth += chunk.count("[") - chunk.count("]")
                depth += chunk.count("{") - chunk.count("}")
                i += 1
                if started and depth <= 0 and (";" in chunk or "}," in chunk or "];" in chunk):
                    break
            continue
        if re.search(r"@/assets/avatars/", line):
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def canonicalize_paths(text: str) -> str:
    for pattern, repl in PATH_ALIASES:
        text = pattern.sub(repl, text)
    text = re.sub(r"from\s+['\"]\.\/[^'\"]+['\"]", "from '__REL__'", text)
    text = re.sub(r"from\s+['\"]\.\.\/[^'\"]+['\"]", "from '__REL__'", text)
    return text


def normalize_source(text: str) -> str:
    if MOCK_CONST.search(text):
        text = strip_mock_blocks(text)
    text = canonicalize_paths(text)
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            continue
        if s.startswith("import "):
            continue
        if s.startswith("export type ") and " from " in s:
            continue
        if s.startswith("export ") and " from " in s and "{" not in s.split(" from ")[0]:
            continue
        lines.append(s)
    return "\n".join(lines)


def is_reexport_barrel(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    if not lines or len(lines) > 25:
        return False
    export_lines = [ln for ln in lines if RE_EXPORT_ONLY.match(ln)]
    return len(export_lines) == len(lines)


def _resolve_import(web_root: Path, from_rel: str, spec: str) -> Path | None:
    base = (web_root / from_rel).parent
    if spec.startswith("."):
        target = (base / spec).resolve()
        for ext in ("", ".tsx", ".ts", ".jsx", ".js"):
            candidate = Path(str(target) + ext) if ext else target
            if candidate.is_file():
                return candidate
        if target.is_file():
            return target
    return None


def resolve_web_comparison_content(web_root: Path, web_rel: str, text: str, *, depth: int = 0) -> str:
    """Sigue re-exports y concatena implementación real para comparación justa."""
    if depth > 4 or not is_reexport_barrel(text):
        return text
    seen: set[str] = set()
    chunks: list[str] = [text]
    for match in IMPORT_FROM.finditer(text):
        spec = match.group(1)
        if not spec.startswith("."):
            continue
        target = _resolve_import(web_root, web_rel, spec)
        if not target:
            continue
        key = str(target)
        if key in seen:
            continue
        seen.add(key)
        try:
            sub = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = target.relative_to(web_root).as_posix()
        chunks.append(resolve_web_comparison_content(web_root, rel, sub, depth=depth + 1))
    return "\n".join(chunks)


def file_similarity(lovable_text: str, web_text: str) -> float:
    import difflib

    a = normalize_source(lovable_text)
    b = normalize_source(web_text)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    # Archivos UI muy grandes (p. ej. SeatingMapEditor) — muestra representativa
    max_chars = 32_000
    if len(a) > max_chars:
        a = a[:max_chars]
    if len(b) > max_chars:
        b = b[:max_chars]
    return difflib.SequenceMatcher(None, a, b).quick_ratio()
