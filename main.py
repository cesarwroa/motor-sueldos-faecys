# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from escalas import get_meta, get_payload, get_adicionales_funebres, match_regla_conexiones, get_titulo_pct_por_nivel, get_regla_cajero, get_regla_km

app = FastAPI(title="Motor Sueldos FAECYS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # si querés, después lo limitamos a tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------
# Helpers de cálculo
# --------------------------

def _round2(x: float) -> float:
    return float(round(x + 1e-9, 2))

def _pct(base: float, p: float) -> float:
    return base * (p / 100.0)

def _presentismo(base_rem: float) -> float:
    # 8,33% = 1/12
    return base_rem / 12.0 if base_rem else 0.0

def _antiguedad(base: float, anios: float, rama: str) -> float:
    # Regla: Agua Potable 2% acumulativo, resto 1% no acumulativo
    if anios <= 0:
        return 0.0
    if rama == "AGUA POTABLE":
        return base * (0.02 * anios)
    return base * (0.01 * anios)

def _calc_items_base(rama: str, basico: float, no_rem: float, suma_fija: float, anios_antig: float,
                     titulo_pct: float = 0.0, conexiones: int = 0,
                     funebres_adic: Optional[List[str]] = None,
                     mes: str = "") -> List[Dict[str, Any]]:
    """
    Arma ítems remunerativos/no remunerativos antes de deducciones.
    """
    items: List[Dict[str, Any]] = []

    # Básico REM
    items.append({
        "concepto": "Básico (REM)",
        "base": _round2(basico),
        "rem": _round2(basico),
        "nr": 0.0,
        "ded": 0.0
    })

    # Presentismo REM
    pres = _presentismo(basico)
    if pres:
        items.append({
            "concepto": "Presentismo (REM)",
            "base": _round2(basico),
            "rem": _round2(pres),
            "nr": 0.0,
            "ded": 0.0
        })

    # Antigüedad (REM + NR en Agua Potable, según tu política general de cálculo sobre NR)
    # Para no romper, lo calculamos sobre la suma base (basico + no rem total) y lo desdoblamos.
    base_nr_total = (no_rem + suma_fija)
    anti_base_total = basico + base_nr_total
    anti_total = _antiguedad(anti_base_total, anios_antig, rama)
    if anti_total:
        # prorrateo simple: parte rem proporcional al basico, parte nr al nr_total
        rem_part = anti_total * (basico / anti_base_total) if anti_base_total else anti_total
        nr_part = anti_total - rem_part
        items.append({
            "concepto": "Antigüedad",
            "base": _round2(anti_base_total),
            "rem": _round2(rem_part),
            "nr": _round2(nr_part),
            "ded": 0.0
        })

    # No Rem "variable"
    if no_rem:
        items.append({
            "concepto": "No Rem (variable)",
            "base": _round2(no_rem),
            "rem": 0.0,
            "nr": _round2(no_rem),
            "ded": 0.0
        })

    # Suma Fija NR
    if suma_fija:
        items.append({
            "concepto": "Suma Fija (NR)",
            "base": _round2(suma_fija),
            "rem": 0.0,
            "nr": _round2(suma_fija),
            "ded": 0.0
        })

    # Turismo: Adicional por Título (sobre básico y sobre NR)
    if rama == "TURISMO" and titulo_pct and titulo_pct > 0:
        rem_tit = _pct(basico, titulo_pct)
        nr_tit = _pct(base_nr_total, titulo_pct)
        items.append({
            "concepto": f"Adicional por Título ({_round2(titulo_pct)}%)",
            "base": _round2(basico + base_nr_total),
            "rem": _round2(rem_tit),
            "nr": _round2(nr_tit),
            "ded": 0.0
        })

    # Agua Potable: conexiones
    if rama == "AGUA POTABLE" and conexiones and int(conexiones) > 0:
        regla = match_regla_conexiones(int(conexiones))
        if regla and regla.get("porcentaje", 0) > 0:
            pct = float(regla["porcentaje"])
            rem_con = _pct(basico, pct)
            nr_con = _pct(base_nr_total, pct)
            label = f"Adicional por conexiones ({int(conexiones)}) – Cat {regla.get('categoria','')}: +{_round2(pct)}%"
            items.append({
                "concepto": label,
                "base": _round2(basico + base_nr_total),
                "rem": _round2(rem_con),
                "nr": _round2(nr_con),
                "ded": 0.0
            })

    
    # CCT 130/75: Adicionales de Cajero (Art. 30) - se calcula si viene cajero_tipo (A/B/C)
    if cajero_tipo:
        regla = get_regla_cajero(cajero_tipo)
        if regla and regla.get("pct", 0) > 0 and regla.get("base_categoria"):
            base_cat = str(regla["base_categoria"])
            try:
                base_payload = get_payload("GENERAL", "GENERAL", base_cat, mes)
                base_val = float(base_payload.get("basico", 0) or 0)
            except Exception:
                base_val = 0.0
            if base_val > 0:
                rem_caj = _pct(base_val, float(regla["pct"]))
                items.append({
                    "concepto": f"Adicional Cajero ({cajero_tipo})",
                    "base": _round2(base_val),
                    "rem": _round2(rem_caj),
                    "nr": 0.0,
                    "ded": 0.0
                })

    # CCT 130/75: KM Chofer/Ayudante (Art. 36) - se calcula si vienen km_chofer/km_ayudante
    def _calc_km(rol: str, km: float):
        if not km or km <= 0:
            return
        km0 = min(km, 100.0)
        km1 = max(km - 100.0, 0.0)

        # tramo 0-100
        r0 = get_regla_km(rol, "0-100")
        if r0 and r0.get("pct_por_km", 0) and r0.get("base_categoria"):
            try:
                bp = get_payload("GENERAL", "GENERAL", str(r0["base_categoria"]), mes)
                base_val = float(bp.get("basico", 0) or 0)
            except Exception:
                base_val = 0.0
            if base_val > 0 and km0 > 0:
                rem = base_val * (float(r0["pct_por_km"]) / 100.0) * km0
                items.append({
                    "concepto": f"Adicional KM {rol} (0-100 km) x {int(km0)}",
                    "base": _round2(base_val),
                    "rem": _round2(rem),
                    "nr": 0.0,
                    "ded": 0.0
                })

        # tramo >100
        r1 = get_regla_km(rol, "100+")
        if r1 and r1.get("pct_por_km", 0) and r1.get("base_categoria"):
            try:
                bp = get_payload("GENERAL", "GENERAL", str(r1["base_categoria"]), mes)
                base_val = float(bp.get("basico", 0) or 0)
            except Exception:
                base_val = 0.0
            if base_val > 0 and km1 > 0:
                rem = base_val * (float(r1["pct_por_km"]) / 100.0) * km1
                items.append({
                    "concepto": f"Adicional KM {rol} (>100 km) x {int(km1)}",
                    "base": _round2(base_val),
                    "rem": _round2(rem),
                    "nr": 0.0,
                    "ded": 0.0
                })

    _calc_km("CHOFER", km_chofer)
    _calc_km("AYUDANTE", km_ayudante)

# Fúnebres: adicionales por mes (optativos)
    if rama == "FUNEBRES":
        disponibles = get_adicionales_funebres(mes)
        sel = set(funebres_adic or [])
        for ad in disponibles:
            concepto = ad["concepto"]
            if sel and concepto not in sel:
                continue
            rem_v = float(ad.get("rem", 0.0) or 0.0)
            nr_v = float(ad.get("nr", 0.0) or 0.0)
            if rem_v == 0.0 and nr_v == 0.0:
                continue
            items.append({
                "concepto": concepto,
                "base": _round2(rem_v + nr_v),
                "rem": _round2(rem_v),
                "nr": _round2(nr_v),
                "ded": 0.0
            })

    return items


def _sum_totals(items: List[Dict[str, Any]]) -> Dict[str, float]:
    rem = sum(float(i.get("rem", 0) or 0) for i in items)
    nr = sum(float(i.get("nr", 0) or 0) for i in items)
    ded = sum(float(i.get("ded", 0) or 0) for i in items)
    return {"rem": _round2(rem), "nr": _round2(nr), "ded": _round2(ded), "neto": _round2(rem + nr - ded)}


def _add_deducciones(items: List[Dict[str, Any]], rama: str, osecac: bool, afiliado: bool, sind_pct: float) -> None:
    """
    Agrega deducciones según política:
    - Jubilación 11% y PAMI 3% sobre REM
    - Obra Social 3% (+$100 si OSECAC) sobre REM + NR si OSECAC; si no OSECAC, no se aplica (según tu regla).
    - FAECYS 0,5% sobre REM + NR
    - Sindicato % (si afiliado) sobre REM + NR (porcentaje viene en sind_pct)
    """
    tot = _sum_totals(items)
    base_rem = tot["rem"]
    base_total = tot["rem"] + tot["nr"]

    # Jubilación y PAMI (solo rem)
    jub = _pct(base_rem, 11)
    pami = _pct(base_rem, 3)

    if jub:
        items.append({"concepto": "Jubilación 11%", "base": _round2(base_rem), "rem": 0.0, "nr": 0.0, "ded": _round2(jub)})
    if pami:
        items.append({"concepto": "PAMI 3%", "base": _round2(base_rem), "rem": 0.0, "nr": 0.0, "ded": _round2(pami)})

    # Obra social (solo si OSECAC)
    if osecac:
        os3 = _pct(base_total, 3)
        os_total = os3 + 100.0
        items.append({"concepto": "Obra Social 3% + $100 (OSECAC)", "base": _round2(base_total), "rem": 0.0, "nr": 0.0, "ded": _round2(os_total)})

    # FAECYS 0,5% sobre total
    fae = _pct(base_total, 0.5)
    if fae:
        items.append({"concepto": "FAECYS 0,5%", "base": _round2(base_total), "rem": 0.0, "nr": 0.0, "ded": _round2(fae)})

    # Sindicato (solo si afiliado)
    if afiliado and sind_pct and sind_pct > 0:
        sind = _pct(base_total, sind_pct)
        items.append({"concepto": f"SINDICATO {_round2(sind_pct)}%", "base": _round2(base_total), "rem": 0.0, "nr": 0.0, "ded": _round2(sind)})


# --------------------------
# API
# --------------------------

@app.get("/")
def root():
    return {"ok": True, "service": "motor-sueldos-faecys", "today": str(date.today())}


@app.get("/meta")
def meta():
    return get_meta()


@app.get("/payload")
def payload(
    rama: str = Query(...),
    agrup: str = Query("—"),
    categoria: str = Query("—"),
    mes: str = Query(...),
):
    return get_payload(rama, agrup, categoria, mes)


# Compatibilidad: GET /calcular (como venías usando)
@app.get("/calcular")
def calcular_get(
    rama: str = Query(...),
    agrup: str = Query("—"),
    categoria: str = Query("—"),
    mes: str = Query(...),
    jornada: float = Query(48),
    anios_antig: float = Query(0),
    osecac: bool = Query(True),
    afiliado: bool = Query(False),
    sind_pct: float = Query(0),
    titulo_pct: float = Query(0),
    titulo_nivel: Optional[str] = Query(None),
    cajero_tipo: Optional[str] = Query(None),
    km_chofer: float = Query(0),
    km_ayudante: float = Query(0),
    conexiones: int = Query(0),
    funebres_adic: Optional[str] = Query(None),  # "a|b|c"
):
    sel = [s for s in (funebres_adic or "").split("|") if s.strip()]
    return calcular_core(
        {
            "rama": rama,
            "agrup": agrup,
            "categoria": categoria,
            "mes": mes,
            "jornada": jornada,
            "anios_antig": anios_antig,
            "osecac": osecac,
            "afiliado": afiliado,
            "sind_pct": sind_pct,
            "titulo_pct": titulo_pct,
            "titulo_nivel": titulo_nivel,
            "cajero_tipo": cajero_tipo,
            "km_chofer": km_chofer,
            "km_ayudante": km_ayudante,
            "conexiones": conexiones,
            "funebres_adicionales": sel,
        }
    )


# Nuevo: POST /calcular (recomendado)
@app.post("/calcular")
def calcular_post(payload: Dict[str, Any] = Body(...)):
    return calcular_core(payload)


def calcular_core(p: Dict[str, Any]) -> Dict[str, Any]:
    rama = str(p.get("rama", "")).strip()
    agrup = str(p.get("agrup", "—")).strip() or "—"
    categoria = str(p.get("categoria", "")).strip()
    mes = str(p.get("mes", "")).strip()[:7]

    jornada = float(p.get("jornada", 48) or 48)
    anios_antig = float(p.get("anios_antig", 0) or 0)

    osecac = bool(p.get("osecac", True))
    afiliado = bool(p.get("afiliado", False))
    sind_pct = float(p.get("sind_pct", 0) or 0)

    titulo_pct = float(p.get("titulo_pct", 0) or 0)

    titulo_nivel = p.get("titulo_nivel")
    if titulo_nivel:
        titulo_pct = float(get_titulo_pct_por_nivel(str(titulo_nivel)) or 0)

    cajero_tipo = str(p.get("cajero_tipo") or "").strip()
    km_chofer = float(p.get("km_chofer", 0) or 0)
    km_ayudante = float(p.get("km_ayudante", 0) or 0)
    conexiones = int(p.get("conexiones", 0) or 0)
    fun_sel = p.get("funebres_adicionales", None) or []
    if isinstance(fun_sel, str):
        fun_sel = [s for s in fun_sel.split("|") if s.strip()]
    if not isinstance(fun_sel, list):
        fun_sel = []

    base = get_payload(rama, agrup, categoria, mes)
    if not base.get("ok"):
        return {**base, "status": 404}

    basico = float(base["basico"])
    no_rem = float(base["no_rem"])
    suma_fija = float(base["suma_fija"])

    # Jornada: solo prorrateamos el básico (y presentismo/antig) salvo Call Center?
    # Por simplicidad: prorrateo general para REM. Los NR se mantienen (si tu maestro ya los trae prorrateados).
    # Si querés un comportamiento distinto por rama, lo ajustamos.
    if jornada and jornada != 48:
        factor = jornada / 48.0
        basico = basico * factor

    items = _calc_items_base(
        rama=base["rama"],
        basico=basico,
        no_rem=no_rem,
        suma_fija=suma_fija,
        anios_antig=anios_antig,
        titulo_pct=titulo_pct,
        conexiones=conexiones,
        funebres_adic=fun_sel,
        mes=mes,
    )

    _add_deducciones(items, rama=base["rama"], osecac=osecac, afiliado=afiliado, sind_pct=sind_pct)

    tot = _sum_totals(items)

    return {
        "ok": True,
        "rama": base["rama"],
        "agrup": base["agrup"],
        "categoria": base["categoria"],
        "mes": mes,
        "jornada": jornada,
        "anios_antig": anios_antig,
        "items": items,
        "totales": tot,
    }
