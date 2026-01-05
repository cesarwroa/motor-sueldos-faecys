
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import re
import unicodedata

from models import DatosLiquidacion, ResultadoCalculo, ItemRecibo
from escalas import get_payload

app = FastAPI(title="Motor Sueldos FAECYS", version="api-only-v3")

# CORS (Render / GitHub Pages / local file)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PAYLOAD = get_payload()

def _norm(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper()
    s = re.sub(r"\s+", " ", s)
    return s

def r2(x: float) -> float:
    return round(float(x or 0.0) + 1e-9, 2)

def _safe_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, str):
            v = v.replace(".", "").replace(",", ".")  # tolerate AR formatting
        return float(v)
    except Exception:
        return 0.0

def _build_scale_index() -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
    idx: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for row in _PAYLOAD.get("escala", []):
        key = (_norm(row.get("Rama","")),
               _norm(row.get("Agrup","")),
               _norm(row.get("Categoria","")),
               _norm(row.get("Mes","")))
        idx[key] = row
    return idx

_SCALE_IDX = _build_scale_index()

def _meta_from_scales() -> Dict[str, Any]:
    ramas: Dict[str, Any] = {}
    for row in _PAYLOAD.get("escala", []):
        r = row.get("Rama","")
        a = row.get("Agrup","")
        c = row.get("Categoria","")
        m = row.get("Mes","")
        if not (r and a and c and m):
            continue
        ramas.setdefault(r, {"agrups": {}})
        ramas[r]["agrups"].setdefault(a, {"cats": set(), "meses": {}})
        ramas[r]["agrups"][a]["cats"].add(c)
        ramas[r]["agrups"][a]["meses"].setdefault(c, set()).add(m)

    # convert sets to sorted lists
    for r in list(ramas.keys()):
        for a in list(ramas[r]["agrups"].keys()):
            ramas[r]["agrups"][a]["cats"] = sorted(list(ramas[r]["agrups"][a]["cats"]))
            meses = ramas[r]["agrups"][a]["meses"]
            for c in list(meses.keys()):
                meses[c] = sorted(list(meses[c]))
    return {"ramas": ramas}

_FUN_CONCEPT = {
    "CADAVER": "Adicional General (todo el personal, incluidos choferes)",
    "RESTO": "Adicional Personal no incluido en inciso 1",
    "CHOFER": "Adicional Chofer/Furgonero (vehículos)",
    "INDUMENT": "Adicional por Indumentaria",
}

def _funebres_val(mes: str, key: str) -> float:
    target = _FUN_CONCEPT.get(key, "")
    if not target:
        return 0.0
    for row in _PAYLOAD.get("adicionales", []):
        if row.get("Rama") != "Fúnebres":
            continue
        if _norm(row.get("Mes","")) != _norm(mes):
            continue
        if row.get("Concepto") == target:
            return _safe_float(row.get("Valor"))
    return 0.0

_AGUA_FACT = {"A": 1.00, "B": 1.07, "C": 1.1449, "D": 1.2250}

@app.get("/meta")
def meta() -> Dict[str, Any]:
    # Solo nombres; sin montos
    return _meta_from_scales()

