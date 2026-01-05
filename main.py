from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import DatosEmpleado
from escalas import buscar_escala, valor_funebres, ESCALAS, _norm, get_payload


app = FastAPI(title="ComercioOnline - Cálculo CCT 130/75")

# CORS abierto para que el HTML pueda consumir la API incluso desde file:// (Origin: null)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "service": "motor-sueldos-faecys"}


# Endpoints para que el HTML cargue el maestro
@app.get("/maestro")
def maestro() -> Dict[str, Any]:
    return get_payload()


@app.get("/payload")
def payload() -> Dict[str, Any]:
    return get_payload()


@dataclass
class Item:
    concepto: str
    remunerativo: float = 0.0
    no_rem: float = 0.0
    descuentos: float = 0.0


@app.post("/calcular")
def calcular(d: DatosEmpleado) -> Dict[str, Any]:
    """Calcula una liquidación mensual simple (demostrativa)."""

    if not d.rama:
        raise HTTPException(status_code=400, detail="Falta rama")
    if not d.categoria:
        raise HTTPException(status_code=400, detail="Falta categoría")
    if not d.mes:
        raise HTTPException(status_code=400, detail="Falta mes")

    rama = _norm(d.rama)
    cat = d.categoria
    mes = d.mes

    escala = buscar_escala(rama, d.agrupamiento, cat, mes)
    if not escala:
        raise HTTPException(status_code=404, detail="No se encontró escala para esos filtros")

    # Básicos
    basico = float(escala.get("basico_rem", 0.0) or 0.0)
    nr_var = float(escala.get("nr_variable", 0.0) or 0.0)
    suma_fija = float(escala.get("suma_fija_nr", 0.0) or 0.0)

    items: List[Item] = []
    items.append(Item("Básico", remunerativo=basico))

    # Presentismo 8,33% sobre básico (REM)
    presentismo = round(basico / 12, 2)
    items.append(Item("Presentismo", remunerativo=presentismo))

    # Antigüedad (regla general 1% no acumulativa; Agua Potable 2% acumulativa)
    anios = int(d.anios_antiguedad or 0)
    if rama == _norm("AGUA POTABLE"):
        # 2% acumulativo
        ant_pct = 0.02
        antig = round((basico + nr_var + suma_fija) * (ant_pct * anios), 2)
        items.append(Item("Antigüedad", remunerativo=round(basico * (ant_pct * anios), 2), no_rem=round((nr_var + suma_fija) * (ant_pct * anios), 2)))
    else:
        ant_pct = 0.01
        antig = round((basico + nr_var + suma_fija) * (ant_pct * anios), 2)
        items.append(Item("Antigüedad", remunerativo=round(basico * (ant_pct * anios), 2), no_rem=round((nr_var + suma_fija) * (ant_pct * anios), 2)))

    # No remunerativos
    if nr_var:
        items.append(Item("No Rem (variable)", no_rem=nr_var))
    if suma_fija:
        items.append(Item("Suma fija (NR)", no_rem=suma_fija))

    # Adicionales (ej. Fúnebres)
    if rama == _norm("FUNEBRES"):
        adic = valor_funebres(d, escala)
        for it in adic:
            items.append(Item(it["concepto"], remunerativo=it.get("rem", 0.0) or 0.0, no_rem=it.get("nr", 0.0) or 0.0))

    # Totales
    total_rem = round(sum(i.remunerativo for i in items), 2)
    total_nr = round(sum(i.no_rem for i in items), 2)

    # Descuentos (modelo simplificado)
    # Jubilación 11% y PAMI 3% solo sobre REM
    jub = round(total_rem * 0.11, 2)
    pami = round(total_rem * 0.03, 2)

    # OSECAC / FAECYS / Sindicato sobre (REM + NR total)
    base_aportes_nr = total_rem + total_nr
    osecac = round(base_aportes_nr * 0.03, 2)
    faecys = round(base_aportes_nr * 0.005, 2)
    sindicato = round(base_aportes_nr * 0.02, 2)

    items.append(Item("Jubilación 11%", descuentos=jub))
    items.append(Item("PAMI 3%", descuentos=pami))
    items.append(Item("Obra Social 3%", descuentos=osecac))
    items.append(Item("FAECYS 0,5%", descuentos=faecys))
    items.append(Item("Sindicato 2%", descuentos=sindicato))

    total_desc = round(jub + pami + osecac + faecys + sindicato, 2)
    neto = round(total_rem + total_nr - total_desc, 2)

    return {
        "escala": escala,
        "items": [
            {
                "concepto": i.concepto,
                "rem": i.remunerativo,
                "nr": i.no_rem,
                "desc": i.descuentos,
            }
            for i in items
        ],
        "totales": {
            "rem": total_rem,
            "nr": total_nr,
            "desc": total_desc,
            "neto": neto,
        },
    }
