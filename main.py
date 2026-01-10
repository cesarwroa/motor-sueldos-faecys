
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from escalas import get_meta, get_payload, find_row, DEFAULT_MAESTRO_PATH

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
MAESTRO_PATH = str(DEFAULT_MAESTRO_PATH)

app = FastAPI(title="ComercioOnline - Motor de Sueldos (server-side)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    # Sirve el HTML desde el backend (Render)
    index_path = PUBLIC_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse({"ok": False, "error": "Falta public/index.html"}, status_code=500)
    return FileResponse(index_path)


@app.get("/meta")
def meta():
    return get_meta(MAESTRO_PATH)


@app.get("/payload")
def payload(
    rama: str = Query(...),
    agrup: str = Query("—"),
    categoria: str = Query("—"),
    mes: str = Query(...),
):
    return get_payload(rama=rama, agrup=agrup, categoria=categoria, mes=mes, maestro_path=MAESTRO_PATH)


def _round2(x: float) -> float:
    return float(f"{x:.2f}")


def _pct(x: float, p: float) -> float:
    return x * p


def _antig_factor(rama: str, years: float) -> float:
    rama_u = (rama or "").upper()
    if rama_u == "AGUA POTABLE":
        # 2% acumulativo por año
        y = max(0.0, float(years or 0.0))
        return (1.02 ** y) - 1.0
    # 1% por año (no acumulativo)
    return max(0.0, float(years or 0.0)) * 0.01


@app.get("/calcular")
def calcular(
    rama: str = Query(...),
    agrup: str = Query("—"),
    categoria: str = Query("—"),
    mes: str = Query(...),
    jornada: float = Query(48.0),
    anios_antig: float = Query(0.0),
    osecac: bool = Query(True),
    afiliado: bool = Query(False),
    sind_pct: float = Query(2.0),
    titulo_pct: float = Query(0.0),
):
    """
    Devuelve el recibo armado en JSON (para que el HTML NO haga cálculos).

    Implementación mínima (pero coherente):
    - Básico (REM) (prorratea por jornada vs 48)
    - Antigüedad (REM) (1% anual o 2% acumulativo Agua Potable)
    - Presentismo (REM) (8,33% = /12)
    - No Rem (variable) + Suma fija (NR) (prorratea por jornada)
    - Antigüedad NR + Presentismo NR (sobre NR total)
    - Descuentos: Jubilación 11% (solo REM), PAMI 3% (solo REM),
      Obra Social 3% (REM y, si OSECAC, también NR) + $100 (si OSECAC),
      FAECYS 0,5% (REM+NR), Sindicato 2% (REM+NR si afiliado)
    """
    row = find_row(rama=rama, agrup=agrup, categoria=categoria, mes=mes, maestro_path=MAESTRO_PATH)
    if not row:
        return JSONResponse({"ok": False, "error": "No se encontró esa combinación en el maestro"}, status_code=404)

    # Prorrateo por jornada (base 48)
    j = float(jornada or 48.0)
    pr = j / 48.0 if j > 0 else 1.0

    basico = float(row.basico or 0.0) * pr
    nr_var = float(row.no_rem or 0.0) * pr
    nr_sf = float(row.suma_fija or 0.0) * pr
    nr_total = nr_var + nr_sf

    # Adicional por Título (solo si el front lo envía; turismo suele usar 2.5% o 5%)
    tit_p = max(0.0, float(titulo_pct or 0.0)) / 100.0
    titulo_rem = basico * tit_p
    titulo_nr = nr_total * tit_p

    fact_antig = _antig_factor(row.rama, anios_antig)
    antig_rem = basico * fact_antig
    base_pres_rem = basico + antig_rem
    pres_rem = base_pres_rem / 12.0

    antig_nr = nr_total * fact_antig
    base_pres_nr = nr_total + antig_nr
    pres_nr = base_pres_nr / 12.0

    # Totales por columnas
    total_rem = basico + antig_rem + pres_rem + titulo_rem
    total_nr = nr_total + antig_nr + pres_nr + titulo_nr

    # Descuentos
    jub = _pct(total_rem, 0.11)
    pami = _pct(total_rem, 0.03)

    # Obra social: si no es OSECAC, no aplica $100 ni base NR
    if osecac:
        base_os = total_rem + total_nr
        os_3 = _pct(base_os, 0.03)
        os_100 = 100.0
        obra_social = os_3 + os_100
    else:
        base_os = total_rem
        obra_social = _pct(base_os, 0.03)

    base_sind = total_rem + total_nr
    faecys = _pct(base_sind, 0.005)
    sind_p = max(0.0, float(sind_pct or 0.0)) / 100.0
    sindicato = _pct(base_sind, sind_p) if afiliado and sind_p>0 else 0.0

    total_desc = jub + pami + obra_social + faecys + sindicato
    neto = total_rem + total_nr - total_desc

    items: List[Dict[str, Any]] = []

    def add(concepto: str, base: float = 0.0, rem: float = 0.0, nr: float = 0.0, ded: float = 0.0):
        items.append(
            {
                "concepto": concepto,
                "base": _round2(base),
                "rem": _round2(rem),
                "nr": _round2(nr),
                "ded": _round2(ded),
            }
        )

    add("Básico (REM)", base=basico, rem=basico)
    if antig_rem:
        add("Antigüedad (REM)", base=basico, rem=antig_rem)
    if pres_rem:
        add("Presentismo (REM)", base=base_pres_rem, rem=pres_rem)
    if titulo_rem:
        add("Adicional por Título (REM)", base=basico, rem=titulo_rem)

    if nr_var:
        add("No Rem (variable)", base=nr_var, nr=nr_var)
    if nr_sf:
        add("Suma Fija (NR)", base=nr_sf, nr=nr_sf)
    if titulo_nr:
        add("Adicional por Título (NR)", base=nr_total, nr=titulo_nr)
    if antig_nr:
        add("Antigüedad (NR)", base=nr_total, nr=antig_nr)
    if pres_nr:
        add("Presentismo (NR)", base=base_pres_nr, nr=pres_nr)

    # Descuentos
    add("Jubilación 11%", base=total_rem, ded=jub)
    add("PAMI 3%", base=total_rem, ded=pami)
    if osecac:
        add("Obra Social 3% + $100 (OSECAC)", base=base_os, ded=obra_social)
    else:
        add("Obra Social 3%", base=base_os, ded=obra_social)
    add("FAECYS 0,5%", base=base_sind, ded=faecys)
    if afiliado:
        add("SINDICATO 2%", base=base_sind, ded=sindicato)

    return {
        "ok": True,
        "rama": row.rama,
        "agrup": row.agrup,
        "categoria": row.categoria,
        "mes": row.mes,
        "jornada": j,
        "anios_antig": float(anios_antig or 0.0),
        "items": items,
        "totales": {
            "rem": _round2(total_rem),
            "nr": _round2(total_nr),
            "ded": _round2(total_desc),
            "neto": _round2(neto),
        },
    }
