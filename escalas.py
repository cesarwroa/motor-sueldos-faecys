# -*- coding: utf-8 -*-
"""
escalas.py (sin pandas)
Lee el maestro Excel con openpyxl y expone helpers para:
- /meta (ramas, meses, agrupamientos, categorias)
- /payload (básico / no_rem / suma_fija)
- reglas: conexiones Agua Potable, adicionales Fúnebres, título Turismo, cajero, KM
"""
from __future__ import annotations

import os
import datetime as _dt
from functools import lru_cache
from typing import Dict, Tuple, List, Any, Optional

import openpyxl


# ---------------------------
# Config
# ---------------------------

def _default_maestro_path() -> str:
    # Preferimos SIEMPRE data/maestro_actualizado.xlsx (evita conflicto con un maestro en raíz)
    p1 = os.path.join("data", "maestro_actualizado.xlsx")
    if os.path.exists(p1):
        return p1
    # fallback
    p2 = os.path.join("data", "maestro.xlsx")
    if os.path.exists(p2):
        return p2
    return "maestro.xlsx"


MAESTRO_PATH = os.getenv("MAESTRO_PATH", _default_maestro_path())


# ---------------------------
# Utils
# ---------------------------

def _mes_to_key(v: Any) -> str:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.strftime("%Y-%m")
    if v is None:
        return ""
    s = str(v).strip()
    # admite "2026-04-01 00:00:00"
    if len(s) >= 7 and s[4] == "-" and s[6].isdigit():
        return s[:7]
    return s

def _to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    # números argentinos: "1.176.516" o "1.176.516,50"
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def _norm(s: Any) -> str:
    return str(s).strip() if s is not None else ""


def _nr_labels(rama: str) -> dict:
    """Nombres oficiales de los NR según rama (criterio César)."""
    r = _norm(rama).upper()
    if r in ("TURISMO", "CEREALES"):
        # En el maestro de Turismo/Cereales, suele venir 60k en no_rem y 40k en suma_fija.
        return {
            "no_rem": "Recomp. NR. Acu. 26",
            "suma_fija": "Incr. NR. Acu. Ene 26",
        }
    return {
        "no_rem": "Incr. NR. Acu. Dic 25",
        "suma_fija": "Recomp. NR. Acu. 25",
    }

# ---------------------------
# Maestro loader / parser
# ---------------------------

@lru_cache(maxsize=1)
def _load_wb() -> openpyxl.Workbook:
    return openpyxl.load_workbook(MAESTRO_PATH, data_only=True)

