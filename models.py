from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class DatosEmpleado(BaseModel):
    # Claves exactas esperadas por el frontend
    rama: str
    agrup: str
    categoria: str
    mes: str = Field(..., description="YYYY-MM")

    hs: float = Field(default=48, ge=1, le=48)
    anios: float = Field(default=0, ge=0)
    presentismo: Optional[bool] = None  # si no viene, se infiere con coAus<=1

    # Estos campos NO son necesarios desde el HTML limpio, pero se aceptan por compatibilidad
    basico: float = 0
    zona: float = 0

    afiliado: bool = False
    osecac: Literal["si", "no", "SI", "NO", "sí", "SÍ"] = "no"

    ferNoTrab: float = 0
    ferTrab: float = 0
    hex50: float = 0
    hex100: float = 0
    hsNoct: float = 0

    coAus: float = 0
    coJub: bool = False

    # Compatibilidad con tu modelo anterior (si alguna UI manda esto)
    nrVar: float = 0
    nrSF: float = 0

    # Liquidación final
    lf_tipo: str = "NINGUNA"
    lf_ingreso: Optional[str] = None  # "YYYY-MM-DD"
    lf_egreso: Optional[str] = None   # "YYYY-MM-DD"

    class Config:
        extra = "ignore"

class Totales(BaseModel):
    total_rem: float
    total_nr: float
    total_deducciones: float
    neto: float

class ItemRecibo(BaseModel):
    concepto: str
    base: Optional[float] = None
    remunerativo: float = 0
    no_remunerativo: float = 0
    deduccion: float = 0

class RespuestaCalculo(BaseModel):
    totales: Totales
    items: List[ItemRecibo]
