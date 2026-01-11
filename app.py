from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "maestro_actualizado.xlsx")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app = FastAPI()

# Permitir que el HTML servido desde el mismo dominio o desde localhost pueda consultar la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _norm(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    # normalizar espacios
    s = " ".join(s.split())
    return s

@lru_cache(maxsize=1)
def _load_maestro() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"No existe el maestro en {DATA_PATH}")
    # concatenar todas las hojas de categorías
    xl = pd.ExcelFile(DATA_PATH)
    frames = []
    for sh in xl.sheet_names:
        if not sh.startswith("Categorias_"):
            continue
        df = xl.parse(sh)
        # columnas esperadas: Rama, Agrupamiento, Categoria, Mes
        cols = {c: c.strip() for c in df.columns}
        df.rename(columns=cols, inplace=True)
        needed = ["Rama", "Agrupamiento", "Categoria", "Mes"]
        if not all(c in df.columns for c in needed):
            continue
        # normalizar
        for c in needed:
            df[c] = df[c].apply(_norm)
        frames.append(df)
    if not frames:
        raise ValueError("No se encontraron hojas 'Categorias_*' en el maestro.")
    cat = pd.concat(frames, ignore_index=True)

    # asegurar tipos numéricos si existen
    for col in ["Basico", "No Remunerativo", "SUMA_FIJA"]:
        if col in cat.columns:
            cat[col] = pd.to_numeric(cat[col], errors="coerce").fillna(0.0)

    return cat

@app.get("/meta")
def meta() -> Dict[str, Any]:
    """
    Devuelve combinaciones válidas para selects.
    Formato:
      {
        ok: true,
        ramas: [...],
        rows: [{rama, agrup, categoria, mes}, ...]
      }
    """
    df = _load_maestro()
    rows = (
        df[["Rama", "Agrupamiento", "Categoria", "Mes"]]
        .drop_duplicates()
        .sort_values(["Rama", "Agrupamiento", "Categoria", "Mes"])
    )
    out_rows = [
        {
            "rama": r.Rama,
            "agrup": r.Agrupamiento,
            "categoria": r.Categoria,
            "mes": str(r.Mes),
        }
        for r in rows.itertuples(index=False)
    ]
    ramas = sorted(df["Rama"].dropna().unique().tolist())
    return {"ok": True, "ramas": ramas, "rows": out_rows}

@app.get("/payload")
def payload(
    rama: str = Query(...),
    mes: str = Query(...),
    agrup: str = Query(...),
    categoria: str = Query(...),
) -> Dict[str, Any]:
    """
    Devuelve importes base de la combinación seleccionada.
    """
    df = _load_maestro()

    rama_n = _norm(rama)
    mes_n = _norm(mes)
    agrup_n = _norm(agrup)
    cat_n = _norm(categoria)

    sub = df[
        (df["Rama"] == rama_n)
        & (df["Mes"].astype(str) == mes_n)
        & (df["Agrupamiento"] == agrup_n)
        & (df["Categoria"] == cat_n)
    ]

    if sub.empty:
        return {
            "ok": False,
            "error": "No se encontró esa combinación en el maestro",
            "rama": rama_n,
            "agrup": agrup_n,
            "categoria": cat_n,
            "mes": mes_n,
        }

    # si hubiera más de una fila, tomar la primera
    row = sub.iloc[0].to_dict()

    return {
        "ok": True,
        "rama": rama_n,
        "agrup": agrup_n,
        "categoria": cat_n,
        "mes": mes_n,
        "basico": float(row.get("Basico", 0.0)),
        "no_rem": float(row.get("No Remunerativo", 0.0)),
        "suma_fija": float(row.get("SUMA_FIJA", 0.0)),
    }

# Servir estáticos (index.html)
if os.path.isdir(PUBLIC_DIR):
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
