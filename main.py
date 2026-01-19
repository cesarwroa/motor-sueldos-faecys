from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import escalas
import calculo

app = FastAPI(title="motor-sueldos-faecys")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent


@app.get("/", include_in_schema=False)
def home():
    # Servimos index.html desde raíz (recomendado)
    p = BASE_DIR / "index.html"
    if p.exists():
        return FileResponse(p)

    # fallback
    p2 = BASE_DIR / "static" / "index.html"
    if p2.exists():
        return FileResponse(p2)

    return {"ok": True, "error": "index.html no encontrado"}


@app.get("/health")
def health():
    return {"ok": True, "servicio": "motor-sueldos-faecys"}


@app.get("/meta")
def meta():
    try:
        return escalas.get_meta_full()
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/meses")
def meses(rama: str, agrup: str = "—", categoria: str = "—"):
    try:
        return escalas.list_meses_combo(rama=rama, agrup=agrup, categoria=categoria)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/payload")
def payload(rama: str, mes: str, agrup: str = "—", categoria: str = "—"):
    # Devuelve base del maestro (básico + NR + suma fija) para la combinación.
    return escalas.get_payload(rama=rama, mes=mes, agrup=agrup, categoria=categoria)


@app.get("/calcular")
def calcular(request: Request):
    # Acepta cualquier query param (no hay que tocar backend por cada campo nuevo del HTML)
    try:
        qp: Dict[str, Any] = dict(request.query_params)
        return calculo.calcular_mensual_desde_query(qp)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/calcular-final")
def calcular_final(request: Request):
    try:
        qp: Dict[str, Any] = dict(request.query_params)
        return calculo.calcular_final_desde_query(qp)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/adicionales-funebres")
def adicionales_funebres(mes: str):
    return escalas.get_adicionales_funebres(mes)


@app.get("/regla-conexiones")
def regla_conexiones(cantidad: int):
    return escalas.match_regla_conexiones(cantidad)


@app.get("/titulo-pct")
def titulo_pct(nivel: str):
    return escalas.get_titulo_pct_por_nivel(nivel)