@lru_cache(maxsize=1)
def _build_index() -> Dict[str, Any]:
    wb = _load_wb()

    # salida
    payload: Dict[Tuple[str, str, str, str], Dict[str, float]] = {}
    ramas_set = set()
    meses_set = set()
    agrup_by_rama: Dict[str, set] = {}
    cat_by_rama_agrup: Dict[Tuple[str, str], set] = {}
    meses_by_rama: Dict[str, set] = {}

    def add_row(rama: str, agrup: str, cat: str, mes: str, bas: float, nr: float, sf: float):
        rama_u = _norm(rama).upper()
        agrup_u = _norm(agrup) if _norm(agrup) else "—"
        cat_u = _norm(cat) if _norm(cat) else "—"

        # Fix maestro FUNEBRES: a veces las categorías quedaron en "Agrupamiento" y "Categoria" viene vacío.
        if rama_u == "FUNEBRES" and (cat_u == "—" or cat_u == "") and agrup_u not in ("—", ""):
            cat_u = agrup_u
            agrup_u = "—"
        mes_k = _mes_to_key(mes)

        if not rama_u or not mes_k:
            return

        payload[(rama_u, agrup_u, cat_u, mes_k)] = {"basico": bas, "no_rem": nr, "suma_fija": sf}
        ramas_set.add(rama_u)
        meses_set.add(mes_k)
        agrup_by_rama.setdefault(rama_u, set()).add(agrup_u)
        cat_by_rama_agrup.setdefault((rama_u, agrup_u), set()).add(cat_u)
        meses_by_rama.setdefault(rama_u, set()).add(mes_k)

    # --- Tabulares (GENERAL, TURISMO, FUNEBRES, CEREALES, CALL CENTER)
    for sh_name in wb.sheetnames:
        if not sh_name.startswith("Categorias_"):
            continue
        if sh_name == "Categorias_Agua_Potable":
            continue  # parse especial abajo

        ws = wb[sh_name]
        # headers en fila 1
        headers = [_norm(ws.cell(1, c).value).lower() for c in range(1, 10)]
        # buscamos indices
        def idx(name: str) -> Optional[int]:
            for i,h in enumerate(headers, start=1):
                if h == name:
                    return i
            return None

        i_rama = idx("rama") or 1
        i_agr = idx("agrupamiento") or 2
        i_cat = idx("categoria") or 3
        i_mes = idx("mes") or 4
        i_bas = idx("basico") or 5
        i_nr  = idx("no_rem") or 6
        i_sf  = idx("suma_fija") or 7

        for r in range(2, ws.max_row + 1):
            rama = ws.cell(r, i_rama).value
            if rama is None:
                continue
            mes = ws.cell(r, i_mes).value
            rama_u = _norm(rama).upper()
            agrup = ws.cell(r, i_agr).value
            cat = ws.cell(r, i_cat).value
            bas = _to_float(ws.cell(r, i_bas).value)
            nr  = _to_float(ws.cell(r, i_nr).value)
            sf  = _to_float(ws.cell(r, i_sf).value)
            add_row(rama_u, agrup, cat, mes, bas, nr, sf)

    # --- AGUA POTABLE (sheet no tabular, por bloques)
    if "Categorias_Agua_Potable" in wb.sheetnames:
        ws = wb["Categorias_Agua_Potable"]
        rama_u = "AGUA POTABLE"
        current_agr = "—"
        current_cat = ""
        in_table = False

        for r in range(1, ws.max_row + 1):
            a = ws.cell(r, 1).value
            b = ws.cell(r, 2).value
            c = ws.cell(r, 3).value
            d = ws.cell(r, 4).value

            a_s = _norm(a)

            # AGRUPAMIENTO:
            if isinstance(a, str) and a_s.upper().startswith("AGRUPAMIENTO"):
                # el valor puede venir en col 2
                current_agr = _norm(b) if _norm(b) else "—"
                in_table = False
                continue

            # Categoría:
            if isinstance(a, str) and a_s.upper().startswith("CATEGOR"):
                current_cat = _norm(b)
                in_table = False
                continue

            # header MES - AÑO
            if isinstance(a, str) and a_s.upper().startswith("MES"):
                in_table = True
                continue

            if not in_table:
                continue

            # filas de mes
            mes_k = _mes_to_key(a)
            if not mes_k or mes_k.lower().startswith("mes"):
                continue

            bas = _to_float(b)
            # En Agua Potable, los NR vienen como 2 columnas (incrementos NR) => los consolidamos en "suma_fija"
            sf = _to_float(c) + _to_float(d)
            nr = 0.0

            add_row(rama_u, current_agr or "—", current_cat or "—", mes_k, bas, nr, sf)

    # ---------------------------
    # Adicionales Fúnebres
    # ---------------------------
    funebres_adic: Dict[str, List[Dict[str, Any]]] = {}  # mes -> list
    if "Adicionales" in wb.sheetnames:
        ws = wb["Adicionales"]
        # headers: Rama, Concepto, Mes, Tipo, Monto, % , Observación
        for r in range(2, ws.max_row + 1):
            rama = _norm(ws.cell(r, 1).value)
            if rama.lower() not in ["funebres", "fúnebres"]:
                continue
            concepto = _norm(ws.cell(r, 2).value)
            mes = _mes_to_key(ws.cell(r, 3).value)
            tipo = _norm(ws.cell(r, 4).value).lower()  # "monto" o "porcentaje"
            monto = _to_float(ws.cell(r, 5).value)
            pct = _to_float(ws.cell(r, 6).value)
            obs = _norm(ws.cell(r, 7).value)
            if not mes or not concepto:
                continue
            funebres_adic.setdefault(mes, []).append({
                "id": concepto,        # id simple
                "label": concepto,     # label
                "tipo": "pct" if "por" in tipo else "monto",
                "monto": monto,
                "pct": pct,
                "obs": obs,
            })

    # ---------------------------
    # Build meta
    # ---------------------------
    ramas = sorted(ramas_set)
    meses = sorted(meses_set)

    agrupamientos: Dict[str, List[str]] = {}
    categorias: Dict[str, Dict[str, List[str]]] = {}

    for rama in ramas:
        agrupamientos[rama] = sorted(list(agrup_by_rama.get(rama, set())))
        categorias[rama] = {}
        for agr in agrupamientos[rama]:
            categorias[rama][agr] = sorted(list(cat_by_rama_agrup.get((rama, agr), set())))

    return {
        "payload": payload,
        "meta": {
            "ramas": ramas,
            "meses": meses,
            "agrupamientos": agrupamientos,
            "categorias": categorias,
        },
        "meses_by_rama": {k: sorted(list(v)) for k, v in meses_by_rama.items()},
        "funebres_adic": funebres_adic,
    }


