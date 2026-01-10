
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MAESTRO_PATH = BASE_DIR / "maestro.xlsx"

# Ramas "oficiales" que queremos siempre presentes en /meta (aunque el Excel venga incompleto)
FORCED_RAMAS = ["GENERAL", "TURISMO", "CEREALES", "CALL CENTER", "AGUA POTABLE", "FUNEBRES"]
INVALID_RAMAS = {"MES - AÑO", "MES", "AÑO", "ANO"}


def _to_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _looks_like_date_or_number(v: Any) -> bool:
    # Filtra datetime/date y también strings que se parsean como fechas tipo "2025-12-01 00:00:00"
    if v is None:
        return True
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, (datetime.date, datetime.datetime)):
        return True
    s = _to_str(v)
    if not s:
        return True
    # YYYY-MM o YYYY-MM-DD (con o sin hora)
    if re.match(r"^\d{4}-\d{2}(-\d{2})?(\s+\d{2}:\d{2}:\d{2})?$", s):
        return True
    # dd/mm/aaaa
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", s):
        return True
    return False


def _norm_rama(rama: str) -> str:
    s = _to_str(rama).upper()
    # Normalizaciones típicas
    s = s.replace("CENTRO DE LLAMADAS", "CALL CENTER")
    s = s.replace("CALLCENTER", "CALL CENTER")
    s = s.replace("FÚNEBRES", "FUNEBRES")
    s = s.replace("AGUA POTABLE", "AGUA POTABLE")
    return s


@dataclass(frozen=True)
class ScaleRow:
    rama: str
    agrup: str
    categoria: str
    mes: str  # YYYY-MM
    basico: float
    no_rem: float
    suma_fija: float


@lru_cache(maxsize=2)
def _load_rows(maestro_path: str) -> List[ScaleRow]:
    path = Path(maestro_path) if maestro_path else DEFAULT_MAESTRO_PATH
    wb = load_workbook(path, data_only=True)

    rows: List[ScaleRow] = []

    for name in wb.sheetnames:
        if not name.startswith("Categorias_"):
            continue
        ws = wb[name]

        # Cabecera esperada en fila 1:
        # Rama | Agrupamiento | Categoria | Mes | Basico | No Remunerativo | SUMA_FIJA
        # Pero Funebres viene sin "Categoria" y usa Agrupamiento como categoria.
        for r in range(2, ws.max_row + 1):
            rama = ws.cell(r, 1).value
            if rama is None:
                continue

            rama_s = _norm_rama(rama)
            agrup = _to_str(ws.cell(r, 2).value)
            cat = _to_str(ws.cell(r, 3).value)
            mes = _to_str(ws.cell(r, 4).value)

            basico = ws.cell(r, 5).value
            no_rem = ws.cell(r, 6).value
            suma_fija = ws.cell(r, 7).value

            # Limpieza mínima
            if not mes:
                continue
            # Si el mes viene como datetime, convertir a YYYY-MM
            if isinstance(ws.cell(r, 4).value, (datetime.date, datetime.datetime)):
                dt = ws.cell(r, 4).value
                mes = f"{dt.year:04d}-{dt.month:02d}"

            # Funebres: categoria vacía -> usar agrup como categoria y agrup = "—"
            if not cat and rama_s in {"FUNEBRES", "FÚNEBRES"}:
                cat = agrup or "—"
                agrup = "—"

            # Si la RAMA vino corrupta (fecha/número), la ignoramos.
            if _looks_like_date_or_number(rama):
                continue
            if not rama_s:
                continue
            if rama_s in INVALID_RAMAS:
                continue

            def _num(x: Any) -> float:
                try:
                    return float(x or 0)
                except Exception:
                    return 0.0

            rows.append(
                ScaleRow(
                    rama=rama_s,
                    agrup=agrup or "—",
                    categoria=cat or "—",
                    mes=mes[:7],  # YYYY-MM
                    basico=_num(basico),
                    no_rem=_num(no_rem),
                    suma_fija=_num(suma_fija),
                )
            )

    return rows


def get_meta(maestro_path: str | None = None) -> Dict[str, Any]:
    rows = _load_rows(maestro_path or str(DEFAULT_MAESTRO_PATH))

    ramas_set = {_norm_rama(r.rama) for r in rows if r.rama and not _looks_like_date_or_number(r.rama)}
    for forced in FORCED_RAMAS:
        ramas_set.add(forced)

    ramas = sorted(ramas_set)

    meses = sorted({r.mes for r in rows if r.mes})

    # Agrupamientos por rama
    agrup_por_rama: Dict[str, List[str]] = {}
    cat_por_rama_agrup: Dict[str, Dict[str, List[str]]] = {}

    for r in rows:
        if not r.rama:
            continue
        agrup_por_rama.setdefault(r.rama, set()).add(r.agrup)
        cat_por_rama_agrup.setdefault(r.rama, {}).setdefault(r.agrup, set()).add(r.categoria)

    # Convert sets -> sorted lists
    agrup_por_rama_out: Dict[str, List[str]] = {k: sorted(list(v)) for k, v in agrup_por_rama.items()}
    cat_por_rama_agrup_out: Dict[str, Dict[str, List[str]]] = {}
    for rama, d in cat_por_rama_agrup.items():
        cat_por_rama_agrup_out[rama] = {agr: sorted(list(cats)) for agr, cats in d.items()}

    return {
        "ramas": ramas,
        "meses": meses,
        "agrupamientos": agrup_por_rama_out,
        "categorias": cat_por_rama_agrup_out,
    }


def find_row(
    rama: str,
    agrup: str,
    categoria: str,
    mes: str,
    maestro_path: str | None = None
) -> Optional[ScaleRow]:
    rows = _load_rows(maestro_path or str(DEFAULT_MAESTRO_PATH))
    rama = _norm_rama(rama)
    mes = (mes or "")[:7]
    agrup = _to_str(agrup) or "—"
    categoria = _to_str(categoria) or "—"

    # Tomamos la ÚLTIMA ocurrencia en el Excel (por si hay duplicados).
    found: Optional[ScaleRow] = None
    for r in rows:
        if r.rama == rama and r.mes == mes and r.agrup == agrup and r.categoria == categoria:
            found = r
    return found


def get_payload(rama: str, agrup: str, categoria: str, mes: str, maestro_path: str | None = None) -> Dict[str, Any]:
    row = find_row(rama=rama, agrup=agrup, categoria=categoria, mes=mes, maestro_path=maestro_path)
    if not row:
        return {
            "ok": False,
            "error": "No se encontró esa combinación en el maestro",
            "rama": rama,
            "agrup": agrup,
            "categoria": categoria,
            "mes": mes,
        }
    return {
        "ok": True,
        "rama": row.rama,
        "agrup": row.agrup,
        "categoria": row.categoria,
        "mes": row.mes,
        "basico": row.basico,
        "no_rem": row.no_rem,
        "suma_fija": row.suma_fija,
    }


# Compatibilidad con nombres viejos (por si algún main.py importaba esto)
load_meta = get_meta
