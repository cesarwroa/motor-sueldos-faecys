from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Literal, Dict, Any, List
from datetime import date

from models import DatosEmpleado, RespuestaCalculo, ItemRecibo, Totales
import escalas

app = FastAPI(title="Motor de Sueldos CCT 130/75")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"mensaje": "API de Liquidación de Sueldos CCT 130/75 Online"}

@app.get("/metadata")
def metadata() -> Dict[str, Any]:
    """
    Devuelve solo metadata (sin importes) para poblar selects del frontend.
    """
    ramas = escalas.listar_ramas()
    meses = escalas.listar_meses()
    agrups = {r: escalas.listar_agrups(r) for r in ramas}
    categorias = {}
    for r in ramas:
        for a in agrups[r]:
            categorias[f"{r}|||{a}"] = escalas.listar_categorias(r, a)
    return {"ramas": ramas, "meses": meses, "agrups": agrups, "categorias": categorias}

@app.post("/calcular", response_model=RespuestaCalculo)
def calcular_sueldo(d: DatosEmpleado) -> RespuestaCalculo:
    # --- 1) Escala ---
    escala = escalas.buscar_escala(d.rama, d.agrup, d.categoria, d.mes)

    # Si hay escala, manda el servidor. Si no, cae a lo que mande el front (por compatibilidad).
    basico_full = float((escala or {}).get("Basico") or d.basico or 0.0)
    nr_var_full = float((escala or {}).get("No Remunerativo") or d.nrVar or 0.0)
    nr_sf_full  = float((escala or {}).get("Suma Fija") or d.nrSF or 0.0)

    # --- 2) Proporcionalidad por jornada ---
    rama_u = (d.rama or "").strip().upper()
    cat_u = (d.categoria or "").strip().upper()

    prop = 1.0
    # Regla: Call Center trae valores por jornada (no prorratear); Menores trae valores cerrados (no prorratear)
    if "CALL CENTER" not in rama_u and "MENOR" not in cat_u:
        hs = float(d.hs or 48)
        prop = hs / 48.0 if hs else 1.0

    basico = basico_full * prop
    nr_var = nr_var_full * prop
    nr_sf  = nr_sf_full  * prop

    # --- 3) Antigüedad ---
    # General: 1% por año. Agua: 2% acumulativo (según tu regla de sistema)
    anios = float(d.anios or 0)
    if "AGUA" in rama_u:
        tasa_antig = (1.02 ** anios) - 1.0
    else:
        tasa_antig = 0.01 * anios

    antig_rem = basico * tasa_antig
    antig_nr  = (nr_var + nr_sf) * tasa_antig

    # --- 4) Zona (porcentaje) sobre (básico + antigüedad) ---
    zona_pct = float(d.zona or 0.0) / 100.0
    zona_rem = (basico + antig_rem) * zona_pct

    # --- 5) Presentismo ---
    # Regla: presente si coAus <= 1
    coAus = float(d.coAus or 0.0)
    presentismo_ok = bool(d.presentismo) if d.presentismo is not None else (coAus <= 1)

    base_pres_rem = basico + antig_rem + zona_rem
    base_pres_nr  = (nr_var + nr_sf) + antig_nr

    pres_rem = (base_pres_rem / 12.0) if presentismo_ok else 0.0
    pres_nr  = (base_pres_nr  / 12.0) if presentismo_ok else 0.0

    # --- 6) Totales Brutos ---
    total_rem = base_pres_rem + pres_rem
    total_nr  = base_pres_nr + pres_nr

    # --- 7) Deducciones ---
    base_aportes_rem = total_rem
    base_total = total_rem + total_nr  # base para sindicato/faecys y OS (si OSECAC)

    jubilacion = base_aportes_rem * 0.11

    # PAMI 3%: si jubilado, no aplica (según tu código actual)
    pami = 0.0 if d.coJub else (base_aportes_rem * 0.03)

    sindicato = base_total * 0.02
    faecys = base_total * 0.005

    # Obra Social 3%: si OSECAC=si -> Rem+NR, si no -> solo Rem (tu regla)
    tiene_osecac = (str(d.osecac).lower() in ["si", "sí"])
    base_os = base_total if tiene_osecac else base_aportes_rem

    # Ajuste jornada parcial: elevar base a jornada completa (excepto Call Center)
    if prop < 1.0 and prop > 0.0 and "CALL CENTER" not in rama_u:
        base_os = base_os / prop

    obra_social = 0.0 if d.coJub else (base_os * 0.03)
    osecac_fijo = 0.0 if (d.coJub or not tiene_osecac) else 100.0

    total_deducciones = jubilacion + pami + sindicato + faecys + obra_social + osecac_fijo
    neto = total_rem + total_nr - total_deducciones

    # --- 8) Items (con NR explícitos) ---
    items: List[ItemRecibo] = [
        ItemRecibo(concepto="Básico", base=basico_full, remunerativo=round(basico, 2), no_remunerativo=0.0, deduccion=0.0),
    ]

    if nr_var != 0:
        items.append(ItemRecibo(concepto="No Remunerativo (Variable)", base=nr_var_full, remunerativo=0.0, no_remunerativo=round(nr_var, 2), deduccion=0.0))
    if nr_sf != 0:
        items.append(ItemRecibo(concepto="Suma Fija (NR)", base=nr_sf_full, remunerativo=0.0, no_remunerativo=round(nr_sf, 2), deduccion=0.0))

    if anios:
        items.append(ItemRecibo(concepto="Antigüedad", base=None, remunerativo=round(antig_rem, 2), no_remunerativo=round(antig_nr, 2), deduccion=0.0))

    if zona_pct:
        items.append(ItemRecibo(concepto="Zona Desfavorable", base=round(basico + antig_rem, 2), remunerativo=round(zona_rem, 2), no_remunerativo=0.0, deduccion=0.0))

    if presentismo_ok and (pres_rem or pres_nr):
        items.append(ItemRecibo(concepto="Presentismo (8.33%)", base=None, remunerativo=round(pres_rem, 2), no_remunerativo=round(pres_nr, 2), deduccion=0.0))

    # Deducciones
    items.extend([
        ItemRecibo(concepto="Jubilación 11%", base=round(base_aportes_rem, 2), remunerativo=0.0, no_remunerativo=0.0, deduccion=round(jubilacion, 2)),
        ItemRecibo(concepto="Ley 19.032 (PAMI) 3%", base=round(base_aportes_rem, 2), remunerativo=0.0, no_remunerativo=0.0, deduccion=round(pami, 2)),
        ItemRecibo(concepto="FAECYS 0,5%", base=round(base_total, 2), remunerativo=0.0, no_remunerativo=0.0, deduccion=round(faecys, 2)),
        ItemRecibo(concepto="Sindicato 2%", base=round(base_total, 2), remunerativo=0.0, no_remunerativo=0.0, deduccion=round(sindicato, 2)),
        ItemRecibo(concepto="Obra Social 3%", base=round(base_os, 2), remunerativo=0.0, no_remunerativo=0.0, deduccion=round(obra_social, 2)),
        ItemRecibo(concepto="OSECAC $100", base=None, remunerativo=0.0, no_remunerativo=0.0, deduccion=round(osecac_fijo, 2)),
    ])

    return RespuestaCalculo(
        totales=Totales(
            total_rem=round(total_rem, 2),
            total_nr=round(total_nr, 2),
            total_deducciones=round(total_deducciones, 2),
            neto=round(neto, 2),
        ),
        items=items
    )
