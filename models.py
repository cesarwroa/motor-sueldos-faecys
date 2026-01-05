from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


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

    # Rem/NR base (normalmente vienen del maestro; se aceptan por compatibilidad)
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
    osecac: Literal["si", "no"] = "si"
    coJub: bool = False
    afiliado: bool = False  # (UI) no afecta el cálculo en el JS actual
    afiliado_selector: str = "NO"  # % adicional (ej: "2", "3", o "NO")
    afiliado_fijo: float = 0

    # Vacaciones / licencias (mensual)
    coVacDias: float = 0
    coLicP: int = 0
    coLicS: int = 0
    coSuspension: bool = False
    coAus: float = 0  # ausencias injustificadas (días)

    # Adicionales (UI)
    manejoCaja: bool = False
    cajero_tipo: str = ""  # A/B/C (si vacío, se infiere por categoría)
    faltanteCajaInput: str = ""  # string; el JS lo parsea

    armadoAuto: bool = False  # Vidrierista (Art. 23)
    kmTipo: str = ""          # Chofer/Ayudante o Turismo
    kmMenos100: float = 0
    kmMas100: float = 0

    # Fúnebres
    funAdic1: bool = False  # CADAVER (General)
    funAdic2: bool = False  # RESTO
    funAdic3: bool = False  # CHOFER (+General si no marcado)
    funAdic4: bool = False  # INDUMENT

    # Agua potable
    aguaConex: str = ""  # selector (categoría de conexiones)

    # Liquidación final (inputs)
    lf_tipo: str = "RENUNCIA"          # RENUNCIA / DESPIDO_SIN_CAUSA / DESPIDO_CON_CAUSA / FALLECIMIENTO
    lf_ingreso: Optional[date] = None
    lf_egreso: Optional[date] = None
    lf_anios: float = 0
    lf_dias_mes: float = 30
    lf_integracion: bool = False
    lf_preaviso: str = "NO"
    lf_vac_anuales: float = 0
    lf_vac_calc: float = 0
    lf_mrmnh: float = 0
    lf_sac_pre: bool = False
    lf_sac_int: bool = False
    lf_use_lastday: bool = False
