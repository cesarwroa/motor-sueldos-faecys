from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from escalas import get_meta, get_payload, clear_cache
from calculo import calcular_recibo


app = FastAPI(title="Motor Sueldos FAECYS (Server-Side)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_DIR = Path(__file__).with_name("public")
INDEX_HTML = PUBLIC_DIR / "index.html"


class CalcularIn(BaseModel):
    # Required
    rama: str
    agrup: str | None = "—"
    categoria: str
    mes: str

    # Optional / extras (UI)
    modo: str | None = "MENSUAL"
    hs: float | None = 48
    anios: int | None = 0
    zona_pct: float | None = 0
    presentismo: bool | None = True
    afiliado: bool | None = False
    osecac: bool | None = True
    jubilado: bool | None = False

    # extras
    tur_titulo_pct: float | None = 0
    agua_conex: int | None = 0
    funAdic1: bool | None = False
    funAdic2: bool | None = False
    funAdic3: bool | None = False
    funAdic4: bool | None = False

    a_cuenta: float | None = 0
    viaticos_nr: float | None = 0

    hex50: float | None = 0
    hex100: float | None = 0
    noct: float | None = 0
    fer_no: int | None = 0
    fer_si: int | None = 0
    vac_goz: float | None = 0
    lic_sg: float | None = 0
    aus: float | None = 0
    faltante: float | None = 0
    embargo: float | None = 0

    # Liquidación final
    lf_tipo: str | None = "RENUNCIA"
    lf_ingreso: str | None = None
    lf_egreso: str | None = None
    lf_mrmnh: float | None = 0
    lf_preaviso: int | None = 0
    lf_integracion: bool | None = False
    lf_sac_pre: bool | None = False
    lf_sac_int: bool | None = False

    model_config = ConfigDict(extra="allow")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    if INDEX_HTML.exists():
        return INDEX_HTML.read_text(encoding="utf-8")
    return "<h1>Motor Sueldos FAECYS</h1><p>Falta public/index.html</p>"


@app.get("/meta")
def meta():
    return get_meta()


@app.get("/payload")
def payload():
    return get_payload()


@app.post("/calcular")
def calcular(inp: CalcularIn):
    data = inp.model_dump()
    res = calcular_recibo(data)
    if not res.get("ok", False):
        raise HTTPException(status_code=400, detail=res.get("error", "Error de cálculo"))
    return res


@app.post("/reload")
def reload_maestro():
    clear_cache()
    return {"ok": True, "msg": "Cache limpiada. /meta y /payload se regeneran en el próximo request."}
