"""
Generador de meta/payload a partir del maestro XLSX.
- get_meta(): estructura liviana para poblar selects (rama/agrup/categoría).
- get_payload(): por ahora retorna meta + info de versión (sirve como base para expandir).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

MAESTRO_PATH = Path(__file__).resolve().parent / "maestro.xlsx"

def _build_meta_from_maestro(xlsx_path: Path) -> dict:
    xl = pd.ExcelFile(xlsx_path)
    ramas=set()
    agrups={}
    cats={}

    for s in [sn for sn in xl.sheet_names if sn.startswith("Categorias_") and sn!="Categorias_Agua_Potable"]:
        df = pd.read_excel(xlsx_path, sheet_name=s)
        # columnas esperadas: Rama, Agrupamiento, Categoria
        if not set(["Rama","Agrupamiento","Categoria"]).issubset(df.columns):
            continue
        df = df.dropna(subset=["Rama","Agrupamiento","Categoria"])
        for _, r in df.iterrows():
            rama = str(r["Rama"]).strip()
            agrup = str(r["Agrupamiento"]).strip() or "—"
            cat = str(r["Categoria"]).strip()
            if not rama or not cat:
                continue
            ramas.add(rama)
            agrups.setdefault(rama,set()).add(agrup)
            cats.setdefault(rama,{}).setdefault(agrup,set()).add(cat)

    # Agua Potable: hoja con formato no tabular
    if "Categorias_Agua_Potable" in xl.sheet_names:
        df_ap = pd.read_excel(xlsx_path, sheet_name="Categorias_Agua_Potable", header=None)
        if 0 in df_ap.columns:
            col0 = df_ap[0].dropna().astype(str)
            ap_cats = sorted(set([x.replace("Categoría:","").strip() for x in col0[col0.str.startswith("Categoría")]]))
            if ap_cats:
                rama = "AGUA POTABLE"
                ramas.add(rama)
                agrups.setdefault(rama,set()).add("—")
                cats.setdefault(rama,{}).setdefault("—",set()).update(ap_cats)

    ramas_sorted = sorted(ramas)
    agrups_sorted = {r: sorted(list(v)) for r,v in agrups.items()}
    cats_sorted = {r: {a: sorted(list(vv)) for a,vv in av.items()} for r,av in cats.items()}

    return {
        "ramas": ramas_sorted,
        "agrups": agrups_sorted,
        "cats": cats_sorted,
        "source": "maestro.xlsx"
    }

_META_CACHE: dict | None = None

def get_meta(force_reload: bool=False) -> dict:
    global _META_CACHE
    if _META_CACHE is None or force_reload:
        if not MAESTRO_PATH.exists():
            raise FileNotFoundError(f"No existe maestro.xlsx en {MAESTRO_PATH}")
        _META_CACHE = _build_meta_from_maestro(MAESTRO_PATH)
    return _META_CACHE

def get_payload() -> dict:
    # Por ahora: payload = meta + lugar para crecer (escalas, importes, reglas, etc.)
    meta = get_meta()
    return {
        "version": "v3",
        "meta": meta,
    }
