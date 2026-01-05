from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict, List, Optional

from models import DatosEmpleado
import escalas

app = FastAPI(title="Motor de Sueldos CCT 130/75")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _norm(s: str) -> str:
    return " ".join((s or "").strip().upper().split())

def r2(x: float) -> float:
    # redondeo a 2 decimales consistente
    try:
        return float(f"{float(x):.2f}")
    except Exception:
        return 0.0

def _get_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        return float(v)
    except Exception:
        return 0.0

def _is_call_center(rama: str) -> bool:
    return "CALL CENTER" in _norm(rama)

def _is_menores(categoria: str) -> bool:
    return "MENOR" in _norm(categoria)

def _jornada_prop(d: DatosEmpleado) -> float:
    """
    Regla del sistema (idéntica a tu HTML histórico):
    - Call Center: NO prorratea por hs (la escala ya viene por jornada en la categoría)
    - Menores: NO prorratea
    - Resto: prorratea hs/48
    """
    if _is_call_center(d.rama) or _is_menores(d.categoria):
        return 1.0
    hs = float(d.hs or 48)
    if hs <= 0:
        hs = 48.0
    return hs / 48.0

def _antig_tasa(d: DatosEmpleado) -> float:
    # Agua Potable: 2% acumulativo por año
    if _norm(d.rama) == "AGUA POTABLE":
        anios = int(d.anios or 0)
        if anios <= 0:
            return 0.0
        return (1.02 ** anios) - 1.0
    # Resto: 1% lineal por año
    return (float(d.anios or 0) * 0.01)

def _zona_factor(d: DatosEmpleado) -> float:
    # d.zona viene como porcentaje (0, 10, 20, etc.)
    z = _get_float(d.zona)
    if z <= 0:
        return 0.0
    return z / 100.0

