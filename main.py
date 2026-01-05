from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
import escalas
from models import DatosEmpleado

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def r2(x: float) -> float:
    return round(float(x or 0), 2)

@app.post("/calcular")
def calcular_sueldo(d: DatosEmpleado) -> Dict[str, Any]:
    escala = escalas.buscar_escala(d.rama, d.agrup, d.categoria, d.mes)

    basico_escala = float(escala.get("Basico") or 0) if escala else float(d.basico or 0)
    nr_var_escala = float(escala.get("No Remunerativo") or 0) if escala else float(d.nrVar or 0)
    nr_sf_escala  = float(escala.get("Suma Fija") or 0) if escala else float(d.nrSF or 0)

    rama_u = (d.rama or "").upper()
    cat_u = (d.categoria or "").upper()

    # Proporcional jornada
    prop = 1.0
    if "CALL CENTER" not in rama_u and "MENOR" not in cat_u:
        prop = (d.hs or 48) / 48.0

    basico_calc = basico_escala * prop
    nr_var_calc = nr_var_escala * prop
    nr_sf_calc  = nr_sf_escala * prop

    # Antigüedad
    tasa_antig = 0.01 * (d.anios or 0)
    if "AGUA" in rama_u:
        tasa_antig = (1.02 ** (d.anios or 0)) - 1

    antig_rem = basico_calc * tasa_antig
    antig_nr_var = nr_var_calc * tasa_antig
    antig_nr_sf  = nr_sf_calc * tasa_antig

    # Zona (porcentaje)
    zona_pct = float(d.zona or 0) / 100.0
    zona_rem = basico_calc * zona_pct
    zona_nr_var = nr_var_calc * zona_pct
    zona_nr_sf  = nr_sf_calc * zona_pct

    # Presentismo (backend manda el definitivo por coAus)
    presentismo_ok = (d.coAus or 0) <= 1
    pres_rem = (basico_calc + antig_rem + zona_rem) / 12.0 if presentismo_ok else 0.0
    pres_nr_var = (nr_var_calc + antig_nr_var + zona_nr_var) / 12.0 if presentismo_ok else 0.0
    pres_nr_sf  = (nr_sf_calc  + antig_nr_sf  + zona_nr_sf ) / 12.0 if presentismo_ok else 0.0

    # Agua potable - conexiones (usa tabla de adicionales del maestro)
    adic_conex_pct = 0.0
    if "AGUA" in rama_u and d.aguaConex:
        adics = escalas.obtener_adicionales()
        # estructura esperada: adics["AGUA POTABLE"]["CONEXIONES"]["A"]=0.07 etc
        try:
            adic_conex_pct = float(adics.get("AGUA POTABLE",{}).get("CONEXIONES",{}).get(str(d.aguaConex).upper(),0) or 0)
        except Exception:
            adic_conex_pct = 0.0

    adic_conex_rem = (basico_calc + zona_rem + antig_rem + pres_rem) * adic_conex_pct
    # tu regla pedida: “aplica 7% encadenado a Básico + Suma Fija” (NR) -> aplico sobre NR SF también:
    adic_conex_nr = (nr_sf_calc + zona_nr_sf + antig_nr_sf + pres_nr_sf) * adic_conex_pct

    # Fúnebres - adicionales por tareas (desde maestro)
    fun = escalas.obtener_adicionales().get("FUNEBRES", {})
    fun_total_rem = 0.0
    if "FUN" in rama_u:
        # Esperamos porcentajes o importes fijos en el maestro:
        def add_if(flag: bool, key: str):
            nonlocal fun_total_rem
            if not flag: return
            v = float(fun.get(key, 0) or 0)
            # si es porcentaje (>0 y <1), aplico sobre básico+antig+zona+pres; si es importe fijo, lo sumo
            if 0 < v < 1:
                fun_total_rem += (basico_calc + antig_rem + zona_rem + pres_rem) * v
            else:
                fun_total_rem += v * prop
        add_if(d.funAdic1, "ADIC1")
        add_if(d.funAdic2, "ADIC2")
        add_if(d.funAdic3, "ADIC3")
        add_if(d.funAdic4, "ADIC4")

    # Totales remunerativos / no remunerativos
    total_rem = basico_calc + antig_rem + zona_rem + pres_rem + adic_conex_rem + fun_total_rem
    total_nr_var = nr_var_calc + antig_nr_var + zona_nr_var + pres_nr_var
    total_nr_sf  = nr_sf_calc  + antig_nr_sf  + zona_nr_sf  + pres_nr_sf + adic_conex_nr
    total_nr = total_nr_var + total_nr_sf + float(d.aCuentaNR or 0) + float(d.viaticosNR or 0)

    # Bases aportes
    base_aportes_rem = total_rem  # jubil/pami sobre rem
    base_aportes_all = total_rem + total_nr  # faecys/sind/osecac sobre todo segun tu política

    # Deducciones
    jubilacion = base_aportes_rem * 0.11 if not d.coJub else 0.0
    pami = base_aportes_rem * 0.03 if not d.coJub else 0.0

    # Obra social: si osecac=si aplica 3% sobre (rem + NR) + $100
    obra_social = (base_aportes_all * 0.03) if d.osecac == "si" and not d.coJub else 0.0
    osecac_100 = 100.0 if d.osecac == "si" and not d.coJub else 0.0

    faecys = base_aportes_all * 0.005 if d.afiliado else base_aportes_all * 0.005
    sindicato = base_aportes_all * 0.02 if d.afiliado else base_aportes_all * 0.02

    total_deducciones = jubilacion + pami + obra_social + osecac_100 + faecys + sindicato
    neto = (total_rem + total_nr) - total_deducciones

    items: List[Dict[str, Any]] = []
    items.append({"concepto":"Básico","base":r2(basico_escala),"remunerativo":r2(basico_calc),"no_remunerativo":0,"deduccion":0})
    if antig_rem or antig_nr_var or antig_nr_sf:
        items.append({"concepto":"Antigüedad","base":None,"remunerativo":r2(antig_rem),"no_remunerativo":r2(antig_nr_var+antig_nr_sf),"deduccion":0})
    if zona_rem or zona_nr_var or zona_nr_sf:
        items.append({"concepto":"Zona Desfavorable","base":r2(basico_escala),"remunerativo":r2(zona_rem),"no_remunerativo":r2(zona_nr_var+zona_nr_sf),"deduccion":0})
    if pres_rem or pres_nr_var or pres_nr_sf:
        items.append({"concepto":"Presentismo (8,33%)","base":r2(basico_calc+antig_rem+zona_rem),"remunerativo":r2(pres_rem),"no_remunerativo":r2(pres_nr_var+pres_nr_sf),"deduccion":0})

    # NR explícitos (para que el frontend los muestre)
    if nr_var_calc:
        items.append({"concepto":"No Rem (variable)","base":r2(nr_var_escala),"remunerativo":0,"no_remunerativo":r2(nr_var_calc),"deduccion":0})
    if nr_sf_calc:
        items.append({"concepto":"Suma Fija (NR)","base":r2(nr_sf_escala),"remunerativo":0,"no_remunerativo":r2(nr_sf_calc),"deduccion":0})
    if fun_total_rem:
        items.append({"concepto":"Adicionales Fúnebres","base":None,"remunerativo":r2(fun_total_rem),"no_remunerativo":0,"deduccion":0})
    if adic_conex_rem or adic_conex_nr:
        items.append({"concepto":f"Adicional por conexiones ({(d.aguaConex or '').upper()})","base":None,"remunerativo":r2(adic_conex_rem),"no_remunerativo":r2(adic_conex_nr),"deduccion":0})

    # Deducciones
    if jubilacion: items.append({"concepto":"Jubilación 11%","base":r2(base_aportes_rem),"remunerativo":0,"no_remunerativo":0,"deduccion":r2(jubilacion)})
    if pami: items.append({"concepto":"Ley 19.032 (PAMI) 3%","base":r2(base_aportes_rem),"remunerativo":0,"no_remunerativo":0,"deduccion":r2(pami)})
    if faecys: items.append({"concepto":"FAECYS 0,5%","base":r2(base_aportes_all),"remunerativo":0,"no_remunerativo":0,"deduccion":r2(faecys)})
    if sindicato: items.append({"concepto":"Sindicato 2%","base":r2(base_aportes_all),"remunerativo":0,"no_remunerativo":0,"deduccion":r2(sindicato)})
    if obra_social: items.append({"concepto":"Obra Social 3%","base":r2(base_aportes_all),"remunerativo":0,"no_remunerativo":0,"deduccion":r2(obra_social)})
    if osecac_100: items.append({"concepto":"OSECAC $100","base":None,"remunerativo":0,"no_remunerativo":0,"deduccion":r2(osecac_100)})

    return {
        "auto": {
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
