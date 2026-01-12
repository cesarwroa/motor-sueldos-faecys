# -*- coding: utf-8 -*-
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from escalas import (
    get_meta,
    get_payload,
    get_adicionales_funebres,
    match_regla_conexiones,
    get_titulo_pct_por_nivel,
    get_regla_cajero,
    get_regla_km,
)

app = FastAPI(title="Motor Sueldos FAECYS", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ helpers ------------------

def r2(x: float) -> float:
    return round(float(x), 2)

def pct(base: float, p: float) -> float:
    return base * (p / 100.0)

def presentismo(base: float) -> float:
    return base / 12 if base else 0.0

def antiguedad(base: float, anios: float, rama: str) -> float:
    if anios <= 0:
        return 0.0
    if rama == "AGUA POTABLE":
        return base * 0.02 * anios
    return base * 0.01 * anios

# ------------------ core ------------------

@app.get("/")
def root():
    return {"ok": True, "servicio": "motor-sueldos-faecys", "hoy": str(date.today())}

@app.get("/meta")
def meta():
    return get_meta()

@app.get("/payload")
def payload(rama: str, agrup: str = "—", categoria: str = "—", mes: str = ""):
    return get_payload(rama, agrup, categoria, mes)

@app.get("/calcular")
def calcular_get(
    rama: str,
    agrup: str = "—",
    categoria: str = "—",
    mes: str = "",
    jornada: float = 48,
    anios_antig: float = 0,
    osecac: bool = True,
    afiliado: bool = False,
    sind_pct: float = 0,
    titulo_nivel: Optional[str] = None,
    cajero_tipo: Optional[str] = None,
    km_chofer: float = 0,
    km_ayudante: float = 0,
    conexiones: int = 0,
    funebres_adic: Optional[str] = None,
):
    return calcular_core(locals())

@app.post("/calcular")
def calcular_post(payload: Dict[str, Any] = Body(...)):
    return calcular_core(payload)

def calcular_core(p: Dict[str, Any]) -> Dict[str, Any]:
    base = get_payload(p["rama"], p.get("agrup","—"), p.get("categoria","—"), p.get("mes",""))
    if not base.get("ok"):
        return base

    rama = base["rama"]
    basico = float(base["basico"])
    no_rem = float(base["no_rem"])
    suma_fija = float(base["suma_fija"])

    # prorrateo jornada
    if p.get("jornada",48) != 48:
        basico *= p["jornada"] / 48

    items: List[Dict[str,Any]] = []

    # Básico
    items.append({"concepto":"Básico","base":r2(basico),"rem":r2(basico),"nr":0,"ded":0})

    # Presentismo
    pres = presentismo(basico)
    if pres:
        items.append({"concepto":"Presentismo","base":r2(basico),"rem":r2(pres),"nr":0,"ded":0})

    # Antigüedad
    base_total = basico + no_rem + suma_fija
    anti = antiguedad(base_total, p.get("anios_antig",0), rama)
    if anti:
        items.append({"concepto":"Antigüedad","base":r2(base_total),"rem":r2(anti),"nr":0,"ded":0})

    # NR
    if no_rem:
        items.append({"concepto":"No Remunerativo","base":r2(no_rem),"rem":0,"nr":r2(no_rem),"ded":0})
    if suma_fija:
        items.append({"concepto":"Suma Fija NR","base":r2(suma_fija),"rem":0,"nr":r2(suma_fija),"ded":0})

    # Turismo título
    if rama == "TURISMO" and p.get("titulo_nivel"):
        pct_t = get_titulo_pct_por_nivel(p["titulo_nivel"])
        if pct_t:
            items.append({
                "concepto":f"Adicional por Título ({pct_t}%)",
                "base":r2(base_total),
                "rem":r2(pct(basico,pct_t)),
                "nr":r2(pct(no_rem+suma_fija,pct_t)),
                "ded":0
            })

    # Agua Potable conexiones
    if rama == "AGUA POTABLE" and p.get("conexiones",0) > 0:
        regla = match_regla_conexiones(p["conexiones"])
        if regla:
            pct_c = regla["porcentaje"]
            items.append({
                "concepto":f"Adicional por conexiones ({p['conexiones']}) – Cat {regla['categoria']}",
                "base":r2(base_total),
                "rem":r2(pct(basico,pct_c)),
                "nr":r2(pct(no_rem+suma_fija,pct_c)),
                "ded":0
            })

    # Fúnebres
    if rama == "FUNEBRES":
        sel = (p.get("funebres_adic") or "").split("|")
        for ad in get_adicionales_funebres(p["mes"]):
            if sel and ad["concepto"] not in sel:
                continue
            items.append({
                "concepto":ad["concepto"],
                "base":r2(ad["rem"]+ad["nr"]),
                "rem":r2(ad["rem"]),
                "nr":r2(ad["nr"]),
                "ded":0
            })

    # Totales
    rem = sum(i["rem"] for i in items)
    nr = sum(i["nr"] for i in items)

    # Deducciones
    ded = 0
    ded += pct(rem,11)
    ded += pct(rem,3)
    if p.get("osecac",True):
        ded += pct(rem+nr,3) + 100
    ded += pct(rem+nr,0.5)
    if p.get("afiliado") and p.get("sind_pct",0)>0:
        ded += pct(rem+nr,p["sind_pct"])

    return {
        "ok":True,
        "rama":rama,
        "categoria":base["categoria"],
        "mes":p["mes"],
        "items":items,
        "totales":{
            "rem":r2(rem),
            "nr":r2(nr),
            "ded":r2(ded),
            "neto":r2(rem+nr-ded)
        }
    }
