# -*- coding: utf-8 -*-
"""
escalas.py
Carga y consulta del maestro de escalas y tablas auxiliares (adicionales y conexiones).

Diseñado para FastAPI (main.py). Soporta:
- /meta: ramas, meses, agrupamientos, categorias
- /payload: básico/no_rem/suma_fija para una combinación
- Adicionales (Fúnebres) por mes
- Reglas de conexiones (Agua Potable)
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _norm_rama(s: Any) -> str:
    x = _norm(s).upper()
    # Normalizaciones típicas
    x = x.replace("CENTRO DE LLAMADAS", "CALL CENTER")
    x = x.replace("FÚNEBRES", "FUNEBRES")
    x = x.replace("FÚNEBRE", "FUNEBRES")
    x = x.replace("AGUA POTABLE", "AGUA POTABLE")
    return x


def resolve_maestro_path() -> Path:
    """
    Busca el maestro en ubicaciones típicas (preferencia: ./data/maestro.xlsx).
    Permite override por env var MAESTRO_PATH.
    """
    import os
    env = os.getenv("MAESTRO_PATH", "").strip()
    if env:
        p = Path(env)
        if p.exists():
            return p

    here = Path(__file__).resolve().parent
    candidates = [
        here / "data" / "maestro_actualizado.xlsx",
        here / "data" / "maestro.xlsx",
        here / "maestro_actualizado.xlsx",
        here / "maestro.xlsx",
    ]
    for p in candidates:
        if p.exists():
            return p

    # último recurso: primer xlsx en ./data
    data_dir = here / "data"
    if data_dir.exists():
        xs = sorted(data_dir.glob("*.xlsx"))
        if xs:
            return xs[0]

    raise FileNotFoundError("No se encontró el archivo maestro .xlsx (probé data/ y raíz).")


@dataclass(frozen=True)
class MaestroData:
    df: pd.DataFrame
    adicionales: pd.DataFrame
    reglas_conex: pd.DataFrame
    reglas_adic: pd.DataFrame


def _load_categorias_sheets(xlsx_path: Path) -> pd.DataFrame:
    xls = pd.ExcelFile(xlsx_path)
    sheets = [s for s in xls.sheet_names if s.upper().startswith("CATEGORIAS_")]
    if not sheets:
        raise ValueError("El maestro no tiene hojas CATEGORIAS_*.")

    frames = []
    for sh in sheets:
        df = pd.read_excel(xlsx_path, sheet_name=sh)
        # Normalizar nombres esperados
        # Esperamos: Rama, Agrupamiento, Categoria, Mes, Basico, No_rem, Suma_fija
        cols = {c: c.strip() for c in df.columns}
        df = df.rename(columns=cols)

        # Algunos archivos pueden usar "No Rem" o similar
        rename_map = {}
        for c in df.columns:
            cu = c.upper().replace(" ", "_")
            if cu in ("NO_REM", "NOREM", "NO_REMUNERATIVO", "NO_REMUN"):
                rename_map[c] = "No_rem"
            if cu in ("SUMA_FIJA", "SUMA_FIJA_NR", "NR_FIJO"):
                rename_map[c] = "Suma_fija"
            if cu in ("BASICO", "BÁSICO", "BASICO_REM"):
                rename_map[c] = "Basico"
            if cu in ("AGRUP", "AGRUPAMIENTO", "AGRUPACION", "AGRUPACIÓN"):
                rename_map[c] = "Agrupamiento"
            if cu in ("CATEGORIA", "CATEGORÍA"):
                rename_map[c] = "Categoria"
        if rename_map:
            df = df.rename(columns=rename_map)

        required = ["Rama", "Agrupamiento", "Categoria", "Mes", "Basico", "No_rem", "Suma_fija"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Faltan columnas {missing} en hoja {sh}")

        # Normalizaciones
        df["Rama"] = df["Rama"].apply(_norm_rama)
        df["Agrupamiento"] = df["Agrupamiento"].apply(_norm)
        df["Categoria"] = df["Categoria"].apply(_norm)
        df["Mes"] = df["Mes"].apply(lambda x: _norm(x)[:7])  # YYYY-MM

        for col in ("Basico", "No_rem", "Suma_fija"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        frames.append(df[required])

    out = pd.concat(frames, ignore_index=True)
    # limpiar agrupamiento vacío a "—"
    out.loc[out["Agrupamiento"].eq("") | out["Agrupamiento"].isna(), "Agrupamiento"] = "—"
    return out


def _load_adicionales(xlsx_path: Path) -> pd.DataFrame:
    xls = pd.ExcelFile(xlsx_path)
    if "Adicionales" not in xls.sheet_names:
        # si no existe, devolver vacío
        return pd.DataFrame(columns=["Rama", "Concepto", "Mes", "Remunerativo", "NoRemunerativo"])

    df = pd.read_excel(xlsx_path, sheet_name="Adicionales")
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)

    # columnas esperadas (según tu archivo)
    # Rama | Concepto | Mes | Remunerativo | NoRemunerativo
    for c in ("Rama", "Concepto", "Mes"):
        if c not in df.columns:
            raise ValueError("Hoja Adicionales: faltan columnas base (Rama/Concepto/Mes).")
    if "Remunerativo" not in df.columns:
        # tolerar Rem o similar
        for c in df.columns:
            if c.upper().startswith("REM"):
                df = df.rename(columns={c: "Remunerativo"})
                break
    if "NoRemunerativo" not in df.columns:
        for c in df.columns:
            if "NO" in c.upper() and "REM" in c.upper():
                df = df.rename(columns={c: "NoRemunerativo"})
                break

    if "Remunerativo" not in df.columns:
        df["Remunerativo"] = 0.0
    if "NoRemunerativo" not in df.columns:
        df["NoRemunerativo"] = 0.0

    df["Rama"] = df["Rama"].apply(_norm_rama)
    df["Concepto"] = df["Concepto"].apply(_norm)
    df["Mes"] = df["Mes"].apply(lambda x: _norm(x)[:7])
    df["Remunerativo"] = pd.to_numeric(df["Remunerativo"], errors="coerce").fillna(0.0)
    df["NoRemunerativo"] = pd.to_numeric(df["NoRemunerativo"], errors="coerce").fillna(0.0)

    return df[["Rama", "Concepto", "Mes", "Remunerativo", "NoRemunerativo"]]


def _load_reglas_conexiones(xlsx_path: Path) -> pd.DataFrame:
    xls = pd.ExcelFile(xlsx_path)
    if "ReglasConexiones" not in xls.sheet_names:
        return pd.DataFrame(columns=["Min", "Max", "Categoria", "Base", "Porcentaje"])

    df = pd.read_excel(xlsx_path, sheet_name="ReglasConexiones")
    cols = {c: c.strip() for c in df.columns}
    df = df.rename(columns=cols)

    needed = ["Min", "Max", "Categoria", "Base", "Porcentaje"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Hoja ReglasConexiones: faltan columnas {missing}")

    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0).astype(int)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0).astype(int)
    df["Categoria"] = df["Categoria"].apply(_norm)
    df["Base"] = df["Base"].apply(_norm)
    df["Porcentaje"] = pd.to_numeric(df["Porcentaje"], errors="coerce").fillna(0.0)

    return df[needed]


@lru_cache(maxsize=2)

def _load_reglas_adicionales(xlsx_path: Path) -> pd.DataFrame:
    """Carga hoja 'ReglasAdicionales' (Título Turismo / Cajeros / KM, etc.)."""
    try:
        df = pd.read_excel(xlsx_path, sheet_name="ReglasAdicionales")
    except Exception:
        return pd.DataFrame()

    # Normalizar columnas esperadas
    # (no forzamos mucho: solo garantizamos el nombre de columna de %)
    if "Tasa/Porcentaje" not in df.columns:
        for c in df.columns:
            if "PORC" in str(c).upper() or "%" in str(c):
                df = df.rename(columns={c: "Tasa/Porcentaje"})
                break
    return df


def load_maestro() -> MaestroData:
    path = resolve_maestro_path()
    df = _load_categorias_sheets(path)
    adicionales = _load_adicionales(path)
    reglas = _load_reglas_conexiones(path)
    reglas_adic = _load_reglas_adicionales(path)
    return MaestroData(df=df, adicionales=adicionales, reglas_conex=reglas, reglas_adic=reglas_adic)


def get_meta() -> Dict[str, Any]:
    m = load_maestro().df
    ramas = sorted(m["Rama"].unique().tolist())
    meses = sorted(m["Mes"].unique().tolist())
    agrupamientos: Dict[str, List[str]] = {}
    categorias: Dict[str, Dict[str, List[str]]] = {}

    for rama in ramas:
        sub = m[m["Rama"] == rama]
        agrs = sorted(sub["Agrupamiento"].unique().tolist())
        agrupamientos[rama] = agrs

        categorias[rama] = {}
        for agr in agrs:
            cats = sorted(sub[sub["Agrupamiento"] == agr]["Categoria"].unique().tolist())
            categorias[rama][agr] = cats

    return {
        "ramas": ramas,
        "meses": meses,
        "agrupamientos": agrupamientos,
        "categorias": categorias,
    }


def get_payload(rama: str, agrup: str, categoria: str, mes: str) -> Dict[str, Any]:
    m = load_maestro().df
    r = _norm_rama(rama)
    a = _norm(agrup) or "—"
    c = _norm(categoria)
    ms = _norm(mes)[:7]

    hit = m[(m["Rama"] == r) & (m["Agrupamiento"] == a) & (m["Categoria"] == c) & (m["Mes"] == ms)]
    if hit.empty:
        return {"ok": False, "error": "No se encontró esa combinación en el maestro", "rama": r, "agrup": a, "categoria": c, "mes": ms}

    row = hit.iloc[0]
    out: Dict[str, Any] = {
        "ok": True,
        "rama": r,
        "agrup": a,
        "categoria": c,
        "mes": ms,
        "basico": float(row["Basico"]),
        "no_rem": float(row["No_rem"]),
        "suma_fija": float(row["Suma_fija"]),
    }

    # Extras por rama
    if r == "FUNEBRES":
        out["adicionales"] = get_adicionales_funebres(ms)
    if r == "AGUA POTABLE":
        out["reglas_conexiones"] = get_reglas_conexiones()

    return out


def get_adicionales_funebres(mes: str) -> List[Dict[str, Any]]:
    d = load_maestro().adicionales
    ms = _norm(mes)[:7]
    if d.empty:
        return []
    sub = d[(d["Rama"] == "FUNEBRES") & (d["Mes"] == ms)]
    res = []
    for _, r in sub.iterrows():
        res.append({
            "concepto": _norm(r["Concepto"]),
            "rem": float(r["Remunerativo"]),
            "nr": float(r["NoRemunerativo"]),
        })
    return res


def get_reglas_conexiones() -> List[Dict[str, Any]]:
    df = load_maestro().reglas_conex
    if df.empty:
        return []
    res = []
    for _, r in df.iterrows():
        res.append({
            "min": int(r["Min"]),
            "max": int(r["Max"]),
            "categoria": _norm(r["Categoria"]),
            "base": _norm(r["Base"]),
            "porcentaje": float(r["Porcentaje"]),
        })
    return res


def match_regla_conexiones(conexiones: int) -> Optional[Dict[str, Any]]:
    df = load_maestro().reglas_conex
    if df.empty:
        return None
    n = int(conexiones)
    sub = df[(df["Min"] <= n) & (df["Max"] >= n)]
    if sub.empty:
        return None
    r = sub.iloc[0]
    return {
        "min": int(r["Min"]),
        "max": int(r["Max"]),
        "categoria": _norm(r["Categoria"]),
        "base": _norm(r["Base"]),
        "porcentaje": float(r["Porcentaje"]),
    }


# =========================
# Reglas adicionales (Título / Cajero / KM) desde hoja "ReglasAdicionales"
# =========================

def _parse_pct(x: Any) -> float:
    """Convierte '2.5%' -> 2.5, '48%' -> 48.0, 2.5 -> 2.5"""
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".")
    s = s.replace("%", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


@lru_cache(maxsize=1)
def get_reglas_adicionales() -> pd.DataFrame:
    m = load_maestro()
    # la hoja se carga en load_maestro si existe; si no, leerla directo
    df = getattr(m, "reglas_adic", pd.DataFrame())
    if df is None:
        return pd.DataFrame()
    return df.copy()


def get_titulo_pct_por_nivel(nivel: str) -> float:
    """Devuelve % de título para Turismo según 'ReglasAdicionales'. nivel: 'terciario'/'universitario'."""
    n = _norm(nivel)
    df = get_reglas_adicionales()
    if df.empty:
        return 0.0
    sub = df[df["Convenio/Rama"].astype(str).str.upper().str.strip() == "TURISMO"]
    if sub.empty:
        return 0.0
    if "TERCI" in n:
        row = sub[sub["Concepto"].astype(str).str.contains("Terci", case=False, na=False)]
    elif "UNIV" in n:
        row = sub[sub["Concepto"].astype(str).str.contains("Univers", case=False, na=False)]
    else:
        return 0.0
    if row.empty:
        return 0.0
    return _parse_pct(row.iloc[0].get("Tasa/Porcentaje"))


def get_regla_cajero(tipo: str) -> Optional[Dict[str, Any]]:
    """Regla Art.30 Cajeros. tipo: 'A','B','C'. Retorna {'pct':..,'base_categoria':..} o None."""
    t = _norm(tipo)
    if not t:
        return None
    df = get_reglas_adicionales()
    if df.empty:
        return None
    sub = df[(df["Convenio/Rama"].astype(str).str.upper().str.strip() == "CCT 130/75") &
             (df["Concepto"].astype(str).str.contains("Cajero", case=False, na=False))]
    if sub.empty:
        return None
    if t.startswith("B"):
        row = sub[sub["Concepto"].astype(str).str.contains("Cajero B", case=False, na=False)]
        base_cat = "Cajeros B"
    else:
        row = sub[sub["Concepto"].astype(str).str.contains("Cajero A", case=False, na=False)]
        base_cat = "Cajeros A"
    if row.empty:
        return None
    return {"pct": _parse_pct(row.iloc[0].get("Tasa/Porcentaje")), "base_categoria": base_cat}


def get_regla_km(rol: str, tramo: str) -> Optional[Dict[str, Any]]:
    """Reglas Art.36 por km. rol: 'CHOFER'/'AYUDANTE'. tramo: '0-100' o '100+'."""
    r = _norm(rol)
    tr = _norm(tramo)
    df = get_reglas_adicionales()
    if df.empty:
        return None
    sub = df[(df["Convenio/Rama"].astype(str).str.upper().str.strip() == "CCT 130/75") &
             (df["Concepto"].astype(str).str.contains("Chofer", case=False, na=False))]
    if sub.empty:
        return None

    def pick(pattern: str):
        rr = sub[sub["Concepto"].astype(str).str.contains(pattern, case=False, na=False)]
        if rr.empty:
            return None
        base_cat = rr.iloc[0].get("Base categoría (si aplica)")
        # mapear a nombre de categoría del maestro (GENERAL)
        base_map = {
            "AUXILIAR A": "Auxiliar A",
            "AUXILIAR B": "Auxiliar B",
            "AUXILIAR ESPECIALIZADO A": "Auxiliar Especializado A",
            "AUXILIAR ESPECIALIZADO B": "Auxiliar Especializado B",
        }
        base_norm = _norm(str(base_cat))
        cat = None
        for k,v in base_map.items():
            if k in base_norm:
                cat = v
                break
        if not cat:
            # fallback por texto
            if "AUXILIAR ESPECIALIZADO" in base_norm and "A" in base_norm:
                cat = "Auxiliar Especializado A"
            elif "AUXILIAR ESPECIALIZADO" in base_norm and "B" in base_norm:
                cat = "Auxiliar Especializado B"
            elif "AUXILIAR" in base_norm and "A" in base_norm:
                cat = "Auxiliar A"
            elif "AUXILIAR" in base_norm and "B" in base_norm:
                cat = "Auxiliar B"
        return {"pct_por_km": _parse_pct(rr.iloc[0].get("Tasa/Porcentaje")), "base_categoria": cat}

    is_chofer = "CHOFER" in r and "AYUD" not in r
    if is_chofer:
        if "100+" in tr or "MAS" in tr or "MÁS" in tramo:
            return pick("Chofer - más")
        return pick("Chofer - 0")
    # ayudante
    if "100+" in tr or "MAS" in tr or "MÁS" in tramo:
        return pick("Ayudante")
    # primeros 100
    return pick("Ayudante")
