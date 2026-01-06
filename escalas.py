from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl


MAESTRO_PATH = Path(__file__).with_name("maestro.xlsx")


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


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return 0.0
    # allow "1.234.567,89"
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _norm_mes(x: Any) -> str:
    # expects already like "2026-01" or datetime/date
    if x is None:
        return ""
    if hasattr(x, "strftime"):
        return x.strftime("%Y-%m")
    s = str(x).strip()
    # allow "2026-01-01" -> "2026-01"
    if len(s) >= 7 and s[4] == "-" and s[6].isdigit():
        return s[:7]
    return s


def _load_payload() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    if not MAESTRO_PATH.exists():
        raise FileNotFoundError(f"No se encontró maestro.xlsx en {MAESTRO_PATH}")

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
        # headers in row 1: Rama, Agrupamiento, Categoria, Mes, Basico, No Remunerativo, SUMA_FIJA
        for r in range(2, ws.max_row + 1):
            rama = ws.cell(r, 1).value
            if not rama:
                continue
            rama = str(rama).strip()
            agrup = str(ws.cell(r, 2).value or "—").strip()
            categoria = str(ws.cell(r, 3).value or "").strip()
            mes = _norm_mes(ws.cell(r, 4).value)
            basico = _to_float(ws.cell(r, 5).value)
            nr1 = _to_float(ws.cell(r, 6).value)
            nr2 = _to_float(ws.cell(r, 7).value)

            if not categoria or not mes:
                continue

            ramas.add(rama)
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

    ramas_sorted = sorted(ramas)
    meses_sorted = sorted(meses)

    # IMPORTANT: the current frontend builds <select> options using Object.keys(...).
    # If we return lists, Object.keys returns "0..N" and the UI shows numbers.
    # So we return dictionaries whose keys are the labels.
    ramas_dict = {r: True for r in ramas_sorted}
    meses_dict = {m: True for m in meses_sorted}

    agrupamientos_dict: Dict[str, Dict[str, bool]] = {}
    categorias_dict: Dict[str, Dict[str, bool]] = {}
    for r in ramas_sorted:
        agrups = sorted(list(agrups_by_rama.get(r, set())))
        agrupamientos_dict[r] = {a: True for a in agrups}
        for a in agrups:
            cats = sorted(list(cats_by_rama_agrup.get((r, a), set())))
            categorias_dict[f"{r}||{a}"] = {c: True for c in cats}

    meta = {
        # Used by the frontend (Object.keys)
        "ramas": ramas_dict,
        "meses": meses_dict,
        "agrupamientos": agrupamientos_dict,
        "categorias": categorias_dict,

        # Debug / compatibility (in case you want arrays later)
        "ramas_list": ramas_sorted,
        "meses_list": meses_sorted,
        "filas": len(rows),
        "fuente": "maestro.xlsx",
    }

    _CACHE = {"meta": meta, "rows": rows}
    return _CACHE


def get_meta() -> Dict[str, Any]:
    return _load_payload()["meta"]


def get_payload() -> Dict[str, Any]:
    # Keep a stable key name for the frontend
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
