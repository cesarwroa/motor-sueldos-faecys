from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field

class DatosEmpleado(BaseModel):
    # Campos mínimos que usa el HTML/API (podés ampliar luego)
    rama: Optional[str] = None
    agrupamiento: Optional[str] = None
    categoria: Optional[str] = None
    mes: Optional[str] = None  # YYYY-MM
    jornada: Optional[float] = Field(default=None, description="Horas semanales (ej 48, 36, 24)")
    fecha_alta: Optional[str] = None  # dd/mm/aaaa

class CalculoRequest(BaseModel):
    # Request del endpoint /api/calcular (mensual / final)
    modo: Literal["mensual","final"] = "mensual"
    datos: DatosEmpleado = DatosEmpleado()
    # El HTML suele mandar muchos campos; los aceptamos sin romper
    extra: dict = {}