# ---------------------------
# Public API (used by main.py)
# ---------------------------

def get_meta() -> Dict[str, Any]:
    return _build_index()["meta"]

def get_payload(rama: str, mes: str, agrup: str = "—", categoria: str = "—") -> Dict[str, Any]:
    """Devuelve los valores base del maestro para la combinación dada.

    Se usa en:
      - /payload (solo rama + mes)
      - /calcular (rama + mes + agrup + categoria) como base.
    """
    idx = _build_index()
    key = (_norm(rama).upper(), _norm(agrup) or "—", _norm(categoria) or "—", _mes_to_key(mes))
    rec = idx["payload"].get(key)

    if not rec:
        # fallback: algunos front mandan "—" en agrup/cat o vienen vacíos
        key2 = (_norm(rama).upper(), "—", "—", _mes_to_key(mes))
        rec = idx["payload"].get(key2)

    if not rec:
        return {
            "ok": False,
            "error": "No se encontró esa combinación en el maestro",
            "rama": _norm(rama).upper(),
            "agrup": _norm(agrup) or "—",
            "categoria": _norm(categoria) or "—",
            "mes": _mes_to_key(mes),
        }

    labels = _nr_labels(key[0])

    return {"ok": True, "rama": key[0], "agrup": key[1], "categoria": key[2], "mes": key[3], **rec, "labels": labels}

def calcular_payload(
    rama: str,
    agrup: str,
    categoria: str,
    mes: str,
    jornada: float = 48,
    anios_antig: float = 0,
    osecac: bool = True,
    afiliado: bool = False,
    sind_pct: float = 0,
    titulo_pct: float = 0,
) -> Dict[str, Any]:
    """Cálculo del endpoint /calcular (servidor).

    El front NO calcula: solo renderiza.
    Devuelve items + totales numéricos para que el HTML muestre cada fila.

    Versión núcleo (GENERAL): Básico, Antigüedad, Presentismo, NR base y descuentos principales.
    """
    base = get_payload(rama=rama, mes=mes, agrup=agrup, categoria=categoria)
    if not base.get("ok"):
        return base

    # -------- Bases prorrateadas (48hs) --------
    j = float(jornada or 48)
    factor = (j / 48.0) if 48.0 else 1.0

    bas_base = float(base.get("basico", 0.0) or 0.0)
    nr_base = float(base.get("no_rem", 0.0) or 0.0)
    sf_base = float(base.get("suma_fija", 0.0) or 0.0)

    bas = bas_base * factor
    nr = nr_base * factor
    sf = sf_base * factor

    # -------- Cálculos núcleo --------
    presentismo = bas / 12.0
    antig = bas * (float(anios_antig or 0.0) * 0.01)

    rem_total = bas + presentismo + antig
    nr_total = nr + sf

    jub = rem_total * 0.11
    pami = rem_total * 0.03
    os_aporte = rem_total * 0.03 if bool(osecac) else 0.0
    osecac_100 = 100.0 if bool(osecac) else 0.0

    sind = 0.0
    if bool(afiliado) and float(sind_pct or 0) > 0:
        sind = (rem_total + nr_total) * (float(sind_pct) / 100.0)

    ded_total = jub + pami + os_aporte + osecac_100 + sind
    neto = (rem_total + nr_total) - ded_total

    def item(concepto: str, r: float = 0.0, n: float = 0.0, d: float = 0.0, base_num: float = 0.0) -> Dict[str, Any]:
        out = {"concepto": concepto, "r": float(r), "n": float(n), "d": float(d)}
        if base_num:
            out["base"] = float(base_num)
        return out

    items: List[Dict[str, Any]] = [item("Básico", r=bas, base_num=bas)]

    if antig:
        items.append(item("Antigüedad", r=antig, base_num=bas))

    items.append(item("Presentismo", r=presentismo, base_num=bas + antig))

    labels = _nr_labels(base["rama"])

    if nr:
        items.append(item(labels.get("no_rem", "No Remunerativo"), n=nr))
    if sf:
        items.append(item(labels.get("suma_fija", "Suma Fija (NR)"), n=sf))

    items.append(item("Jubilación 11%", d=jub, base_num=rem_total))
    items.append(item("Ley 19.032 (PAMI) 3%", d=pami, base_num=rem_total))

    if bool(osecac):
        items.append(item("Obra Social 3%", d=os_aporte, base_num=rem_total))
        items.append(item("OSECAC $100", d=osecac_100))
    else:
        items.append(item("Obra Social 3%", d=0.0, base_num=rem_total))

    if sind:
        items.append(item(f"Sindicato {float(sind_pct):g}%", d=sind, base_num=(rem_total + nr_total)))

    return {
        "ok": True,
        "rama": base["rama"],
        "agrup": base["agrup"],
        "categoria": base["categoria"],
        "mes": base["mes"],
        "jornada": j,
        "anios_antig": float(anios_antig or 0),
        "osecac": bool(osecac),
        "afiliado": bool(afiliado),
        "sind_pct": float(sind_pct or 0),
        "titulo_pct": float(titulo_pct or 0),

        "labels": labels,

        "basico_base": float(bas_base),
        "no_rem_base": float(nr_base),
        "suma_fija_base": float(sf_base),

        "basico": float(bas),
        "no_rem": float(nr),
        "suma_fija": float(sf),

        "items": items,
        "totales": {
            "rem": float(rem_total),
            "nr": float(nr_total),
            "ded": float(ded_total),
            "neto": float(neto),
        },
    }


