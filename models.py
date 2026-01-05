from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from datetime import date
import math
import escalas  # Tu archivo escalas.py

app = FastAPI()

# --- 1. CONFIGURACIÓN DE SEGURIDAD (CORS) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite acceso desde cualquier lugar (tu HTML, Vercel, etc)
    allow_credentials=True,
    allow_methods=["*"],  # Permite POST, GET, OPTIONS
    allow_headers=["*"],
)

# --- 2. MODELO DE DATOS (INPUT) ---
class DatosEmpleado(BaseModel):
    # Selección de escala
    rama: str
    agrup: str
    categoria: str
    mes: str = Field(..., description="YYYY-MM")

    # Jornada / parámetros
    hs: Optional[float] = Field(default=48, ge=1, le=48)
    zona: float = Field(default=0, description="Porcentaje (ej: 20 para 20%)")
    anios: float = Field(default=0, ge=0)

    # Rem/NR base
    basico: Optional[float] = 0
    nrVar: Optional[float] = 0
    nrSF: Optional[float] = 0
    aCuentaNR: float = 0
    viaticosNR: float = 0

    # Feriados / HE / nocturnidad
    hex50: float = 0
    hex100: float = 0
    ferNoTrab: float = 0
    ferTrab: float = 0
    hsNoct: float = 0

    # OSECAC / Jubilado / aportes sindicales variables
    osecac: Literal["si", "no", "SI", "NO"] = "si"
    coJub: bool = False
    afiliado: bool = False
    afiliado_selector: str = "NO"
    afiliado_fijo: float = 0

    # Vacaciones / licencias / ausencias
    coVacDias: float = 0
    coLicP: int = 0
    coLicS: int = 0
    coSuspension: bool = False
    coAus: float = 0

    # Adicionales varios
    manejoCaja: bool = False
    cajero_tipo: str = ""
    faltanteCajaInput: str = ""
    armadoAuto: bool = False
    kmTipo: str = ""
    kmMenos100: float = 0
    kmMas100: float = 0

    # Fúnebres
    funAdic1: bool = False
    funAdic2: bool = False
    funAdic3: bool = False
    funAdic4: bool = False
    aguaConex: str = ""

    # Liquidación final
    lf_tipo: str = "NINGUNA"
    lf_ingreso: Optional[date] = None
    lf_egreso: Optional[date] = None

