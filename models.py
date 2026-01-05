from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal

class DatosEmpleado(BaseModel):
    # permitir campos extra (para evolución sin romper)
    model_config = ConfigDict(extra="ignore")

    rama: str
    agrup: str
    categoria: str
    mes: str  # YYYY-MM
    hs: int = Field(default=48, ge=1, le=48)
    anios: int = Field(default=0, ge=0)

    # flags principales
    presentismo: bool = True
    basico: float = 0
    zona: float = 0  # porcentaje (0/10/20/...)
    afiliado: bool = False
    osecac: Literal["si","no"] = "no"
    ferNoTrab: int = 0
    ferTrab: int = 0
    hex50: int = 0
    hex100: int = 0
    hsNoct: int = 0
    coAus: int = 0
    coJub: bool = False

    # Liquidación final (si mensual: NINGUNA/null)
    lf_tipo: str = "NINGUNA"
    lf_ingreso: Optional[str] = None  # YYYY-MM-DD
    lf_egreso: Optional[str] = None   # YYYY-MM-DD

    # Extras UI (opcional)
    nrVar: float = 0
    nrSF: float = 0
    aCuentaNR: float = 0
    viaticosNR: float = 0

    kmTipo: Optional[str] = None
    kmMenos100: int = 0
    kmMas100: int = 0

    aguaConex: Optional[str] = None

    funAdic1: bool = False
    funAdic2: bool = False
    funAdic3: bool = False
    funAdic4: bool = False
