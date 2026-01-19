from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MAESTRO_JSON = DATA_DIR / "maestro.json"


def norm(x: Any) -> str:
    """Normalize strings for case/space-insensitive matching."""
    if x is None:
        return ""
    return " ".join(str(x).strip().upper().split())


def ym(x: Any) -> str:
    """Coerce a value into YYYY-MM string if possible."""
    if x is None:
        return ""
    s = str(x).strip()
    # Common formats already look like 2026-01
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return s[:7]


@lru_cache(maxsize=1)
def load_maestro() -> Dict[str, Any]:
    if not MAESTRO_JSON.exists():
        raise FileNotFoundError(f"Missing maestro.json at {MAESTRO_JSON}")
    return json.loads(MAESTRO_JSON.read_text(encoding="utf-8"))


def find_escala(rama: str, agrup: str, categoria: str, mes: str) -> Optional[Dict[str, Any]]:
    data = load_maestro()
    R = norm(rama)
    A = norm(agrup)
    C = norm(categoria)
    M = ym(mes)
    for r in data.get("escala", []):
        if norm(r.get("Rama")) == R and norm(r.get("Agrupamiento")) == A and norm(r.get("Categoria")) == C and ym(r.get("Mes")) == M:
            return r
    return None


def meta() -> Dict[str, Any]:
    """Return dropdown metadata: ramas->agrup->categorias and months."""
    data = load_maestro()
    tree: Dict[str, Dict[str, List[str]]] = {}
    meses: Dict[Tuple[str, str, str], List[str]] = {}

    for r in data.get("escala", []):
        rama = r.get("Rama")
        agrup = r.get("Agrupamiento")
        cat = r.get("Categoria")
        mes = ym(r.get("Mes"))

        tree.setdefault(rama, {}).setdefault(agrup, [])
        if cat not in tree[rama][agrup]:
            tree[rama][agrup].append(cat)

        key = (rama, agrup, cat)
        meses.setdefault(key, [])
        if mes and mes not in meses[key]:
            meses[key].append(mes)

    # sort categories and months
    for rama in tree:
        for agrup in tree[rama]:
            tree[rama][agrup].sort()

    for k in list(meses.keys()):
        meses[k].sort()

    # convert tuple keys to strings for JSON
    meses_out: Dict[str, List[str]] = {
        f"{k[0]}||{k[1]}||{k[2]}": v for k, v in meses.items()
    }

    return {"tree": tree, "months": meses_out}
