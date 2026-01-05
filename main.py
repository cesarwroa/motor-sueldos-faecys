from __future__ import annotations

from typing import Any, Dict, List, Tuple
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Compat: tu repo venía usando models.py
try:
    from models import DatosEmpleado  # noqa: F401
except Exception:
    DatosEmpleado = None  # type: ignore

from escalas import get_payload  # payload completo (escala + adicionales, etc.)

app = FastAPI(title="Motor Sueldos FAECYS", version="0.2.0")

# CORS: permitir consumo desde file:// (origin "null") y desde cualquier dominio
# Nota: allow_origins=["*"] sirve para la mayoría de casos. También habilitamos headers/métodos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- META / PAYLOAD ----------------

def _uniq_sorted(values: List[str]) -> List[str]:
    out = sorted({(v or "").strip() for v in values if (v or "").strip()})
    return out

def _build_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = payload.get("escala", []) or []
    ramas = _uniq_sorted([r.get("Rama","") for r in rows])

    agrup_by_rama: Dict[str, List[str]] = {}
    cats_by_rama_agrup: Dict[str, Dict[str, List[str]]] = {}
    meses_by_key: Dict[Tuple[str,str,str], List[str]] = {}

    for r in rows:
        rama = (r.get("Rama") or "").strip()
        agr = (r.get("Agrup") or "").strip()
        cat = (r.get("Categoria") or "").strip()
        mes = (r.get("Mes") or "").strip()

        if not rama or not cat or not mes:
            continue

        agrup_by_rama.setdefault(rama, [])
        if agr and agr not in agrup_by_rama[rama]:
            agrup_by_rama[rama].append(agr)

        cats_by_rama_agrup.setdefault(rama, {})
        cats_by_rama_agrup[rama].setdefault(agr or "—", [])
        if cat not in cats_by_rama_agrup[rama][agr or "—"]:
            cats_by_rama_agrup[rama][agr or "—"].append(cat)

        key = (rama, agr or "—", cat)
        meses_by_key.setdefault(key, [])
        if mes not in meses_by_key[key]:
            meses_by_key[key].append(mes)

    # ordenar listas
    for rama in agrup_by_rama:
        agrup_by_rama[rama] = sorted(agrup_by_rama[rama])
    for rama in cats_by_rama_agrup:
        for agr in cats_by_rama_agrup[rama]:
            cats_by_rama_agrup[rama][agr] = sorted(cats_by_rama_agrup[rama][agr])

    meses_all = _uniq_sorted([r.get("Mes","") for r in rows])

    return {
        "ramas": ramas,
        "agrupamientos": agrup_by_rama,
        "categorias": cats_by_rama_agrup,
        "meses": meses_all,
        # Opcional: meses específicos por (rama,agrup,categoria)
        "meses_por_clave": {f"{k[0]}||{k[1]}||{k[2]}": sorted(v) for k,v in meses_by_key.items()},
        "version_payload": payload.get("version") or None,
    }

@app.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "service": "motor-sueldos-faecys", "endpoints": ["/meta","/api/meta","/payload","/api/payload","/health"]}

@app.head("/")
def head_root():
    # Render hace HEAD /
    return

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}

@app.get("/payload")
def payload() -> Dict[str, Any]:
    return get_payload()

@app.get("/api/payload")
def api_payload() -> Dict[str, Any]:
    return get_payload()

@app.get("/meta")
def meta() -> Dict[str, Any]:
    return _build_meta(get_payload())

@app.get("/api/meta")
def api_meta() -> Dict[str, Any]:
    return _build_meta(get_payload())
