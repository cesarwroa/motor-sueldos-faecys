from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from escalas import (
    get_meta,
    get_payload,
    calcular_payload,
    get_adicionales_funebres,
    match_regla_conexiones,
    get_titulo_pct_por_nivel,
    get_regla_cajero,
    get_regla_km,
)

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

# ========= HOME → HTML =========
@app.get("/", include_in_schema=False)
def home():
    p = BASE_DIR / "index.html"
    if p.exists():
        return FileResponse(p)

    p2 = BASE_DIR / "static" / "index.html"
    if p2.exists():
        return FileResponse(p2)

    return {"ok": True, "error": "index.html no encontrado"}

# ========= HEALTH =========
@app.get("/health")
def health():
    return {"ok": True, "servicio": "motor-sueldos-faecys"}

# ========= META =========
@app.get("/meta")
def meta():
    return get_meta()

# ========= PAYLOAD =========
@app.get("/payload")
def payload(rama: str, mes: str):
    return calcular_payload(
        rama=rama,
        agrup=agrup,
        categoria=categoria,
        mes=mes,
        jornada=jornada,
        anios_antig=anios_antig,
        osecac=osecac,
        afiliado=afiliado,
        sind_pct=sind_pct,
        titulo_pct=titulo_pct,
    )

# ========= FUNEBRES =========
@app.get("/adicionales-funebres")
def adicionales_funebres():
    return get_adicionales_funebres()

# ========= AGUA POTABLE =========
@app.get("/regla-conexiones")
def regla_conexiones(cantidad: int):
    return match_regla_conexiones(cantidad)

# ========= TURISMO =========
@app.get("/titulo-pct")
def titulo_pct(nivel: str):
    return get_titulo_pct_por_nivel(nivel)

# ========= CAJEROS =========
@app.get("/regla-cajero")
def regla_cajero(tipo: str):
    return get_regla_cajero(tipo)

# ========= KM =========
@app.get("/regla-km")
def regla_km(categoria: str, km: float):
    return get_regla_km(categoria, km)
