from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from escalas import get_meta, get_payload
from calculo import calcular_recibo

app = FastAPI(title="motor-sueldos-faecys")

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
    p = BASE_DIR / "index.html"
    if p.exists():
        return FileResponse(p)
    p2 = BASE_DIR / "static" / "index.html"
    if p2.exists():
        return FileResponse(p2)
    return {"ok": True, "error": "index.html no encontrado"}

@app.get("/health")
def health():
    return {"ok": True, "servicio": "motor-sueldos-faecys"}

@app.get("/meta")
def meta():
    return get_meta()

@app.get("/payload")
def payload(rama: str, mes: str, agrup: str = "—", categoria: str = "—"):
    return get_payload(rama=rama, mes=mes, agrup=agrup, categoria=categoria)

@app.get("/calcular")
def calcular(request: Request):
    # Tomar TODOS los query params y delegar el cálculo a calculo.py
    qp = dict(request.query_params)

    # Compat: el front viejo manda jornada/anios_antig
    if "jornada" in qp and "hs" not in qp:
        qp["hs"] = qp["jornada"]
    if "anios_antig" in qp and "anios" not in qp:
        qp["anios"] = qp["anios_antig"]

    # Compat: el front viejo manda titulo_pct/sind_pct pero el cálculo usa tur_titulo_pct
    # (lo dejamos, no rompe)

    return calcular_recibo(qp)
