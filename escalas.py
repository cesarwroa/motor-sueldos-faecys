from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os
import re
import datetime as dt

import openpyxl


# Permite override en Render / Docker:
# export MAESTRO_PATH=/app/maestro.xlsx
_DEFAULT = Path(__file__).with_name("maestro.xlsx")
MAESTRO_PATH = Path(os.getenv("MAESTRO_PATH", str(_DEFAULT)))


@dataclass(frozen=True)
class Row:
    rama: str
    agrup: str
    categoria: str
    mes: str  # "YYYY-MM"
    basico: float
    no_rem_1: float
    no_rem_2: float


_CACHE: Optional[Dict[str, Any]] = None


def clear_cache() -> None:
    global _CACHE
    _CACHE = None


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    # allow "1.234.567,89" / "3.208.680"
    s = s.replace("$", "").replace(" ", "")
    # 1.234.567,89 -> 1234567.89
    if s.count(",") == 1 and s.count(".") >= 1:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 0 and s.count(".") >= 1:
        # 3.208.680 -> 3208680
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _norm_mes(x: Any) -> str:
    """Devuelve 'YYYY-MM' o '' si no puede."""
    if x is None:
        return ""
    if isinstance(x, (dt.datetime, dt.date)):
        return x.strftime("%Y-%m")
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        # Evitar '180000' u otros numéricos mal ubicados
        return ""
    s = str(x).strip()
    if not s:
        return ""
    # allow "2026-01-01" -> "2026-01"
    if len(s) >= 7 and s[0:4].isdigit() and s[4] in "-/" and s[5:7].isdigit():
        return f"{s[0:4]}-{s[5:7]}"
    # intento extra: datetime string
    m = re.match(r"^(\d{4})[-/](\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return ""


def _norm_rama_from_sheet(sheet_name: str) -> str:
    rama = sheet_name.replace("Categorias_", "").replace("_", " ").strip().upper()
    # Normalizaciones frecuentes
    rama = rama.replace("FÚNEBRES", "FUNEBRES")
    return rama


def _is_standard_tabular_sheet(ws: openpyxl.worksheet.worksheet.Worksheet) -> bool:
    a1 = str(ws.cell(1, 1).value or "").strip().lower()
    b1 = str(ws.cell(1, 2).value or "").strip().lower()
    c1 = str(ws.cell(1, 3).value or "").strip().lower()
    d1 = str(ws.cell(1, 4).value or "").strip().lower()
    # Formato esperado:
    # Rama | Agrupamiento | Categoria | Mes | Basico | ...
    return a1 == "rama" and "agrup" in b1 and "categ" in c1 and d1.startswith("mes")


def _scan_meses_in_sheet(ws: openpyxl.worksheet.worksheet.Worksheet) -> set[str]:
    """Extrae meses detectando fechas en col A."""
    meses: set[str] = set()
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, (dt.datetime, dt.date)):
            meses.add(v.strftime("%Y-%m"))
        else:
            s = str(v).strip() if v is not None else ""
            m = re.match(r"^(\d{4})[-/](\d{2})", s)
            if m:
                meses.add(f"{m.group(1)}-{m.group(2)}")
    return meses


def _parse_agua_potable(ws: openpyxl.worksheet.worksheet.Worksheet, rama: str) -> Tuple[List[Dict[str, Any]], set[str], Dict[str, set[str]], Dict[Tuple[str,str], set[str]]]:
    """
    Formato por bloques:
      - 'AGRUPAMIENTO: ...'
      - 'Categoría: ...'
      - fila encabezado con 'MES - AÑO'
      - filas con fecha en col A, básico en col B, NR1 col C, NR2 col D
    """
    rows: List[Dict[str, Any]] = []
    meses: set[str] = set()
    agrups_by_rama: Dict[str, set[str]] = {rama: set()}
    cats_by_rama_agrup: Dict[Tuple[str,str], set[str]] = {}

    agrup_actual = "—"
    cat_actual = ""

    # buscar header "MES - AÑO"
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        a_s = str(a).strip() if a is not None else ""

        if a_s.upper().startswith("AGRUPAMIENTO"):
            # "AGRUPAMIENTO: XXX"
            agrup_actual = a_s.split(":", 1)[1].strip() if ":" in a_s else a_s.strip()
            if not agrup_actual:
                agrup_actual = "—"
            continue

        if a_s.upper().startswith("CATEGOR"):
            cat_actual = a_s.split(":", 1)[1].strip() if ":" in a_s else a_s.strip()
            continue

        if a_s.upper().startswith("MES"):
            # parse data rows until next non-date
            rr = r + 1
            while rr <= ws.max_row:
                v = ws.cell(rr, 1).value
                if not isinstance(v, (dt.datetime, dt.date)):
                    break
                mes = v.strftime("%Y-%m")
                basico = _to_float(ws.cell(rr, 2).value)
                nr1 = _to_float(ws.cell(rr, 3).value)
                nr2 = _to_float(ws.cell(rr, 4).value)

                if cat_actual:
                    agrups_by_rama.setdefault(rama, set()).add(agrup_actual)
                    cats_by_rama_agrup.setdefault((rama, agrup_actual), set()).add(cat_actual)
                    meses.add(mes)
                    rows.append({
                        "rama": rama,
                        "agrup": agrup_actual,
                        "categoria": cat_actual,
                        "mes": mes,
                        "basico": basico,
                        "no_rem_1": nr1,
                        "no_rem_2": nr2,
                    })
                rr += 1
            continue

    return rows, meses, agrups_by_rama, cats_by_rama_agrup


