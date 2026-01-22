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
import re
import datetime as _dt
from functools import lru_cache
from typing import Dict, Tuple, List, Any, Optional

from decimal import Decimal, ROUND_HALF_UP

import openpyxl


# ---------------------------
# Config
# ---------------------------

def _default_maestro_path() -> str:
    # Preferimos SIEMPRE data/maestro_actualizado.xlsx (evita conflicto con un maestro en raíz).
    # Resolvemos relativo a este archivo, no al CWD, para evitar errores 500 en deploy.
    here = os.path.dirname(__file__)

    p1 = os.path.join(here, "data", "maestro_actualizado.xlsx")
    if os.path.exists(p1):
        return p1

    p2 = os.path.join(here, "data", "maestro.xlsx")
    if os.path.exists(p2):
        return p2

    # último fallback (raíz del proyecto)
    p3 = os.path.join(here, "maestro.xlsx")
    if os.path.exists(p3):
        return p3

    return "maestro.xlsx"


MAESTRO_PATH = os.getenv("MAESTRO_PATH", _default_maestro_path())


def round2(x: float) -> float:
    """Redondeo a 2 decimales (half up) para importes."""
    try:
        return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


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


def norm_rama(rama: Any) -> str:
    """Normaliza el nombre de rama para comparaciones."""
    return _norm(rama).upper().replace("  ", " ").strip()



