from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import escalas


APP_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = APP_DIR / "public"

app = FastAPI(title="Motor Sueldos FAECYS")

# Si el front se sirve desde este mismo backend, CORS no hace falta,
# pero lo dejamos abierto para pruebas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir estáticos (y el index)
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")


@app.get("/")
def home():
    # Sirve el HTML principal (UI)
    return FileResponse(str(PUBLIC_DIR / "index.html"))


@app.get("/meta")
def meta() -> Dict[str, Any]:
    return escalas.get_meta()


@app.get("/payload")
def payload() -> Dict[str, Any]:
    return escalas.get_payload()


class CalcularIn(BaseModel):
    rama: str
    agrup: Optional[str] = ""
    categoria: str
    mes: str
    hs: Optional[float] = 48
    anios: Optional[float] = 0
    # El front manda muchos campos extra; los ignoramos sin error.
    class Config:
        extra = "allow"


@app.post("/calcular")
def calcular(inp: CalcularIn) -> Dict[str, Any]:
    """
    Devuelve las bases desde el maestro para que el front arme el recibo.
    (básico + NR). Luego, en siguientes iteraciones, devolvemos items/totales completos.
    """
    rama = (inp.rama or "").strip()
    agrup = (inp.agrup or "").strip()
    cat = (inp.categoria or "").strip()
    mes = (inp.mes or "").strip()

    row = escalas.find_row(rama=rama, agrup=agrup, categoria=cat, mes=mes)
    if not row:
        return {
            "ok": False,
            "error": "No se encontró combinación en maestro",
            "rama": rama,
            "agrup": agrup,
            "categoria": cat,
            "mes": mes,
        }

    return {
        "ok": True,
        "rama": rama,
        "agrup": agrup,
        "categoria": cat,
        "mes": mes,
        "basico": row.get("basico", 0),
        "no_rem_1": row.get("no_rem_1", 0),
        "no_rem_2": row.get("no_rem_2", 0),
    }


@app.post("/reload")
def reload_maestro() -> Dict[str, Any]:
    # Limpia cache para que tome el Excel actualizado sin redeploy
    escalas._CACHE = None  # type: ignore[attr-defined]
    return {"ok": True, "reloaded": True, "maestro_path": str(escalas.MAESTRO_PATH)}