@app.post("/calcular", response_model=ResultadoCalculo)
def calcular_sueldo(d: DatosLiquidacion) -> ResultadoCalculo:
    # --- lookup escala ---
    key = (_norm(d.rama), _norm(d.agrup), _norm(d.categoria), _norm(d.mes))
    row = _SCALE_IDX.get(key)

    # tolerancias típicas: agrup vacío / "—"
    if row is None:
        key2 = (_norm(d.rama), _norm(d.agrup or "—"), _norm(d.categoria), _norm(d.mes))
        row = _SCALE_IDX.get(key2)
    if row is None:
        key3 = (_norm(d.rama), _norm(""), _norm(d.categoria), _norm(d.mes))
        row = _SCALE_IDX.get(key3)

    basico_escala = _safe_float(row.get("Basico")) if row else 0.0
    nr_var_escala = _safe_float(row.get("No Remunerativo")) if row else 0.0
    nr_sf_escala = _safe_float(row.get("Suma Fija")) if row else 0.0
    # Algunos maestros usan "SUMA_FIJA"
    if nr_sf_escala == 0.0 and row:
        nr_sf_escala = _safe_float(row.get("SUMA_FIJA"))

    # --- Agua Potable: factor conexiones sobre Básico + Suma Fija ---
    agua_fact = 1.0
    if _norm(d.rama).startswith("AGUA"):
        sel = (d.aguaConex or "A").strip().upper()
        agua_fact = _AGUA_FACT.get(sel, 1.0)
        basico_escala *= agua_fact
        nr_sf_escala *= agua_fact

    # --- Base "auto" (no depende del input del front) ---
    basico_base = basico_escala if basico_escala else _safe_float(d.basico)
    nr_var_base = nr_var_escala
    nr_sf_base = nr_sf_escala
    nr_total_base = nr_var_base + nr_sf_base

    # --- Cálculos principales (resumen; se mantiene lógica simple y estable) ---
    # Presentismo: 8.33% del básico (y del NR total, según tu criterio NR integra)
    pres_rem = (basico_base / 12.0) if d.presentismo else 0.0
    pres_nr = (nr_total_base / 12.0) if d.presentismo else 0.0

    # Antigüedad: 1% por año (no acumulativo); Agua Potable 2% acumulativo (según criterio guardado)
    if _norm(d.rama).startswith("AGUA"):
        ant_pct = 0.02 * float(max(d.anios, 0))
        ant_rem = basico_base * ant_pct
        ant_nr = nr_total_base * ant_pct
    else:
        ant_pct = 0.01 * float(max(d.anios, 0))
        ant_rem = basico_base * ant_pct
        ant_nr = nr_total_base * ant_pct

    # Zona: el front manda % (0, 10, 20...)
    zona_pct = float(max(d.zona, 0)) / 100.0
    zona_rem = basico_base * zona_pct
    zona_nr = nr_total_base * zona_pct

    # Feriados / Horas extras / Nocturnas: en esta versión API-only se modelan simple (sin tablas de valor hora),
    # priorizando no romper el front. Si necesitás, lo extendemos con el mismo criterio del HTML original.
    fer_no_rem = 0.0
    fer_no_nr = 0.0
    fer_si_rem = 0.0
    fer_si_nr = 0.0
    hex50_rem = 0.0
    hex50_nr = 0.0
    hex100_rem = 0.0
    hex100_nr = 0.0
    hs_noct_rem = 0.0
    hs_noct_nr = 0.0

    # Ausencias injustificadas: día = (Básico + Antigüedad + Zona) / 30 (criterio César)
    desc_ausencia = 0.0
    if d.coAus and d.coAus > 0:
        base_dia = (basico_base + ant_rem + zona_rem) / 30.0
        desc_ausencia = base_dia * float(d.coAus)

    # --- Fúnebres: adicionales (según checks) ---
    fun_cad = _safe_float(_funebres_val(d.mes, "CADAVER")) if d.funAdic1 else 0.0
    fun_res = _safe_float(_funebres_val(d.mes, "RESTO")) if d.funAdic2 else 0.0
    fun_cho = _safe_float(_funebres_val(d.mes, "CHOFER")) if d.funAdic3 else 0.0
    fun_ind = _safe_float(_funebres_val(d.mes, "INDUMENT")) if d.funAdic4 else 0.0

    # Regla del HTML: si chofer marcado, suma Chofer; y si no marcó CADAVER, suma también General
    if d.funAdic3 and not d.funAdic1:
        fun_cad = _safe_float(_funebres_val(d.mes, "CADAVER"))

    fun_total = fun_cad + fun_res + fun_cho + fun_ind

    # --- Totales imponibles ---
    total_rem = basico_base + ant_rem + zona_rem + pres_rem + fer_no_rem + fer_si_rem + hex50_rem + hex100_rem + hs_noct_rem + fun_total
    total_nr = nr_total_base + ant_nr + zona_nr + pres_nr + fer_no_nr + fer_si_nr + hex50_nr + hex100_nr + hs_noct_nr

    # Bases para aportes: criterio César (NR integra FAECYS/Sindicato/OSECAC; Jubilación y PAMI solo Rem)
    base_rem = total_rem
    base_sindical = total_rem + total_nr

    jubilacion = 0.0 if d.coJub else r2(base_rem * 0.11)
    pami = 0.0 if d.coJub else r2(base_rem * 0.03)

    faecys = r2(base_sindical * 0.005)
    sindicato = r2(base_sindical * 0.02) if not d.afiliado else 0.0
    sind_af = r2(base_sindical * 0.02) if d.afiliado else 0.0

    obra_social = r2(base_sindical * 0.03) if (d.osecac.lower() == "si") else 0.0
    osecac_fijo = 100.0 if (d.osecac.lower() == "si") else 0.0

    total_deducciones = r2(jubilacion + pami + faecys + sindicato + sind_af + obra_social + osecac_fijo + desc_ausencia)
    neto = r2((total_rem + total_nr) - total_deducciones)

    items: List[ItemRecibo] = []

    def add(concepto: str, rem: float = 0.0, nr: float = 0.0, ded: float = 0.0, base: Optional[float] = None):
        items.append(ItemRecibo(concepto=concepto, remunerativo=r2(rem), no_remunerativo=r2(nr), deduccion=r2(ded), base=(r2(base) if base is not None else None)))

    add("Básico", rem=basico_base, base=basico_base)
    if ant_rem or ant_nr:
        add("Antigüedad", rem=ant_rem, nr=ant_nr, base=float(d.anios))
    if zona_rem or zona_nr:
        add("Zona Desfavorable", rem=zona_rem, nr=zona_nr, base=float(d.zona))
    if nr_total_base:
        add("No Remunerativo (Acuerdo)", nr=nr_total_base)
    if pres_rem or pres_nr:
        add("Presentismo (8.33%)", rem=pres_rem, nr=pres_nr)

    if fun_total:
        add("Adicionales Fúnebres", rem=fun_total)

    if desc_ausencia:
        add(f"Ausencia Injustificada ({d.coAus} días)", ded=desc_ausencia)

    add("Jubilación 11%", ded=jubilacion, base=base_rem)
    if pami:
        add("Ley 19.032 (PAMI) 3%", ded=pami, base=base_rem)
    add("FAECYS 0,5%", ded=faecys, base=base_sindical)
    if sindicato:
        add("Sindicato 2%", ded=sindicato, base=base_sindical)
    if sind_af:
        add("Sindicato Afiliado 2%", ded=sind_af, base=base_sindical)
    if obra_social:
        add("Obra Social 3%", ded=obra_social, base=base_sindical)
    if osecac_fijo:
        add("OSECAC $100", ded=osecac_fijo)

    # Totales
    return ResultadoCalculo(
        inputs_normalizados=d,
        auto={
            "basico": r2(basico_base),
            "nrVar": r2(nr_var_base),
            "nrSF": r2(nr_sf_base),
            "nrTotal": r2(nr_total_base),
        },
        totales={
            "total_rem": r2(total_rem),
            "total_nr": r2(total_nr),
            "total_deducciones": r2(total_deducciones),
            "neto": r2(neto),
        },
        items=items
    )
