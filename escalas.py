# -*- coding: utf-8 -*-
"""escalas.py (sin pandas)

Lee el maestro Excel con openpyxl y provee:
- Meta (ramas, agrupamientos, categorias, meses globales y por rama)
- Lookup de base (basico, no_rem, suma_fija)
- Adicionales (Fúnebres) y reglas (Agua Potable conexiones)

El backend usa este archivo para evitar dependencias pesadas (pandas) que suelen romper en deploy.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import openpyxl


def _default_maestro_path() -> str:
    # Preferimos siempre data/maestro_actualizado.xlsx
    here = os.path.dirname(os.path.abspath(__file__))
    p1 = os.path.join(here, "data", "maestro_actualizado.xlsx")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(here, "maestro_actualizado.xlsx")
    if os.path.exists(p2):
        return p2
    # fallbacks
    p3 = os.path.join(here, "data", "maestro.xlsx")
    if os.path.exists(p3):
        return p3
    return os.path.join(here, "maestro.xlsx")


MAESTRO_PATH = os.getenv("MAESTRO_PATH", _default_maestro_path())

# CO: Limite inferior del selector de meses (inclusive).
# Default: 2025-12 para evitar que el selector muestre meses viejos.
# Para permitir meses anteriores, setear env MIN_MES_SELECT=YYYY-MM.
MIN_MES_SELECT = os.getenv('MIN_MES_SELECT', '2025-12').strip()

def _filter_meses(meses):
    mm = MIN_MES_SELECT
    if mm and len(mm)==7 and mm[4]=='-':
        return [m for m in meses if m >= mm]
    return meses



def _norm(x: Any) -> str:
    return str(x or "").strip()


def _u(x: Any) -> str:
    return _norm(x).upper()


def _mes_to_key(v: Any) -> str:
    """Convierte una celda de mes a clave YYYY-MM y filtra basura (p.ej. 'MES - AÑO')."""

    def _valid_ym(s: str) -> bool:
        if len(s) != 7 or s[4] != '-':
            return False
        y, m = s[:4], s[5:7]
        if not (y.isdigit() and m.isdigit()):
            return False
        mm = int(m)
        return 1 <= mm <= 12

    if isinstance(v, (dt.datetime, dt.date)):
        s = v.strftime('%Y-%m')
        return s if _valid_ym(s) else ''
    if v is None:
        return ''
    s = _norm(v)
    # admite '2026-04-01 00:00:00'
    if len(s) >= 7 and s[4] == '-':
        s = s[:7]
    return s if _valid_ym(s) else ''


def _to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = _norm(v)
    if not s:
        return 0.0
    # formato AR: 1.234.567,89
    s = s.replace("$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


@lru_cache(maxsize=1)
def _load_wb() -> openpyxl.Workbook:
    if not os.path.exists(MAESTRO_PATH):
        raise FileNotFoundError(f"No se encontró el maestro: {MAESTRO_PATH}")
    return openpyxl.load_workbook(MAESTRO_PATH, data_only=True)


@lru_cache(maxsize=1)
def _build() -> Dict[str, Any]:
    wb = _load_wb()

    payload: Dict[Tuple[str, str, str, str], Dict[str, float]] = {}
    ramas_set = set()
    meses_set = set()
    agrup_by_rama: Dict[str, set] = {}
    cat_by_rama_agr: Dict[Tuple[str, str], set] = {}
    meses_by_rama: Dict[str, set] = {}
    meses_by_combo: Dict[Tuple[str, str, str], set] = {}

    def add_row(rama: str, agrup: Any, categoria: Any, mes: Any, bas: float, nr: float, sf: float):
        rama_u = _u(rama)
        if not rama_u:
            return
        agr = _norm(agrup) or "—"
        cat = _norm(categoria) or "—"
        mes_k = _mes_to_key(mes)
        if not mes_k:
            return

        # Fix maestro: en FUNEBRES a veces la categoria quedo en Agrupamiento
        if rama_u == "FUNEBRES" and (cat in ("—", "") and agr not in ("—", "")):
            cat = agr
            agr = "—"

        payload[(rama_u, agr, cat, mes_k)] = {"basico": float(bas), "no_rem": float(nr), "suma_fija": float(sf)}

        ramas_set.add(rama_u)
        meses_set.add(mes_k)
        agrup_by_rama.setdefault(rama_u, set()).add(agr)
        cat_by_rama_agr.setdefault((rama_u, agr), set()).add(cat)
        meses_by_rama.setdefault(rama_u, set()).add(mes_k)
        meses_by_combo.setdefault((rama_u, agr, cat), set()).add(mes_k)

    # ---- Hojas tabulares Categorias_* (excepto Agua Potable)
    for sh in wb.sheetnames:
        if not sh.startswith("Categorias_"):
            continue
        if sh == "Categorias_Agua_Potable":
            continue

        ws = wb[sh]
        headers = [_norm(ws.cell(1, c).value).lower() for c in range(1, 15)]

        def col(name: str, fallback: int) -> int:
            for i, h in enumerate(headers, start=1):
                if h == name:
                    return i
            return fallback

        c_rama = col("rama", 1)
        c_agr = col("agrupamiento", 2)
        c_cat = col("categoria", 3)
        c_mes = col("mes", 4)
        c_bas = col("basico", 5)
        c_nr = col("no_rem", 6)
        c_sf = col("suma_fija", 7)

        for r in range(2, ws.max_row + 1):
            rama = ws.cell(r, c_rama).value
            if rama is None:
                continue
            mes = ws.cell(r, c_mes).value
            add_row(
                rama=rama,
                agrup=ws.cell(r, c_agr).value,
                categoria=ws.cell(r, c_cat).value,
                mes=mes,
                bas=_to_float(ws.cell(r, c_bas).value),
                nr=_to_float(ws.cell(r, c_nr).value),
                sf=_to_float(ws.cell(r, c_sf).value),
            )

    # ---- Agua Potable: formato por bloques
    if "Categorias_Agua_Potable" in wb.sheetnames:
        ws = wb["Categorias_Agua_Potable"]
        rama_u = "AGUA POTABLE"
        current_agr = "—"
        current_cat = "—"
        in_table = False

        for r in range(1, ws.max_row + 1):
            a = ws.cell(r, 1).value
            b = ws.cell(r, 2).value
            c = ws.cell(r, 3).value
            d = ws.cell(r, 4).value

            a_s = _u(a)
            if isinstance(a, str) and a_s.startswith("AGRUPAMIENTO"):
                current_agr = _norm(b) or "—"
                in_table = False
                continue
            if isinstance(a, str) and a_s.startswith("CATEGOR"):
                current_cat = _norm(b) or "—"
                in_table = False
                continue
            if isinstance(a, str) and a_s.startswith("MES"):
                in_table = True
                continue
            if not in_table:
                continue

            mes_k = _mes_to_key(a)
            if not mes_k or mes_k.lower().startswith("mes"):
                continue

            bas = _to_float(b)
            # Agua: NR en 2 columnas -> consolidamos en suma_fija
            sf = _to_float(c) + _to_float(d)
            add_row(rama_u, current_agr, current_cat, mes_k, bas, 0.0, sf)

    # ---- Adicionales Fúnebres
    funebres_adic: Dict[str, List[Dict[str, Any]]] = {}
    if "Adicionales" in wb.sheetnames:
        ws = wb["Adicionales"]
        for r in range(2, ws.max_row + 1):
            rama = _u(ws.cell(r, 1).value)
            if rama not in ("FUNEBRES", "FÚNEBRES"):
                continue
            concepto = _norm(ws.cell(r, 2).value)
            mes = _mes_to_key(ws.cell(r, 3).value)
            tipo = _u(ws.cell(r, 4).value)
            monto = _to_float(ws.cell(r, 5).value)
            pct = _to_float(ws.cell(r, 6).value)
            obs = _norm(ws.cell(r, 7).value)
            if not mes or not concepto:
                continue
            funebres_adic.setdefault(mes, []).append(
                {
                    "id": concepto,
                    "label": concepto,
                    "tipo": "pct" if "POR" in tipo else "monto",
                    "monto": monto,
                    "pct": pct,
                    "obs": obs,
                }
            )

    # ---- Reglas conexiones (Agua Potable)
    reglas_conex: List[Dict[str, Any]] = []
    if "ReglasConexiones" in wb.sheetnames:
        ws = wb["ReglasConexiones"]
        headers = [_norm(ws.cell(1, c).value).lower() for c in range(1, 10)]
        def _c(name: str) -> Optional[int]:
            for i, h in enumerate(headers, start=1):
                if h == name:
                    return i
            return None
        c_base = _c("base") or 1
        c_pct = _c("porcentaje") or 2
        c_det = _c("detalle") or 3
        for r in range(2, ws.max_row + 1):
            base = int(_to_float(ws.cell(r, c_base).value))
            pct = _to_float(ws.cell(r, c_pct).value)
            det = _norm(ws.cell(r, c_det).value)
            if base <= 0:
                continue
            reglas_conex.append({"base": base, "pct": pct, "detalle": det})
        reglas_conex.sort(key=lambda x: x["base"])

    ramas = sorted(ramas_set)
    meses = sorted(meses_set)
    meses = _filter_meses(meses)

    agrupamientos: Dict[str, List[str]] = {}
    categorias: Dict[str, Dict[str, List[str]]] = {}
    for rama in ramas:
        agrupamientos[rama] = sorted(list(agrup_by_rama.get(rama, set())))
        categorias[rama] = {}
        for agr in agrupamientos[rama]:
            categorias[rama][agr] = sorted(list(cat_by_rama_agr.get((rama, agr), set())))

    return {
        "payload": payload,
        "meta": {
            "ramas": ramas,
            "meses": _filter_meses(meses),
            "meses_por_rama": {k: _filter_meses(sorted(list(v))) for k, v in meses_by_rama.items()},
            "agrupamientos": agrupamientos,
            "categorias": categorias,
        },
        "funebres_adic": funebres_adic,
        "reglas_conex": reglas_conex,
        "meses_combo": meses_by_combo,
    }


# -----------------
# Public helpers
# -----------------

def get_meta_full() -> Dict[str, Any]:
    d = _build()["meta"]
    return {"ok": True, **d}


def get_meta() -> Dict[str, Any]:
    # compat
    return _build()["meta"]


def list_meses_combo(rama: str, agrup: str = "—", categoria: str = "—") -> Dict[str, Any]:
    r = _u(rama)
    a = _norm(agrup) or "—"
    c = _norm(categoria) or "—"
    m = _build().get("meses_combo", {})
    meses = sorted(list(m.get((r, a, c), set())))
    if not meses and a != "—":
        # fallback: algunos maestros usan agrup "—"
        meses = sorted(list(m.get((r, "—", c), set())))
    meses = _filter_meses(meses)
    return {"ok": True, "rama": r, "agrup": a, "categoria": c, "meses": meses}


def find_row(rama: str, agrup: str, categoria: str, mes: str) -> Optional[Dict[str, Any]]:
    key = (_u(rama), _norm(agrup) or "—", _norm(categoria) or "—", _mes_to_key(mes))
    rec = _build()["payload"].get(key)
    if rec:
        return {"rama": key[0], "agrup": key[1], "categoria": key[2], "mes": key[3], **rec}
    # fallback agrup "—"
    key2 = (_u(rama), "—", _norm(categoria) or "—", _mes_to_key(mes))
    rec2 = _build()["payload"].get(key2)
    if rec2:
        return {"rama": key2[0], "agrup": key2[1], "categoria": key2[2], "mes": key2[3], **rec2}
    return None


def get_payload(rama: str, mes: str, agrup: str = "—", categoria: str = "—") -> Dict[str, Any]:
    hit = find_row(rama=rama, agrup=agrup, categoria=categoria, mes=mes)
    if not hit:
        return {
            "ok": False,
            "error": "No se encontró esa combinación en el maestro",
            "rama": _u(rama),
            "agrup": _norm(agrup) or "—",
            "categoria": _norm(categoria) or "—",
            "mes": _mes_to_key(mes),
        }
    return {"ok": True, **hit}


def get_adicionales_funebres(mes: str) -> Dict[str, Any]:
    mes_k = _mes_to_key(mes)
    items = _build()["funebres_adic"].get(mes_k, [])
    return {"ok": True, "mes": mes_k, "items": items}


def match_regla_conexiones(cantidad: int) -> Dict[str, Any]:
    regs = _build()["reglas_conex"]
    if not regs:
        return {"ok": False, "error": "No hay reglas de conexiones en el maestro"}
    try:
        n = int(cantidad)
    except Exception:
        return {"ok": False, "error": "Cantidad inválida"}

    best = None
    for r in regs:
        if n >= int(r["base"]):
            best = r
        else:
            break
    if not best:
        best = regs[0]
    return {"ok": True, "cantidad": n, **best}


def get_titulo_pct_por_nivel(nivel: str) -> float:
    n = _u(nivel)
    if n in ("TERCIARIO", "TERCIARY"):
        return 2.5
    if n in ("UNIVERSITARIO", "LICENCIATURA", "UNIVERSITY"):
        return 5.0
    return 0.0


def get_regla_cajero(tipo: str) -> Dict[str, Any]:
    # Regla histórica (Acuerdo 26/09/1983) - porcentajes
    t = _u(tipo)
    if t in ("A", "C"):
        return {"ok": True, "tipo": t, "pct": 12.25}
    if t == "B":
        return {"ok": True, "tipo": t, "pct": 48.0}
    return {"ok": False, "error": "Tipo inválido"}


def get_regla_km(categoria: str, km: float) -> Dict[str, Any]:
    # En el HTML actual se calcula directo; dejamos endpoint por compatibilidad
    try:
        kmv = float(km)
    except Exception:
        return {"ok": False, "error": "km inválido"}
    return {"ok": True, "categoria": _u(categoria), "km": kmv}