def _load_payload() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    if not MAESTRO_PATH.exists():
        raise FileNotFoundError(f"No se encontró el maestro en {MAESTRO_PATH}")

    wb = openpyxl.load_workbook(MAESTRO_PATH, data_only=True)

    rows: List[Dict[str, Any]] = []
    ramas: set[str] = set()
    agrups_by_rama: Dict[str, set[str]] = {}
    cats_by_rama_agrup: Dict[Tuple[str, str], set[str]] = {}
    meses: set[str] = set()

    for name in wb.sheetnames:
        if not name.startswith("Categorias_"):
            continue

        ws = wb[name]
        rama_sheet = _norm_rama_from_sheet(name)
        ramas.add(rama_sheet)

        # Agua Potable: parsear su formato por bloques
        if rama_sheet == "AGUA POTABLE":
            ap_rows, ap_meses, ap_agr, ap_cats = _parse_agua_potable(ws, rama_sheet)
            rows.extend(ap_rows)
            meses |= ap_meses
            for k,v in ap_agr.items():
                agrups_by_rama.setdefault(k, set()).update(v)
            for k,v in ap_cats.items():
                cats_by_rama_agrup.setdefault(k, set()).update(v)
            continue

        # Hojas tabulares estándar
        if not _is_standard_tabular_sheet(ws):
            meses |= _scan_meses_in_sheet(ws)
            continue

        for r in range(2, ws.max_row + 1):
            rama = rama_sheet  # siempre desde el nombre de hoja (robusto a celdas combinadas)

            agrup = str(ws.cell(r, 2).value or "—").strip()
            categoria = str(ws.cell(r, 3).value or "").strip()
            mes = _norm_mes(ws.cell(r, 4).value)

            basico = _to_float(ws.cell(r, 5).value)
            nr1 = _to_float(ws.cell(r, 6).value)
            nr2 = _to_float(ws.cell(r, 7).value)

            # Fallback: si Categoria viene vacía, usar el texto del agrupamiento como categoría
            if (not categoria) and agrup and agrup != "—":
                categoria = agrup
                agrup = "—"

            if not categoria or not mes:
                continue

            agrups_by_rama.setdefault(rama, set()).add(agrup)
            cats_by_rama_agrup.setdefault((rama, agrup), set()).add(categoria)
            meses.add(mes)

            rows.append(
                {
                    "rama": rama,
                    "agrup": agrup,
                    "categoria": categoria,
                    "mes": mes,
                    "basico": basico,
                    "no_rem_1": nr1,
                    "no_rem_2": nr2,
                }
            )

    # Orden y “limpieza” de ramas
    desired = ["GENERAL", "TURISMO", "CEREALES", "CALL CENTER", "AGUA POTABLE", "FUNEBRES"]
    ramas_sorted: List[str] = [r for r in desired if r in ramas] + sorted(ramas - set(desired))
    meses_sorted = sorted(meses)

    # Compat (Object.keys)
    ramas_dict = {r: True for r in ramas_sorted}
    meses_dict = {m: True for m in meses_sorted}

    # Estructuras para selects
    agrupamientos: Dict[str, List[str]] = {}
    categorias: Dict[str, List[str]] = {}

    agrupamientos_dict: Dict[str, Dict[str, bool]] = {}
    categorias_dict: Dict[str, Dict[str, bool]] = {}

    for r in ramas_sorted:
        agrups = sorted(list(agrups_by_rama.get(r, set()))) or ["—"]
        agrupamientos[r] = agrups
        agrupamientos_dict[r] = {a: True for a in agrups}

        for a in agrups:
            cats = sorted(list(cats_by_rama_agrup.get((r, a), set())))
            categorias[f"{r}||{a}"] = cats
            categorias_dict[f"{r}||{a}"] = {c: True for c in cats}

    meta = {
        "ramas": ramas_sorted,
        "meses": meses_sorted,
        "agrupamientos": agrupamientos,
        "categorias": categorias,
        "ramas_dict": ramas_dict,
        "meses_dict": meses_dict,
        "agrupamientos_dict": agrupamientos_dict,
        "categorias_dict": categorias_dict,
        "filas": len(rows),
        "fuente": str(MAESTRO_PATH.name),
    }

    _CACHE = {"meta": meta, "rows": rows}
    return _CACHE


def get_meta() -> Dict[str, Any]:
    return _load_payload()["meta"]


def get_payload() -> Dict[str, Any]:
    data = _load_payload()
    return {"rows": data["rows"]}


def find_row(rama: str, agrup: str, categoria: str, mes: str) -> Optional[Dict[str, Any]]:
    data = _load_payload()["rows"]
    for row in data:
        if (
            row["rama"] == rama
            and row["agrup"] == agrup
            and row["categoria"] == categoria
            and row["mes"] == mes
        ):
            return row
    return None
