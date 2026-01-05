from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models_fixed import DatosEmpleado
import escalas


app = FastAPI(title="Motor Sueldos FAECYS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _antiguedad(monto: float, anios: int, rama: str) -> float:
    rama_u = (rama or "").strip().upper()
    if rama_u == "AGUA POTABLE":
        # 2% acumulativo por año: monto*(1.02^n - 1)
        return float(monto) * ((1.02 ** int(anios)) - 1.0) if anios > 0 else 0.0
    # 1% por año (no acumulativo)
    return float(monto) * (0.01 * int(anios)) if anios > 0 else 0.0


def calcular_sueldo(d: DatosEmpleado) -> dict:
    # Escala (si no está, usa lo que venga desde el front)
    row = escalas.buscar_escala(d.rama, d.agrup, d.categoria, d.mes)

    basico = float((row or {}).get("Basico") or d.basico or 0.0)

    nr_40 = float((row or {}).get("No Remunerativo") or 0.0)
    nr_60 = float((row or {}).get("Suma Fija") or 0.0)
    total_nr_base = nr_40 + nr_60

    # Zona (porcentaje)
    zona_pct = float(d.zona or 0.0) / 100.0
    zona_rem = basico * zona_pct
    zona_nr = total_nr_base * zona_pct

    # Antigüedad
    antig_rem = _antiguedad(basico, d.anios, d.rama)
    antig_nr = _antiguedad(total_nr_base, d.anios, d.rama)

    # Bases para presentismo
    base_pres_rem = basico + antig_rem + zona_rem
    base_pres_nr = total_nr_base + antig_nr + zona_nr

    pres_rem = (base_pres_rem / 12.0) if d.presentismo else 0.0
    pres_nr = (base_pres_nr / 12.0) if d.presentismo else 0.0

    total_rem = base_pres_rem + pres_rem
    total_nr = base_pres_nr + pres_nr

    # Deducciones
    jubilacion = 0.0 if d.coJub else (total_rem * 0.11)
    pami = 0.0 if d.coJub else (total_rem * 0.03)

    base_rem_mas_nr = total_rem + total_nr

    faecys = base_rem_mas_nr * 0.005  # criterio del sistema (sobre Rem + NR)
    sindicato = (base_rem_mas_nr * 0.02) if d.afiliado else 0.0

    base_os = total_rem + (total_nr if d.osecac == "si" else 0.0)
    obra_social = 0.0 if d.coJub else (base_os * 0.03)
    osecac_100 = 100.0 if (d.osecac == "si" and not d.coJub) else 0.0

    total_deducciones = jubilacion + pami + faecys + sindicato + obra_social + osecac_100
    neto = (total_rem + total_nr) - total_deducciones

    items = [
        {"concepto": "Básico", "base": basico, "remunerativo": basico, "no_remunerativo": 0.0, "deduccion": 0.0},
        {"concepto": "Antigüedad", "base": None, "remunerativo": antig_rem, "no_remunerativo": antig_nr, "deduccion": 0.0},
        {"concepto": "Zona Desfavorable", "base": base_pres_rem if zona_pct else None, "remunerativo": zona_rem, "no_remunerativo": zona_nr, "deduccion": 0.0},
        {"concepto": "Presentismo (8.33%)", "base": base_pres_rem if d.presentismo else None, "remunerativo": pres_rem, "no_remunerativo": pres_nr, "deduccion": 0.0},
        {"concepto": "No Remunerativo (40.000)", "base": None, "remunerativo": 0.0, "no_remunerativo": nr_40, "deduccion": 0.0},
        {"concepto": "Suma Fija NR (60.000)", "base": None, "remunerativo": 0.0, "no_remunerativo": nr_60, "deduccion": 0.0},

        {"concepto": "Jubilación 11%", "base": total_rem, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": jubilacion},
        {"concepto": "Ley 19.032 (PAMI) 3%", "base": total_rem, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": pami},
        {"concepto": "FAECYS 0,5%", "base": base_rem_mas_nr, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": faecys},
        {"concepto": "Sindicato 2%", "base": base_rem_mas_nr if d.afiliado else None, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": sindicato},
        {"concepto": "Obra Social 3%", "base": base_os if d.osecac == "si" else total_rem, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": obra_social},
        {"concepto": "OSECAC $100", "base": None, "remunerativo": 0.0, "no_remunerativo": 0.0, "deduccion": osecac_100},
    ]

    return {
        "totales": {
            "total_rem": round(total_rem, 2),
            "total_nr": round(total_nr, 2),
            "total_deducciones": round(total_deducciones, 2),
            "neto": round(neto, 2),
        },
        "items": [
            {
                "concepto": it["concepto"],
                "base": (None if it["base"] is None else round(float(it["base"]), 2)),
                "remunerativo": round(float(it["remunerativo"]), 2),
                "no_remunerativo": round(float(it["no_remunerativo"]), 2),
                "deduccion": round(float(it["deduccion"]), 2),
            }
            for it in items
        ],
    }


@app.post("/calcular")
def calcular(d: DatosEmpleado):
    try:
        return calcular_sueldo(d)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