# --- 3. LÓGICA DE CÁLCULO ---
@app.post("/calcular")
def calcular_sueldo(d: DatosEmpleado):
    # 1. Buscar Escala en el archivo maestro
    escala = escalas.buscar_escala(d.rama, d.agrup, d.categoria, d.mes)
    
    if not escala:
        # Fallback: devolver error o calcular con ceros
        # Para que no rompa el front, usamos ceros si no encuentra
        basico_escala = d.basico or 0
        nr_escala = d.nrVar or 0
        sf_escala = d.nrSF or 0
    else:
        basico_escala = float(escala.get("Basico") or 0)
        nr_escala = float(escala.get("No Remunerativo") or 0)
        sf_escala = float(escala.get("Suma Fija") or 0)

    # 2. Proporcional jornada
    # Regla: Si es 'CALL CENTER' y el maestro ya trae valores por jornada, NO prorratear.
    # Si es 'GENERAL' y son MENORES (6hs/8hs), NO prorratear.
    prop = 1.0
    if "CALL CENTER" not in d.rama.upper() and "MENOR" not in d.categoria.upper():
        prop = d.hs / 48.0

    basico_calc = basico_escala * prop
    nr_calc = (nr_escala + sf_escala) * prop

    # 3. Antigüedad (1% por año, acumulativo en agua)
    tasa_antig = 0.01 * d.anios
    if "AGUA" in d.rama.upper():
        tasa_antig = (1.02 ** d.anios) - 1
    
    antig_rem = basico_calc * tasa_antig
    antig_nr = nr_calc * tasa_antig

    # 4. Zona
    zona_rem = basico_calc * (d.zona / 100)

    # 5. Presentismo (8.33% si no hay faltas injustificadas > 1)
    presentismo_ok = d.coAus <= 1
    base_pres_rem = basico_calc + antig_rem + zona_rem + d.aCuentaNR
    base_pres_nr = nr_calc + antig_nr
    
    pres_rem = (base_pres_rem / 12) if presentismo_ok else 0
    pres_nr = (base_pres_nr / 12) if presentismo_ok else 0

    # 6. Sumar todo (Bruto)
    total_rem = base_pres_rem + pres_rem
    total_nr = base_pres_nr + pres_nr

    # 7. Deducciones
    base_aportes_rem = total_rem
    base_aportes_nr = total_nr # Para sindicato y FAECYS

    # Jubilación 11%
    jubilacion = base_aportes_rem * 0.11
    
    # Ley 19032 3% (si no es jubilado)
    pami = 0 if d.coJub else (base_aportes_rem * 0.03)

    # Sindicato y FAECYS (sobre Rem + NR)
    base_total = base_aportes_rem + base_aportes_nr
    sindicato = base_total * 0.02
    if d.afiliado:
        # Si hay selector extra, acá se sumaría
        pass 
    faecys = base_total * 0.005

    # Obra Social (sobre Rem + NR si tiene OSECAC, sino sobre Rem)
    base_os = base_total if d.osecac.lower() in ["si", "sí"] else base_aportes_rem
    # Ajuste jornada parcial (Art 92 ter): elevar base a jornada completa si corresponde
    if prop < 1 and prop > 0 and "CALL CENTER" not in d.rama.upper(): 
        base_os = base_os / prop
    
    obra_social = base_os * 0.03 if not d.coJub else 0
    osecac_fijo = 100 if (d.osecac.lower() in ["si", "sí"] and not d.coJub) else 0

    total_deducciones = jubilacion + pami + sindicato + faecys + obra_social + osecac_fijo

    # 8. Neto
    neto = total_rem + total_nr - total_deducciones

    # 9. Construir respuesta JSON
    return {
        "inputs_normalizados": {
            "rama": d.rama,
            "agrup": d.agrup,
            "categoria": d.categoria,
            "mes": d.mes,
            "hs": d.hs,
            "prop": round(prop, 2),
            "pres_ok": presentismo_ok
        },
        "totales": {
            "total_rem": round(total_rem, 2),
            "total_nr": round(total_nr, 2),
            "total_deducciones": round(total_deducciones, 2),
            "neto": round(neto, 2)
        },
        "items": [
            # Se pueden agregar filas detalladas aca si el front las necesita,
            # por ahora mandamos un resumen básico para probar totales.
            {"concepto": "Básico", "remunerativo": round(basico_calc, 2), "no_remunerativo": 0, "deduccion": 0, "base": basico_escala},
            {"concepto": "Antigüedad", "remunerativo": round(antig_rem, 2), "no_remunerativo": round(antig_nr, 2), "deduccion": 0, "base": None},
            {"concepto": "Zona Desfavorable", "remunerativo": round(zona_rem, 2), "no_remunerativo": 0, "deduccion": 0, "base": None},
            {"concepto": "Presentismo (8.33%)", "remunerativo": round(pres_rem, 2), "no_remunerativo": round(pres_nr, 2), "deduccion": 0, "base": None},
            {"concepto": "Jubilación 11%", "remunerativo": 0, "no_remunerativo": 0, "deduccion": round(jubilacion, 2), "base": base_aportes_rem},
            {"concepto": "Ley 19.032 (PAMI) 3%", "remunerativo": 0, "no_remunerativo": 0, "deduccion": round(pami, 2), "base": base_aportes_rem},
            {"concepto": "FAECYS 0,5%", "remunerativo": 0, "no_remunerativo": 0, "deduccion": round(faecys, 2), "base": base_total},
            {"concepto": "Sindicato 2%", "remunerativo": 0, "no_remunerativo": 0, "deduccion": round(sindicato, 2), "base": base_total},
            {"concepto": "Obra Social 3%", "remunerativo": 0, "no_remunerativo": 0, "deduccion": round(obra_social, 2), "base": base_os},
            {"concepto": "OSECAC $100", "remunerativo": 0, "no_remunerativo": 0, "deduccion": osecac_fijo, "base": None},
        ]
    }