@app.post("/calcular")
def calcular(d: DatosEmpleado) -> Dict[str, Any]:
    """
    Endpoint principal de cálculo.

    IMPORTANTE:
    - Si el frontend manda basico=0 (HTML limpio), el backend SIEMPRE toma el básico desde escalas.
    - Lo mismo para NR variable (No Remunerativo) y NR fija (Suma Fija) cuando vengan en 0.
    """
    # --- Buscar escala ---
    row = escalas.buscar_escala(d.rama, d.agrup, d.categoria, d.mes)
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Sin escala para Rama={d.rama} / Agrup={d.agrup} / Cat={d.categoria} / Mes={d.mes}",
        )

    basico_escala = _get_float(row.get("Basico"))
    nr_var_escala = _get_float(row.get("No Remunerativo"))
    nr_sf_escala  = _get_float(row.get("Suma Fija"))

    # --- Resolver bases (si vienen en 0 desde el HTML limpio) ---
    basico_base = _get_float(d.basico) if _get_float(d.basico) > 0 else basico_escala
    nr_var_base = _get_float(getattr(d, "nrVar", 0)) if _get_float(getattr(d, "nrVar", 0)) > 0 else nr_var_escala
    nr_sf_base  = _get_float(getattr(d, "nrSF", 0))  if _get_float(getattr(d, "nrSF", 0))  > 0 else nr_sf_escala

    # --- Jornada ---
    prop = _jornada_prop(d)
    basico_calc = basico_base * prop
    nr_var_calc = nr_var_base * prop
    nr_sf_calc  = nr_sf_base * prop

    # --- Antigüedad ---
    tasa_antig = _antig_tasa(d)
    antig_rem = basico_calc * tasa_antig
    antig_nr  = (nr_var_calc + nr_sf_calc) * tasa_antig

    # --- Zona ---
    zona_factor = _zona_factor(d)
    zona_rem = (basico_calc + antig_rem) * zona_factor
    # (si alguna vez necesitás zona NR, se puede agregar; hoy mantenemos 0)
    zona_nr = 0.0

    # --- Presentismo ---
    # Si no viene, inferir con coAus<=1
    pres_flag = d.presentismo
    if pres_flag is None:
        pres_flag = (int(d.coAus or 0) <= 1)

    pres_rem = 0.0
    pres_nr = 0.0
    if pres_flag:
        pres_base_rem = basico_calc + antig_rem + zona_rem
        pres_base_nr  = (nr_var_calc + nr_sf_calc + antig_nr + zona_nr)
        pres_rem = pres_base_rem / 12.0
        pres_nr  = pres_base_nr  / 12.0

    # --- Totales remunerativos / NR ---
    total_rem = basico_calc + antig_rem + zona_rem + pres_rem
    total_nr  = nr_var_calc + nr_sf_calc + antig_nr + pres_nr

    # --- Deducciones (reglas CO) ---
    jubilado = bool(d.coJub)

    base_jub = total_rem
    jubilacion = 0.0 if jubilado else (base_jub * 0.11)
    pami      = 0.0 if jubilado else (base_jub * 0.03)

    # Base sindical: Rem + todo lo NR del mes (criterio CO)
    base_sind = total_rem + total_nr

    # Si no afiliado, no cobra sindicato ni faecys (ajustable)
    if bool(d.afiliado):
        faecys = base_sind * 0.005
        sindicato = base_sind * 0.02
    else:
        faecys = 0.0
        sindicato = 0.0

    # Obra social:
    # - si osecac == "si": 3% sobre Rem + NR
    # - si osecac == "no": 3% solo sobre Rem (y sin $100 fijo)
    osecac_si = _norm(d.osecac) in ("SI", "SÍ")
    base_os = total_rem + (total_nr if osecac_si else 0.0)
    obra_social = base_os * 0.03

    osecac_fijo = 100.0 if osecac_si else 0.0

    total_deducciones = jubilacion + pami + faecys + sindicato + obra_social + osecac_fijo
    neto = (total_rem + total_nr) - total_deducciones

    # --- Items para UI ---
    items: List[Dict[str, Any]] = []

    def add(concepto: str, rem: float = 0.0, nr: float = 0.0, ded: float = 0.0, base: Optional[float] = None):
        items.append({
            "concepto": concepto,
            "base": (r2(base) if base is not None else None),
            "remunerativo": r2(rem),
            "no_remunerativo": r2(nr),
            "deduccion": r2(ded),
        })

    add("Básico", rem=basico_calc, base=basico_base)
    if antig_rem or antig_nr:
        add("Antigüedad", rem=antig_rem, nr=antig_nr, base=float(d.anios or 0))
    if zona_rem:
        add("Zona Desfavorable", rem=zona_rem, base=float(d.zona or 0))
    if (nr_var_calc + nr_sf_calc) > 0:
        add("No Remunerativo (Acuerdo)", nr=(nr_var_calc + nr_sf_calc))

    if pres_rem or pres_nr:
        add("Presentismo (8.33%)", rem=pres_rem, nr=pres_nr)

    # Deducciones
    add("Jubilación 11%", ded=jubilacion, base=total_rem)
    add("Ley 19.032 (PAMI) 3%", ded=pami, base=total_rem)
    if faecys:
        add("FAECYS 0,5%", ded=faecys, base=base_sind)
    if sindicato:
        add("Sindicato 2%", ded=sindicato, base=base_sind)
    add("Obra Social 3%", ded=obra_social, base=base_os)
    if osecac_fijo:
        add("OSECAC $100", ded=osecac_fijo)

    # --- Respuesta ---
    return {
        "auto": {
            # IMPORTANTE: devolvemos CALCULADO (no crudo de escala) para no filtrar tu maestro
            "basico": r2(basico_calc),
            "nrVar": r2(nr_var_calc),
            "nrSF": r2(nr_sf_calc),
            "nrTotal": r2(total_nr),
        },
        "totales": {
            "total_rem": r2(total_rem),
            "total_nr": r2(total_nr),
            "total_deducciones": r2(total_deducciones),
            "neto": r2(neto),
        },
        "items": items,
    }
