from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services.repo import meta, find_escala
from app.services.calculo_mensual import calcular_mensual
from app.services.calculo_final import calcular_final

app = FastAPI(title="ComercioOnline - Motor (Day1)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Models
# -----------------------------
class MensualIn(BaseModel):
    rama: str
    agrup: str
    categoria: str
    mes: str
    anios_antig: float = 0
    osecac: bool = True
    afiliado: bool = False
    sind_pct: float = 0
    incluir_sac_proporcional: bool = False
    adelanto: float = 0


class FinalIn(BaseModel):
    tipo: str = Field(default="DESPIDO_SIN_CAUSA")
    fecha_ingreso: str
    fecha_egreso: str
    mejor_salario: float
    vac_no_gozadas_dias: float = 0
    incluir_sac_vac: bool = True
    preaviso_dias: float = 0
    incluir_sac_preaviso: bool = False


# -----------------------------
# Endpoints
# -----------------------------
@app.get("/api/meta")
def api_meta():
    return meta()


@app.get("/api/escala")
def api_escala(rama: str, agrup: str, categoria: str, mes: str):
    r = find_escala(rama, agrup, categoria, mes)
    if not r:
        raise HTTPException(status_code=404, detail="Escala no encontrada")
    return r


@app.post("/api/calc/mensual")
def api_calc_mensual(inp: MensualIn):
    try:
        return calcular_mensual(inp.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/calc/final")
def api_calc_final(inp: FinalIn):
    try:
        return calcular_final(inp.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


# Static frontend (optional)
# Put the built/static files in ../frontend/public and mount at /
import pathlib
FRONTEND_DIR = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
