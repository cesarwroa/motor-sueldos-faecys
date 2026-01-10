from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from escalas import load_meta, find_row

APP_ROOT = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(APP_ROOT, "public")

app = FastAPI(title="Motor Sueldos FAECYS", version="1.1.0")

# CORS (para servir index.html y que pueda llamar al backend sin problemas)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir frontend
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}

@app.get("/meta")
def meta() -> Dict[str, Any]:
    return load_meta()

def _to_float(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(".", "").replace(",", ".")
        return float(s) if s else 0.0
    except Exception:
        return 0.0

def _pct(base: float, p: float) -> float:
    return round(base * (p / 100.0), 2)

def _add(items: List[Dict[str, Any]], concepto: str, base: float, rem: float = 0.0, nr: float = 0.0, ded: float = 0.0) -> None:
    items.append({
        "concepto": concepto,
        "base": round(base, 2),
        "remunerativo": round(rem, 2),
        "no_remunerativo": round(nr, 2),
        "deduccion": round(ded, 2),
    })

@app.post("/calcular")
async def calcular(payload: Request) -> Dict[str, Any]:
    data = await payload.json()

    rama = (data.get("rama") or "").strip()
    agrup = (data.get("agrup") or "").strip()
    cat = (data.get("cat") or "").strip()
    mes = (data.get("mes") or "").strip()

    if not (rama and cat and mes):
        raise HTTPException(status_code=400, detail="Faltan datos: rama / cat / mes")

    # Datos principales desde Maestro
    row = find_row(rama=rama, agrup=agrup, cat=cat, mes=mes)
    if not row:
        raise HTTPException(status_code=404, detail="No hay fila en Maestro para esa selección")

    basico = _to_float(row.get("basico"))
    nr_var = _to_float(row.get("no_rem_1"))
    nr_sf = _to_float(row.get("no_rem_2"))

    # Inputs del formulario (si no vienen, default)
    anios = int(_to_float(data.get("anios", 0)))
    zona_pct = _to_float(data.get("zona_pct", 0))  # 0 / 10 / 20 / ...
    osecac_mode = (data.get("osecac") or "SI").upper()  # SI / NO

    afiliado_pct = _to_float(data.get("afiliado_selector", 0))  # ej: 2 = 2%
    afiliado_fijo = _to_float(data.get("afiliado_fijo", 0))

    # --- Cálculos (mínimo estable: básico, presentismo, antigüedad, NR, deducciones) ---
    items: List[Dict[str, Any]] = []

    # Zona desfavorable (si se usa, suma sobre REM)
    zona = _pct(basico, zona_pct) if zona_pct else 0.0

    # Antigüedad (regla general 1% por año, no acumulativa) - si en el futuro querés: Agua Potable 2% acumulativo
    antig_rem = _pct(basico + zona, float(anios)) if anios > 0 else 0.0

    # Presentismo 8,33% (1/12) sobre REM (básico + zona + antig)
    base_pres_rem = basico + zona + antig_rem
    pres_rem = round(base_pres_rem / 12.0, 2) if base_pres_rem else 0.0

    # NR total y sus “espejos” de presentismo / antigüedad sobre NR
    nr_total = nr_var + nr_sf
    antig_nr = _pct(nr_total, float(anios)) if (anios > 0 and nr_total) else 0.0
    pres_nr = round((nr_total + antig_nr) / 12.0, 2) if nr_total else 0.0

    # --- HABERES ---
    _add(items, "Básico (REM)", base=basico, rem=basico)
    if zona:
        _add(items, f"Zona desfavorable ({zona_pct:.0f}%)", base=basico, rem=zona)
    if antig_rem:
        _add(items, f"Antigüedad ({anios} años)", base=basico + zona, rem=antig_rem)
    if pres_rem:
        _add(items, "Presentismo (8,33%)", base=base_pres_rem, rem=pres_rem)

    if nr_var:
        _add(items, "No Rem (variable)", base=nr_var, nr=nr_var)
    if nr_sf:
        _add(items, "Suma Fija (NR)", base=nr_sf, nr=nr_sf)
    if antig_nr:
        _add(items, f"Antigüedad (NR) ({anios} años)", base=nr_total, nr=antig_nr)
    if pres_nr:
        _add(items, "Presentismo (NR) (8,33%)", base=(nr_total + antig_nr), nr=pres_nr)

    # Totales haberes
    tot_rem = sum(_to_float(it["remunerativo"]) for it in items)
    tot_nr = sum(_to_float(it["no_remunerativo"]) for it in items)

    # --- DEDUCCIONES (según reglas del sistema) ---
    base_jub_pami = tot_rem
    jub = _pct(base_jub_pami, 11.0)
    pami = _pct(base_jub_pami, 3.0)

    # Obra social: siempre 3% sobre REM.
    # Si OSECAC=SI, además 3% sobre NR y $100 fijo.
    os_base = tot_rem
    os_nr_base = tot_nr if osecac_mode == "SI" else 0.0
    os_aporte = _pct(os_base, 3.0) + (_pct(os_nr_base, 3.0) if os_nr_base else 0.0)
    os_fijo = 100.0 if osecac_mode == "SI" else 0.0

    # FAECYS 0,5% sobre (REM + todo lo NR)
    base_solidarios = tot_rem + tot_nr
    faecys = _pct(base_solidarios, 0.5)

    # Sindicato: % configurable sobre (REM + NR) + fijo (si se usa)
    sindicato = _pct(base_solidarios, afiliado_pct) if afiliado_pct else 0.0
    sindicato_fijo = afiliado_fijo

    # Agregar filas de descuentos
    _add(items, "Jubilación 11%", base=base_jub_pami, ded=jub)
    _add(items, "PAMI 3%", base=base_jub_pami, ded=pami)
    _add(items, "Obra Social 3%", base=(os_base + os_nr_base), ded=os_aporte)
    if os_fijo:
        _add(items, "OSECAC ($100)", base=100.0, ded=os_fijo)
    _add(items, "FAECYS 0,5%", base=base_solidarios, ded=faecys)
    if sindicato or sindicato_fijo:
        _add(items, "Sindicato", base=base_solidarios, ded=(sindicato + sindicato_fijo))

    tot_ded = sum(_to_float(it["deduccion"]) for it in items)
    neto = round((tot_rem + tot_nr - tot_ded), 2)

    return {
        "ok": True,
        "auto": {
            "basico": round(basico, 2),
            "nr_var": round(nr_var, 2),
            "nr_sf": round(nr_sf, 2),
            "nr_total": round(nr_total, 2),
        },
        "items": items,
        "totales": {
            "remunerativo": round(tot_rem, 2),
            "no_remunerativo": round(tot_nr, 2),
            "deducciones": round(tot_ded, 2),
            "neto": neto,
        },
    }
