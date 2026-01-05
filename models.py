
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class DatosLiquidacion(BaseModel):
    rama: str = ""
    agrup: str = ""
    categoria: str = ""
    mes: str = ""
    hs: float = 48
    anios: int = 0
    presentismo: bool = True

    basico: float = 0
    zona: float = 0

    afiliado: bool = False
    osecac: str = "si"  # "si" / "no"

    ferNoTrab: int = 0
    ferTrab: int = 0
    hex50: float = 0
    hex100: float = 0
    hsNoct: float = 0

    coAus: int = 0
    coJub: bool = False

    lf_tipo: str = "NINGUNA"
    lf_ingreso: Optional[str] = None
    lf_egreso: Optional[str] = None

    # Extras para API-only (no rompen si el front no los manda)
    aguaConex: Optional[str] = "A"   # A/B/C/D
    funAdic1: bool = False
    funAdic2: bool = False
    funAdic3: bool = False
    funAdic4: bool = False

    class Config:
        extra = "ignore"

class ItemRecibo(BaseModel):
    concepto: str
    remunerativo: float = 0
    no_remunerativo: float = 0
    deduccion: float = 0
    base: Optional[float] = None

class ResultadoCalculo(BaseModel):
    inputs_normalizados: DatosLiquidacion
    auto: Dict[str, float]
    totales: Dict[str, float]
    items: List[ItemRecibo]