def _extract_hs_from_categoria(cat: Any) -> Optional[float]:
    """Extrae horas de una categoría tipo '... 20HS' / '... 36 hs'."""
    s = _norm(cat).upper()
    if not s:
        return None
    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*H", s)
    if not m:
        return None
    raw = m.group(1).replace(",", ".")
    try:
        v = float(raw)
    except Exception:
        return None
    # límites razonables
    if v <= 0 or v > 48:
        return None
    return v

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
        if rama_u in ("FUNEBRES", "FÚNEBRES") and (cat_u == "—" or cat_u == "") and agrup_u not in ("—", ""):
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
    # La hoja "Adicionales" del maestro puede venir en distintos formatos según versión.
    # Formato usual actual (enero 2026): Rama | Concepto | Mes | Valor | Detalle
    # Otros formatos posibles: Rama | Concepto | Mes | Tipo | Monto | % | Observación
    funebres_adic: Dict[str, List[Dict[str, Any]]] = {}  # mes -> list
    if "Adicionales" in wb.sheetnames:
        ws = wb["Adicionales"]

        # Mapear columnas por encabezados (fila 1)
        header = {}
        for c in range(1, ws.max_column + 1):
            h = _norm(ws.cell(1, c).value)
            if h:
                header[h.lower()] = c

        col_rama = header.get("rama", 1)
        col_concepto = header.get("concepto", 2)
        col_mes = header.get("mes", 3)
        col_tipo = header.get("tipo")  # opcional
        col_monto = header.get("monto") or header.get("valor") or header.get("importe")
        col_pct = header.get("%") or header.get("porcentaje") or header.get("pct")
        col_obs = header.get("observación") or header.get("observacion") or header.get("detalle") or header.get("obs")

        for r in range(2, ws.max_row + 1):
            rama = _norm(ws.cell(r, col_rama).value)
            if rama.lower() not in ["funebres", "fúnebres"]:
                continue

            concepto_raw = _norm(ws.cell(r, col_concepto).value)
            mes_k = _mes_to_key(ws.cell(r, col_mes).value)
            if not mes_k or not concepto_raw:
                continue

            tipo_raw = _norm(ws.cell(r, col_tipo).value).lower() if col_tipo else ""
            monto_val = _to_float(ws.cell(r, col_monto).value) if col_monto else 0.0
            pct_val = _to_float(ws.cell(r, col_pct).value) if col_pct else 0.0
            obs_raw = _norm(ws.cell(r, col_obs).value) if col_obs else ""

            # Determinar tipo
            tipo = "pct" if ("por" in tipo_raw or "%" in tipo_raw) else "monto"

            # Etiquetas amigables (como en el HTML offline)
            cl = concepto_raw.lower()
            label = concepto_raw
            if "indument" in cl:
                label = "Indumentaria"
            elif "general" in cl:
                # Ojo: este concepto suele venir como "... incluidos choferes", por eso
                # se evalúa ANTES que el de chofer/furgonero.
                label = "Resto del personal"
            elif "cadaver" in cl or "cadáver" in cl or "no incluido" in cl or "inciso" in cl:
                label = "Manipulación de cadáveres"
            elif "furgon" in cl or "chofer/furgon" in cl:
                label = "Chofer/Furgonero"

            funebres_adic.setdefault(mes_k, []).append({
                "id": concepto_raw,   # id estable (se usa en fun_adic[] del /calcular)
                "label": label,
                "tipo": tipo,
                "monto": monto_val if tipo == "monto" else 0.0,
                "pct": pct_val if tipo == "pct" else 0.0,
                "obs": obs_raw,
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

def get_payload(
    rama: str,
    mes: str,
    agrup: str = "—",
    categoria: str = "—",
    conex_cat: str = "",
    conexiones: int = 0,
    fun_adic: Optional[List[str]] = None,
) -> Dict[str, Any]:
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

    out = {"ok": True, "rama": key[0], "agrup": key[1], "categoria": key[2], "mes": key[3], **rec, "labels": labels}

    # Agua Potable: ajustar valores base según selector de conexiones (A/B/C/D)
    if norm_rama(key[0]) in ("AGUA POTABLE", "AGUA", "AGUAPOTABLE") and (conex_cat or conexiones):
        regla = match_regla_conexiones(conex_cat or conexiones)
        try:
            f = float(regla.get("factor", 1.0))
        except Exception:
            f = 1.0
        if f and f != 1.0:
            out["basico"] = _round2(out.get("basico", 0.0) * f)
            out["no_rem"] = _round2(out.get("no_rem", 0.0) * f)
            out["suma_fija"] = _round2(out.get("suma_fija", 0.0) * f)
            out["conex_cat"] = _norm(conex_cat).upper() if conex_cat else ""
            out["conexiones"] = int(conexiones or 0)

    return out


# Compat: algunos módulos históricos importan find_row().
# Devuelve el registro del maestro para (rama, agrup, categoria, mes) o None si no existe.
def find_row(rama: str, agrup: str, categoria: str, mes: str) -> Optional[Dict[str, Any]]:
    res = get_payload(rama=rama, mes=mes, agrup=agrup, categoria=categoria)
    if not isinstance(res, dict) or not res.get("ok"):
        return None
    return res

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
    sind_fijo: float = 0,
    titulo_pct: float = 0,
    zona_pct: float = 0,
    fer_no_trab: int = 0,
    fer_trab: int = 0,
    aus_inj: int = 0,
    # Horas (cantidades)
    hex50: float = 0,
    hex100: float = 0,
    hs_noct: float = 0,

    # Adicional por KM (Art. 36 Chofer/Ayudante)
    km_tipo: str = "",
    km_menos100: float = 0,
    km_mas100: float = 0,
    # Etapa 5/6: A cuenta (REM) / Viáticos (NR sin aportes)
    a_cuenta_rem: float = 0,
    viaticos_nr: float = 0,

    # Etapa 7: Manejo de Caja / Vidriera / Adelanto
    manejo_caja: bool = False,
    cajero_tipo: str = "",
    faltante_caja: float = 0,
    armado_vidriera: bool = False,
    adelanto_sueldo: float = 0,
    # Agua potable: selector A/B/C/D (impacta en básicos y NR). Se mantiene conexiones por compatibilidad.
    conex_cat: str = "",
    conexiones: int = 0,
    # Fúnebres: ids de adicionales seleccionados (coma-separados)
    fun_adic: str = "",
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
    # CALL CENTER: la categoría ya trae su jornada (20/21/24/30/34/35/36/48hs).
    # No se prorratea por selector (evita que el básico se achique al poner 20hs).
    is_call = norm_rama(rama) in ("CALL CENTER", "CALLCENTER", "CALL", "CENTRO DE LLAMADAS", "CENTRO DE LLAMADA")
    hs_cat = _extract_hs_from_categoria(categoria) if is_call else None

    if is_call and hs_cat:
        j = float(hs_cat)
        factor = 1.0
        call_to_48 = (48.0 / j) if j else 1.0
    else:
        j = float(jornada or 48)
        factor = (j / 48.0) if 48.0 else 1.0
        call_to_48 = 1.0


    bas_base = float(base.get("basico", 0.0) or 0.0)
    nr_base = float(base.get("no_rem", 0.0) or 0.0)
    sf_base = float(base.get("suma_fija", 0.0) or 0.0)

    # Agua Potable: Conexiones (A/B/C/D) NO se muestra como adicional;
    # modifica directamente el valor del Básico y de los No Rem.
    is_agua = norm_rama(rama) in ("AGUA POTABLE", "AGUA", "AGUAPOTABLE")
    if is_agua:
        nivel = _norm(conex_cat).upper() if conex_cat else ""
        info = match_regla_conexiones(nivel if nivel else conexiones)
        fac = float(info.get("factor", 1.0) or 1.0)
        if fac and fac != 1.0:
            bas_base *= fac
            nr_base *= fac
            sf_base *= fac

    bas = bas_base * factor
    nr = nr_base * factor
    sf = sf_base * factor

    # NR base total (sin derivados). Se usa también para valor-hora NR.
    nr_base_total = round2(nr + sf)

    # -------- Horas extra / nocturnas --------
    # Reglas: divisor fijo 200. Nocturnas = recargo 13,33% (1h = 1h08m).
    def _fh(x: float) -> float:
        try:
            v = float(x or 0.0)
        except Exception:
            v = 0.0
        return max(0.0, v)

    hex50_h = _fh(hex50)
    hex100_h = _fh(hex100)
    hs_noct_h = _fh(hs_noct)

    # -------- Bases NR --------
    nr_base_total = round2(nr + sf)

    # -------- Horas (extras + nocturnas) --------
    # Divisor fijo: 200 hs.
    def _h(x) -> float:
        try:
            return max(0.0, float(x or 0.0))
        except Exception:
            return 0.0

    hex50_h = _h(hex50)
    hex100_h = _h(hex100)
    hs_noct_h = _h(hs_noct)

    # -------- Adicional por KM (Art. 36) --------
    # Regla histórica (Acuerdo 26/09/1983):
    #  - Ayudante: 0,0082% (primeros 100km) sobre básico inicial Auxiliar A
    #             0,01%   (>100km)         sobre básico inicial Auxiliar Especializado A
    #  - Chofer:   0,01%   (primeros 100km) sobre básico inicial Auxiliar B
    #             0,0115% (>100km)         sobre básico inicial Auxiliar Especializado B
    #
    # El front manda:
    #   km_tipo: "AY" (Ayudante) o "CH" (Chofer)
    #   km_menos100: km dentro de los primeros 100
    #   km_mas100: km por encima de 100
    #
    # Se prorratea por jornada (factor) igual que el básico (salvo Call Center, donde factor=1).
    def _canon(s: str) -> str:
        s = _norm(s).upper()
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _basico_ref(_rama: str, _mes: str, candidates: List[str]) -> float:
        idx = _build_index()
        mes_k = _mes_to_key(_mes)
        cand_can = [_canon(c) for c in candidates]

        def _search(rama_k: str) -> float:
            # 1) match exacto
            for (r, _agr, cat, m), rec in idx.get("payload", {}).items():
                if r != rama_k or m != mes_k:
                    continue
                cat_c = _canon(cat)
                if "MENORES" in cat_c:
                    continue
                if cat_c in cand_can:
                    try:
                        return float(rec.get("basico") or 0.0)
                    except Exception:
                        return 0.0
            # 2) contiene
            for (r, _agr, cat, m), rec in idx.get("payload", {}).items():
                if r != rama_k or m != mes_k:
                    continue
                cat_c = _canon(cat)
                if "MENORES" in cat_c:
                    continue
                if any(cc in cat_c for cc in cand_can):
                    try:
                        return float(rec.get("basico") or 0.0)
                    except Exception:
                        return 0.0
            return 0.0

        r0 = _canon(_rama)
        v = _search(r0)
        if (not v) and r0 != "GENERAL":
            v = _search("GENERAL")
        return float(v or 0.0)

    km_tipo_n = _norm(km_tipo).upper()
    km_le100 = max(0.0, float(km_menos100 or 0.0))
    km_gt100 = max(0.0, float(km_mas100 or 0.0))

    # 2 renglones (<=100 y >100) para que el "Base" muestre el básico referencia correcto.
    km_rem_le = 0.0
    km_rem_gt = 0.0
    km_base_le = 0.0
    km_base_gt = 0.0

    # Turismo (CCT 547/08): adicionales por KM con valores fijos por categoría operativa (C4/C5)
    is_turismo = norm_rama(rama) == "TURISMO"
    tur_cat = None
    if is_turismo:
        if "C4" in km_tipo_n:
            tur_cat = "C4"
        elif "C5" in km_tipo_n:
            tur_cat = "C5"

    if is_turismo and tur_cat and (km_le100 or km_gt100):
        TUR_KM_RATES = {
            "C4": {
                "2026-01": {"le": 112.31, "gt": 129.16},
                "2026-02": {"le": 112.31, "gt": 129.16},
                "2026-03": {"le": 112.31, "gt": 129.16},
                "2026-04": {"le": 112.31, "gt": 129.16},
                "2026-05": {"le": 122.31, "gt": 140.66},
            },
            "C5": {
                "2026-01": {"le": 110.62, "gt": 127.21},
                "2026-02": {"le": 110.62, "gt": 127.21},
                "2026-03": {"le": 110.62, "gt": 127.21},
                "2026-04": {"le": 110.62, "gt": 127.21},
                "2026-05": {"le": 120.62, "gt": 138.71},
            },
        }

        def _pick_rate(rmap: Dict[str, Dict[str, float]], mes_k: str) -> Dict[str, float]:
            if not rmap:
                return {"le": 0.0, "gt": 0.0}
            keys = sorted(rmap.keys())
            chosen = keys[0]
            for k in keys:
                if k <= mes_k:
                    chosen = k
            return rmap.get(chosen) or {"le": 0.0, "gt": 0.0}

        mes_k = _mes_to_key(mes)
        rates = _pick_rate(TUR_KM_RATES.get(tur_cat, {}), mes_k)
        rate_le = float(rates.get("le") or 0.0)
        rate_gt = float(rates.get("gt") or 0.0)

        # En Turismo el "Base" lo mostramos como $/km (igual que en la escala).
        km_base_le = rate_le
        km_base_gt = rate_gt
        km_rem_le = round2(rate_le * km_le100) if (rate_le and km_le100) else 0.0
        km_rem_gt = round2(rate_gt * km_gt100) if (rate_gt and km_gt100) else 0.0

    elif km_tipo_n in ("AY", "AYUDANTE", "CH", "CHOFER") and (km_le100 or km_gt100):
        if km_tipo_n in ("AY", "AYUDANTE"):
            km_base_le = _basico_ref(rama, mes, ["AUXILIAR A", "AUXILIAR  A", "PERSONAL AUXILIAR A", "AUXILIAR LETRA A"])
            km_base_gt = _basico_ref(rama, mes, ["AUXILIAR ESPECIALIZADO A", "AUXILIAR  ESPECIALIZADO A"])
            # Art. 36: adicional por km recorrido (no se prorratea por jornada).
            km_rem_le = round2(km_base_le * 0.000082 * km_le100) if (km_base_le and km_le100) else 0.0
            km_rem_gt = round2(km_base_gt * 0.0001 * km_gt100) if (km_base_gt and km_gt100) else 0.0
        else:
            km_base_le = _basico_ref(rama, mes, ["AUXILIAR B", "AUXILIAR  B", "PERSONAL AUXILIAR B", "AUXILIAR LETRA B"])
            km_base_gt = _basico_ref(rama, mes, ["AUXILIAR ESPECIALIZADO B", "AUXILIAR  ESPECIALIZADO B"])
            # Art. 36: adicional por km recorrido (no se prorratea por jornada).
            km_rem_le = round2(km_base_le * 0.0001 * km_le100) if (km_base_le and km_le100) else 0.0
            km_rem_gt = round2(km_base_gt * 0.000115 * km_gt100) if (km_base_gt and km_gt100) else 0.0

    km_rem_total = round2(km_rem_le + km_rem_gt)

    DIV_HORA = 200.0
    hora_rem = (float(bas) / DIV_HORA) if bas else 0.0
    hora_nr = (float(nr_base_total) / DIV_HORA) if nr_base_total else 0.0

    hex50_rem = round2(hora_rem * 1.5 * hex50_h) if (hora_rem and hex50_h) else 0.0
    hex50_nr = round2(hora_nr * 1.5 * hex50_h) if (hora_nr and hex50_h) else 0.0
    hex100_rem = round2(hora_rem * 2.0 * hex100_h) if (hora_rem and hex100_h) else 0.0
    hex100_nr = round2(hora_nr * 2.0 * hex100_h) if (hora_nr and hex100_h) else 0.0

    # Hora nocturna: recargo 13,33% (1h nocturna = 1h 8m). Se liquida como adicional.
    NOCT_ADIC_PCT = 0.13333333333333333
    noct_rem = round2(hora_rem * NOCT_ADIC_PCT * hs_noct_h) if (hora_rem and hs_noct_h) else 0.0
    noct_nr = round2(hora_nr * NOCT_ADIC_PCT * hs_noct_h) if (hora_nr and hs_noct_h) else 0.0

    # -------- Cálculos núcleo --------
    # Remunerativos
    pct_ant = float(anios_antig or 0.0) * 0.01

    # Etapa 5/6: A cuenta (REM) / Viáticos (NR sin aportes)
    def _fpos(x) -> float:
        try:
            return max(0.0, float(x or 0.0))
        except Exception:
            return 0.0

    a_cuenta = _fpos(a_cuenta_rem)
    viaticos = _fpos(viaticos_nr)

    # Etapa 7: Manejo de Caja / Vidriera / Adelanto / Faltante
    # - Manejo de Caja (REM): A/C 12,25% sobre básico inicial Cajero A; B 48% sobre básico inicial Cajero B.
    #   Regla del sistema: el adicional se considera ANUAL, por lo que se liquida mensualmente como (importe anual / 12).
    # - Armado de vidriera (REM): 3,83% sobre básico inicial Vendedor B.
    # - Adelanto de sueldo y Faltante de caja: descuentos (no afectan bases de aportes).

    caj_tipo = str(cajero_tipo or "").strip().upper()
    manejo_caja_ok = bool(manejo_caja) and caj_tipo in ("A", "B", "C")

    caja_base = 0.0
    caja_pct = 0.0
    if manejo_caja_ok:
        if caj_tipo in ("A", "C"):
            caja_base = _basico_ref(rama, mes, ["CAJERO A", "CAJEROS A", "CAJERO  A", "CAJERO A "])
            caja_pct = 0.1225
        elif caj_tipo == "B":
            caja_base = _basico_ref(rama, mes, ["CAJERO B", "CAJEROS B", "CAJERO  B", "CAJERO B "])
            caja_pct = 0.48

    # ANUAL -> mensual (/12). Se prorratea por jornada usando factor (j/48).
    caja_rem = round2((caja_base * caja_pct * factor) / 12.0) if (caja_base and caja_pct) else 0.0
    caja_rem_os = round2((caja_base * caja_pct) / 12.0) if (caja_base and caja_pct) else 0.0

    vid_base = _basico_ref(rama, mes, ["VENDEDOR B", "Vendedor B", "VENDEDOR  B"]) if bool(armado_vidriera) else 0.0
    vid_pct = 0.0383
    vid_rem = round2(vid_base * vid_pct * factor) if (vid_base and bool(armado_vidriera)) else 0.0
    vid_rem_os = round2(vid_base * vid_pct) if (vid_base and bool(armado_vidriera)) else 0.0

    faltante = _fpos(faltante_caja)
    adelanto = _fpos(adelanto_sueldo)
    # El faltante se descuenta ÚNICAMENTE hasta el monto del adicional de Manejo de Caja.
    faltante_desc = round2(min(faltante, caja_rem)) if (faltante and caja_rem) else 0.0

    # Zona desfavorable (porcentaje sobre Básico prorrateado)
    try:
        zona_pct_f = float(zona_pct or 0.0)
    except Exception:
        zona_pct_f = 0.0
    zona_pct_f = max(0.0, zona_pct_f)
    zona = round2(bas * (zona_pct_f / 100.0)) if zona_pct_f else 0.0

    # Antigüedad: base incluye Zona (criterio del sistema para cálculos generales)
    base_ant = round2(bas + zona)
    antig = round2(base_ant * pct_ant)

    # Regla Presentismo: se pierde con 2 (dos) o más ausencias injustificadas.
    aus_dias = max(0, int(aus_inj or 0))
    presentismo_habil = (aus_dias < 2)
    # Presentismo: doceava parte de (Básico + Zona + Antigüedad + Horas + Adicionales)
    # Incluye: horas extra/nocturnas, adicional por KM y A cuenta (REM).
    base_pres = round2(bas + zona + antig + hex50_rem + hex100_rem + noct_rem + km_rem_total + caja_rem + vid_rem + a_cuenta)
    presentismo = round2(base_pres / 12.0) if presentismo_habil else 0.0

    rem_total = round2(bas + zona + presentismo + antig + hex50_rem + hex100_rem + noct_rem + km_rem_total + caja_rem + vid_rem + a_cuenta)

    # No remunerativos (NR) + derivados (Antigüedad NR / Presentismo NR)
    antig_nr = round2(nr_base_total * pct_ant) if nr_base_total else 0.0
    # Presentismo sobre NR: misma lógica que REM (12ava parte), incluyendo Antigüedad NR
    # y también horas extra/nocturnas NR.
    # Se pierde si hay 2+ ausencias injustificadas.
    base_pres_nr = round2(nr_base_total + antig_nr + hex50_nr + hex100_nr + noct_nr)
    presentismo_nr = round2(base_pres_nr / 12.0) if (base_pres_nr and presentismo_habil) else 0.0

    nr_total = round2(nr_base_total + antig_nr + presentismo_nr + hex50_nr + hex100_nr + noct_nr)

    # Viáticos (NR sin aportes): se suman al NR a pagar, pero NO integran bases de aportes
    # ni el Presentismo sobre NR.
    if viaticos:
        nr_total = round2(nr_total + viaticos)

    # -------- FUNEBRES: Adicionales (según maestro) --------
    fun_rows: List[Dict[str, Any]] = []
    if norm_rama(base["rama"]) in ("FUNEBRES", "FÚNEBRES"):
        sel_raw = (fun_adic or "").strip()
        if sel_raw:
            # IMPORTANTE: NO cortar por coma, porque algunos IDs contienen comas
            # (p.ej. "incluidos choferes"). Usamos solo ";" como separador.
            sel_ids = [s.strip() for s in sel_raw.split(";") if s.strip()]
            if sel_ids:
                defs = get_adicionales_funebres(mes)
                by_id = {str(d.get("id")): d for d in defs}
                for sid in sel_ids:
                    d = by_id.get(str(sid))
                    if not d:
                        continue
                    label = str(d.get("label") or sid)
                    tipo = str(d.get("tipo") or "").strip().lower()
                    monto = float(d.get("monto") or 0.0)
                    pct = float(d.get("pct") or 0.0)

                    val = 0.0
                    base_num = 0.0
                    if tipo in ("monto", "importe", "fijo") and monto:
                        # prorrateo por jornada
                        val = round2(monto * factor)
                    elif pct:
                        base_num = float(bas)
                        val = round2(bas * (pct / 100.0))
                    elif monto:
                        val = round2(monto * factor)

                    if val:
                        fun_rows.append({"label": label, "val": float(val), "base": float(base_num)})
                        rem_total = round2(rem_total + val)

    # -------- TURISMO: Adicional por Título --------
    # Se aplica sobre el básico (REM) y sobre el NR de $40.000 (en nuestro maestro = suma_fija).
    try:
        titulo_pct_f = float(titulo_pct or 0.0)
    except Exception:
        titulo_pct_f = 0.0
    titulo_pct_f = max(0.0, titulo_pct_f)

    titulo_rem = 0.0
    titulo_nr = 0.0
    if base["rama"] == "TURISMO" and titulo_pct_f > 0:
        titulo_rem = round2(bas * (titulo_pct_f / 100.0)) if bas else 0.0
        # Turismo: $40.000 NR corresponde a suma_fija (sf)
        titulo_nr = round2(sf * (titulo_pct_f / 100.0)) if sf else 0.0
        rem_total = round2(rem_total + titulo_rem)
        nr_total = round2(nr_total + titulo_nr)

    # -------- Feriados --------
    fer_no = max(0, int(fer_no_trab or 0))
    fer_si = max(0, int(fer_trab or 0))
    base_fer_rem = round2(bas + zona + antig)
    base_fer_nr = round2(nr_base_total + antig_nr)
    # Para mensualizados:
    # - Feriado NO trabajado: se suma la diferencia entre día feriado (1/25) y día normal incluido en el mensual (1/30).
    # - Feriado trabajado: se suma 1 día feriado (1/25).
    vdia25_rem = round2(base_fer_rem / 25.0) if base_fer_rem else 0.0
    vdia30_rem = round2(base_fer_rem / 30.0) if base_fer_rem else 0.0
    vdia25_nr = round2(base_fer_nr / 25.0) if base_fer_nr else 0.0
    vdia30_nr = round2(base_fer_nr / 30.0) if base_fer_nr else 0.0

    fer_no_rem = round2(fer_no * (vdia25_rem - vdia30_rem)) if fer_no else 0.0
    fer_si_rem = round2(fer_si * vdia25_rem) if fer_si else 0.0

    fer_no_nr = round2(fer_no * (vdia25_nr - vdia30_nr)) if fer_no else 0.0
    fer_si_nr = round2(fer_si * vdia25_nr) if fer_si else 0.0

    rem_total = round2(rem_total + fer_no_rem + fer_si_rem)
    nr_total = round2(nr_total + fer_no_nr + fer_si_nr)

    # -------- Ausencias injustificadas (descuento) --------
    base_dia_aus = round2((bas + zona + antig) / 30.0) if (bas or zona or antig) else 0.0
    aus_rem = round2(aus_dias * base_dia_aus) if aus_dias else 0.0

    # Base imponible para aportes: REM - ausencias
    rem_aportes = max(0.0, round2(rem_total - aus_rem))

    # Descuentos
    jub = round2(rem_aportes * 0.11)
    pami = round2(rem_aportes * 0.03)
    # Obra Social (OSECAC): BASE JORNADA COMPLETA (48hs), sin prorrateo por jornada.
    # Importante: no "desprorrateamos" totales, porque eso infla importes fijos (p.ej. a-cuenta).
    # Recalculamos una simulación a 48hs manteniendo el resto de parámetros (antig., zona, feriados, ausencias, etc.).
    bas_os = float(bas_base) * call_to_48  # 48hs (CALL: simula a 48). Agua: ya incluye conexiones en bas_base.
    nr_os = float(nr_base) * call_to_48
    sf_os = float(sf_base) * call_to_48

    zona_os = round2(bas_os * (zona_pct_f / 100.0)) if zona_pct_f else 0.0
    base_ant_os = round2(bas_os + zona_os)
    antig_os = round2(base_ant_os * pct_ant)
    # Horas (48hs) – mismo input de horas, con valor hora simulado a 48hs
    hora_rem_os = (float(bas_os) / DIV_HORA) if bas_os else 0.0
    # OJO: para NR, la base hora es (nr_os + sf_os)
    nr_base_total_os = round2(nr_os + sf_os)
    hora_nr_os = (float(nr_base_total_os) / DIV_HORA) if nr_base_total_os else 0.0
    hex50_rem_os = round2(hora_rem_os * 1.5 * hex50_h) if (hora_rem_os and hex50_h) else 0.0
    hex50_nr_os = round2(hora_nr_os * 1.5 * hex50_h) if (hora_nr_os and hex50_h) else 0.0
    hex100_rem_os = round2(hora_rem_os * 2.0 * hex100_h) if (hora_rem_os and hex100_h) else 0.0
    hex100_nr_os = round2(hora_nr_os * 2.0 * hex100_h) if (hora_nr_os and hex100_h) else 0.0
    noct_rem_os = round2(hora_rem_os * NOCT_ADIC_PCT * hs_noct_h) if (hora_rem_os and hs_noct_h) else 0.0
    noct_nr_os = round2(hora_nr_os * NOCT_ADIC_PCT * hs_noct_h) if (hora_nr_os and hs_noct_h) else 0.0

    # Incluye A cuenta (REM) como monto fijo (no se prorratea por la simulación a 48hs).
    base_pres_os = round2(bas_os + zona_os + antig_os + hex50_rem_os + hex100_rem_os + noct_rem_os + km_rem_total + caja_rem_os + vid_rem_os + a_cuenta)
    presentismo_os = round2(base_pres_os / 12.0) if presentismo_habil else 0.0
    rem_total_os = round2(bas_os + zona_os + antig_os + presentismo_os + hex50_rem_os + hex100_rem_os + noct_rem_os + km_rem_total + caja_rem_os + vid_rem_os + a_cuenta)

    antig_nr_os = round2(nr_base_total_os * pct_ant) if nr_base_total_os else 0.0
    presentismo_nr_os = (
        round2((nr_base_total_os + antig_nr_os + hex50_nr_os + hex100_nr_os + noct_nr_os) / 12.0)
        if (nr_base_total_os and presentismo_habil)
        else 0.0
    )
    nr_total_os = round2(nr_base_total_os + antig_nr_os + presentismo_nr_os + hex50_nr_os + hex100_nr_os + noct_nr_os)

    # FUNEBRES: adicionales (48hs)
    if norm_rama(base["rama"]) in ("FUNEBRES", "FÚNEBRES"):
        sel_raw = (fun_adic or "").strip()
        if sel_raw:
            sel_ids = [s.strip() for s in sel_raw.split(";") if s.strip()]
            if sel_ids:
                defs = get_adicionales_funebres(mes)
                by_id = {str(d.get("id")): d for d in defs}
                for sid in sel_ids:
                    d = by_id.get(str(sid))
                    if not d:
                        continue
                    tipo = str(d.get("tipo") or "").strip().lower()
                    monto = float(d.get("monto") or 0.0)
                    pct = float(d.get("pct") or 0.0)
                    val = 0.0
                    if tipo in ("monto", "importe", "fijo") and monto:
                        val = round2(monto)  # 48hs
                    elif pct:
                        val = round2(bas_os * (pct / 100.0))
                    elif monto:
                        val = round2(monto)
                    if val:
                        rem_total_os = round2(rem_total_os + val)

    # TURISMO: adicional por título (48hs)
    if base["rama"] == "TURISMO" and titulo_pct_f > 0:
        titulo_rem_os = round2(bas_os * (titulo_pct_f / 100.0)) if bas_os else 0.0
        titulo_nr_os = round2(sf_os * (titulo_pct_f / 100.0)) if sf_os else 0.0
        rem_total_os = round2(rem_total_os + titulo_rem_os)
        nr_total_os = round2(nr_total_os + titulo_nr_os)

    # Feriados (48hs)
    base_fer_rem_os = round2(bas_os + zona_os + antig_os)
    base_fer_nr_os = round2(nr_base_total_os + antig_nr_os)
    vdia25_rem_os = round2(base_fer_rem_os / 25.0) if base_fer_rem_os else 0.0
    vdia30_rem_os = round2(base_fer_rem_os / 30.0) if base_fer_rem_os else 0.0
    vdia25_nr_os = round2(base_fer_nr_os / 25.0) if base_fer_nr_os else 0.0
    vdia30_nr_os = round2(base_fer_nr_os / 30.0) if base_fer_nr_os else 0.0

    fer_no_rem_os = round2(fer_no * (vdia25_rem_os - vdia30_rem_os)) if fer_no else 0.0
    fer_si_rem_os = round2(fer_si * vdia25_rem_os) if fer_si else 0.0
    fer_no_nr_os = round2(fer_no * (vdia25_nr_os - vdia30_nr_os)) if fer_no else 0.0
    fer_si_nr_os = round2(fer_si * vdia25_nr_os) if fer_si else 0.0

    rem_total_os = round2(rem_total_os + fer_no_rem_os + fer_si_rem_os)
    nr_total_os = round2(nr_total_os + fer_no_nr_os + fer_si_nr_os)

    # Ausencias (48hs)
    base_dia_aus_os = round2((bas_os + zona_os + antig_os) / 30.0) if (bas_os or zona_os or antig_os) else 0.0
    aus_rem_os = round2(aus_dias * base_dia_aus_os) if aus_dias else 0.0
    rem_aportes_os = max(0.0, round2(rem_total_os - aus_rem_os))

    os_base = round2((rem_aportes_os + nr_total_os) if bool(osecac) else rem_aportes_os)
    os_aporte = round2(os_base * 0.03) if bool(osecac) else 0.0
    osecac_100 = 100.0 if bool(osecac) else 0.0

    # Base para aportes porcentuales (Sindicato/FAECYS, etc.): excluye viáticos NR sin aportes.
    nr_aportable_real = max(0.0, round2(nr_total - (viaticos or 0.0)))

    sind = 0.0
    sind_fijo_monto = 0.0
    if bool(afiliado):
        try:
            sp = float(sind_pct or 0.0)
        except Exception:
            sp = 0.0
        if sp > 0:
            sind = round2((rem_aportes + nr_aportable_real) * (sp / 100.0))

        # Monto fijo de sindicato (se aplica SOLO si está afiliado).
        try:
            sind_fijo_monto = round2(max(0.0, float(sind_fijo or 0.0)))
        except Exception:
            sind_fijo_monto = 0.0

    ded_total = round2(jub + pami + os_aporte + osecac_100 + sind + sind_fijo_monto + aus_rem + faltante_desc + adelanto)
    neto = round2((rem_total + nr_total) - ded_total)

    def item(concepto: str, r: float = 0.0, n: float = 0.0, d: float = 0.0, base_num: float = 0.0) -> Dict[str, Any]:
        out = {"concepto": concepto, "r": float(r), "n": float(n), "d": float(d)}
        if base_num:
            out["base"] = float(base_num)
        return out

    items: List[Dict[str, Any]] = [item("Básico", r=bas, base_num=bas)]

    if zona:
        items.append(item("Zona desfavorable", r=zona, base_num=bas))

    if antig:
        items.append(item("Antigüedad", r=antig, base_num=base_ant))

    # Horas extra / nocturnas (2 filas o 4 si hay NR)
    if hex50_rem:
        items.append(item("Horas extra 50% (Rem)", r=hex50_rem, base_num=hora_rem))
    if hex50_nr:
        items.append(item("Horas extra 50% (NR)", n=hex50_nr, base_num=hora_nr))
    if hex100_rem:
        items.append(item("Horas extra 100% (Rem)", r=hex100_rem, base_num=hora_rem))
    if hex100_nr:
        items.append(item("Horas extra 100% (NR)", n=hex100_nr, base_num=hora_nr))
    if noct_rem:
        items.append(item("Horas nocturnas (Rem)", r=noct_rem, base_num=hora_rem))
    if noct_nr:
        items.append(item("Horas nocturnas (NR)", n=noct_nr, base_num=hora_nr))

    # Adicional por KM — 2 filas (<=100 / >100)
    if km_rem_le:
        if is_turismo and tur_cat:
            items.append(item(f'Adicional por KM (Turismo - Operativo {tur_cat}) ≤100 km ({km_le100:g} km)', r=km_rem_le, base_num=km_base_le))
        else:
            tipo_txt = 'Ayudante' if km_tipo_n in ('AY','AYUDANTE') else 'Chofer'
            items.append(item(f'Adicional por KM (Art. 36 - {tipo_txt}) ≤100 km ({km_le100:g} km)', r=km_rem_le, base_num=km_base_le))
    if km_rem_gt:
        if is_turismo and tur_cat:
            items.append(item(f'Adicional por KM (Turismo - Operativo {tur_cat}) >100 km ({km_gt100:g} km)', r=km_rem_gt, base_num=km_base_gt))
        else:
            tipo_txt = 'Ayudante' if km_tipo_n in ('AY','AYUDANTE') else 'Chofer'
            items.append(item(f'Adicional por KM (Art. 36 - {tipo_txt}) >100 km ({km_gt100:g} km)', r=km_rem_gt, base_num=km_base_gt))

    # Manejo de Caja (REM)
    if caja_rem:
        lbl_tipo = "Cajero B" if caj_tipo == "B" else "Cajero A/C"
        lbl_pct = "48%" if caj_tipo == "B" else "12,25%"
        items.append(item(
            f"Manejo de Caja ({lbl_tipo}) {lbl_pct}",
            r=caja_rem,
            base_num=caja_base,
        ))

    # Armado de vidriera (REM)
    if vid_rem:
        items.append(item(
            "Armado de vidriera (Art. 23) 3,83%",
            r=vid_rem,
            base_num=vid_base,
        ))

    # A cuenta futuros aumentos (REM)
    if a_cuenta:
        items.append(item(
            "A cuenta futuros aumentos (REM)",
            r=a_cuenta,
        ))

    # Presentismo: si se pierde por 2+ ausencias injustificadas, NO se muestra la fila (pedido César).
    if presentismo_habil and presentismo:
        items.append(item(
            "Presentismo",
            r=presentismo,
            base_num=base_pres,
        ))

    # Fúnebres: adicionales seleccionados (según maestro)
    if fun_rows:
        for fr in fun_rows:
            items.append(item(
                str(fr.get("label") or "Adicional"),
                r=float(fr.get("val") or 0.0),
                base_num=float(fr.get("base") or 0.0),
            ))



    # -------- Etapa 12: Mostrar adicionales (Turismo Título / Agua Conexiones) --------
    if titulo_rem:
        items.append(item(
            'Adicional por Título',
            r=titulo_rem,
            base_num=bas,
        ))
    if titulo_nr:
        items.append(item(
            'Adicional por Título (NR)',
            n=titulo_nr,
            base_num=sf,
        ))

    # Conexiones (Agua Potable): no se agrega fila, porque el selector modifica el básico y los NR.
    # Feriados (REM)
    if fer_no_rem:
        items.append(item(
            f"Feriado no trabajado ({fer_no} día{'s' if fer_no != 1 else ''})",
            r=fer_no_rem,
            base_num=base_fer_rem,
        ))
    if fer_si_rem:
        items.append(item(
            f"Feriado trabajado ({fer_si} día{'s' if fer_si != 1 else ''})",
            r=fer_si_rem,
            base_num=base_fer_rem,
        ))

    labels = _nr_labels(base["rama"])

    if nr:
        items.append(item(labels.get("no_rem", "No Remunerativo"), n=nr))
    if sf:
        items.append(item(labels.get("suma_fija", "Suma Fija (NR)"), n=sf))

    # Viáticos (NR sin aportes)
    if viaticos:
        items.append(item(
            "Viáticos (NR sin aportes)",
            n=viaticos,
        ))

    # Derivados sobre NR (desglosado como filas NR)
    if antig_nr:
        items.append(item("Antigüedad (NR)", n=antig_nr, base_num=nr_base_total))
    # Presentismo sobre NR: si se pierde por 2+ ausencias injustificadas, NO se muestra la fila.
    if presentismo_habil and presentismo_nr:
        items.append(item(
            "Presentismo (NR)",
            n=presentismo_nr,
            base_num=base_pres_nr,
        ))

    # Feriados (NR)
    if fer_no_nr:
        items.append(item(
            f"Feriado no trabajado (NR) ({fer_no} día{'s' if fer_no != 1 else ''})",
            n=fer_no_nr,
            base_num=base_fer_nr,
        ))
    if fer_si_nr:
        items.append(item(
            f"Feriado trabajado (NR) ({fer_si} día{'s' if fer_si != 1 else ''})",
            n=fer_si_nr,
            base_num=base_fer_nr,
        ))

    # Ausencias injustificadas (descuento) – reduce bases de aportes vía rem_aportes
    if aus_rem:
        items.append(item(
            f"Ausencias injustificadas ({aus_dias} día{'s' if aus_dias != 1 else ''})",
            d=aus_rem,
            base_num=base_dia_aus,
        ))

    if faltante_desc:
        items.append(item(
            "Faltante de caja (desc.)",
            d=faltante_desc,
            base_num=caja_rem,
        ))

    if adelanto:
        items.append(item(
            "Adelanto de sueldo",
            d=adelanto,
        ))

    items.append(item("Jubilación 11%", d=jub, base_num=rem_aportes))
    items.append(item("Ley 19.032 (PAMI) 3%", d=pami, base_num=rem_aportes))

    if bool(osecac):
        items.append(item("Obra Social 3%", d=os_aporte, base_num=os_base))
        items.append(item("OSECAC $100", d=osecac_100))
    else:
        items.append(item("Obra Social 3%", d=0.0, base_num=os_base))

    if sind:
        items.append(item(f"Sindicato {float(sind_pct):g}%", d=sind, base_num=(rem_aportes + nr_aportable_real)))
    if sind_fijo_monto:
        items.append(item("Sindicato (fijo)", d=sind_fijo_monto))

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
        "sind_fijo": float(sind_fijo or 0),
        "titulo_pct": float(titulo_pct or 0),
        "zona_pct": float(zona_pct_f),

        "labels": labels,

        "basico_base": float(bas_base),
        "no_rem_base": float(nr_base),
        "suma_fija_base": float(sf_base),

        "basico": float(bas),
        "zona": float(zona),
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
    """Adicionales de Fúnebres.

    - Si existe definición exacta para el mes, se usa esa.
    - Si no existe, se toma la última definición anterior (prórroga automática).
      Esto permite, por ejemplo, que si el maestro quedó hasta 2026-01, en
      2026-02/03/04 se sigan ofreciendo los mismos adicionales.
    """
    idx = _build_index()
    mes_k = _mes_to_key(mes)

    d = idx.get("funebres_adic", {})
    if mes_k in d:
        return list(d.get(mes_k, []))

    # fallback: última definición <= mes_k
    keys = [k for k in d.keys() if isinstance(k, str) and k <= mes_k]
    if not keys:
        return []
    best = max(keys)
    return list(d.get(best, []))

def match_regla_conexiones(conexiones_o_nivel) -> Dict[str, Any]:
    """
    Agua Potable: reglas por umbrales (según tu UI):
    A: hasta 500
    B: 501-1000
    C: 1001-1600
    D: más de 1600
    El % es 7% encadenado (A=0%, B=7%, C=14,49%, D=22,5043%).
    """
    # Soporta dos entradas:
    # 1) cantidad (int) -> determina A/B/C/D por umbral
    # 2) nivel directo ("A"/"B"/"C"/"D") -> usa ese nivel
    level = 0
    cat = None
    label = None
    if isinstance(conexiones_o_nivel, str) and conexiones_o_nivel.strip():
        c = _norm(conexiones_o_nivel).upper()
        if c in ["A", "B", "C", "D"]:
            cat = c
            level = {"A": 0, "B": 1, "C": 2, "D": 3}[c]
            label = {
                "A": "A (hasta 500)",
                "B": "B (+7% s/A)",
                "C": "C (+7% s/B)",
                "D": "D (+7% s/C)",
            }[c]
        else:
            # Si viene un texto no esperado, intentamos tratarlo como número
            try:
                conexiones_o_nivel = int(c)
            except Exception:
                conexiones_o_nivel = 0

    if cat is None:
        try:
            n = int(conexiones_o_nivel)
        except Exception:
            n = 0
        if n <= 0:
            return {"cat": None, "pct": 0.0, "factor": 1.0, "label": None}

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

    factor = 1.07 ** level
    pct = factor - 1.0  # level 0 => 0
    return {"cat": cat, "pct": pct, "factor": factor, "label": label}

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