def get_adicionales_funebres(mes: str) -> List[Dict[str, Any]]:
    idx = _build_index()
    mes_k = _mes_to_key(mes)
    return idx["funebres_adic"].get(mes_k, [])

def match_regla_conexiones(conexiones: int) -> Dict[str, Any]:
    """
    Agua Potable: reglas por umbrales (según tu UI):
    A: hasta 500
    B: 501-1000
    C: 1001-1600
    D: más de 1600
    El % es 7% encadenado (A=0%, B=7%, C=14,49%, D=22,5043%).
    """
    try:
        n = int(conexiones)
    except Exception:
        n = 0
    if n <= 0:
        return {"cat": None, "pct": 0.0, "label": None}

    if n <= 500:
        level = 0
        cat = "A"
        label = "A (hasta 500)"
    elif n <= 1000:
        level = 1
        cat = "B"
        label = "B (501 a 1000)"
    elif n <= 1600:
        level = 2
        cat = "C"
        label = "C (1001 a 1600)"
    else:
        level = 3
        cat = "D"
        label = "D (más de 1600)"

    pct = (1.07 ** level) - 1.0  # level 0 => 0
    return {"cat": cat, "pct": pct, "label": label}

def get_titulo_pct_por_nivel(nivel: str) -> float:
    n = _norm(nivel).lower()
    if n in ["terciario", "terciario_turismo", "terciario (2.5%)", "2.5", "2,5"]:
        return 2.5
    if n in ["universitario", "licenciatura", "universitario (5%)", "5"]:
        return 5.0
    return 0.0

def get_regla_cajero(tipo: str) -> Dict[str, Any]:
    """
    Regla (CCT 130/75 - Acuerdo 26/09/1983):
      - Cajeros A y C: 12,25% sobre básico inicial Cajeros A
      - Cajeros B: 48% sobre básico inicial Cajeros B
    """
    t = _norm(tipo).upper()
    if t in ["A", "CAJERO A", "CAJEROS A", "CAJERO C", "CAJEROS C", "C"]:
        return {"tipo": t, "pct": 12.25}
    if t in ["B", "CAJERO B", "CAJEROS B"]:
        return {"tipo": t, "pct": 48.0}
    return {"tipo": t, "pct": 0.0}

def get_regla_km(categoria: str, km: float) -> Dict[str, Any]:
    """Normaliza el input de KM para el endpoint /regla-km.

    El motor (y/o el front) puede decidir si aplica la regla <=100 o >100.
    Acá devolvemos ambos tramos ya separados.
    """
    try:
        k = float(km or 0)
    except Exception:
        k = 0.0

    km_le_100 = min(k, 100.0)
    km_gt_100 = max(k - 100.0, 0.0)

    return {
        "categoria": _norm(categoria),
        "km": k,
        "km_le_100": km_le_100,
        "km_gt_100": km_gt_100,
    }
