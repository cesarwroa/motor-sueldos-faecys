from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DatosEmpleado(BaseModel):
    # Selección
    rama: str
    agrup: str
    categoria: str
    mes: str = Field(..., description="YYYY-MM")

    # Parámetros
    hs: int = Field(48, ge=1, le=48)
    anios: int = Field(0, ge=0)
    presentismo: bool = True

    # Valores base (se aceptan desde el front, pero el motor puede revalidarlos)
    basico: float = 0
    zona: float = 0  # porcentaje (ej: 20 => 20%)

    # Aportes / condiciones
    afiliado: bool = False
    osecac: Literal["si", "no"] = "no"
    coJub: bool = False

    # Novedades
    ferNoTrab: int = 0
    ferTrab: int = 0
    hex50: float = 0
    hex100: float = 0
    hsNoct: float = 0
    coAus: int = 0

    # Liquidación final
    lf_tipo: Literal["NINGUNA", "DESPIDO_SC", "DESPIDO_CC", "RENUNCIA", "FALLECIMIENTO"] = "NINGUNA"
    lf_ingreso: Optional[date] = None
    lf_egreso: Optional[date] = None
