from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configuración de CORS para que tu web en Netlify pueda hablar con este motor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Por ahora permitimos todo para probar fácil
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Definimos qué datos esperamos recibir del formulario (el "input")
class DatosEmpleado(BaseModel):
    basico: float
    antiguedad_anios: int
    presentismo: bool

@app.get("/")
def home():
    return {"mensaje": "El motor de FAECYS está en línea"}

@app.post("/api/calcular")
def calcular_sueldo(datos: DatosEmpleado):
    # 1. Calculamos antigüedad (1% por año según CCT 130/75)
    monto_antiguedad = datos.basico * (datos.antiguedad_anios * 0.01)
    
    # 2. Subtotal para presentismo
    subtotal = datos.basico + monto_antiguedad
    
    # 3. Presentismo (8.33% sobre el subtotal)
    monto_presentismo = 0
    if datos.presentismo:
        monto_presentismo = subtotal * 0.0833
        
    bruto = subtotal + monto_presentismo
    
    # 4. Descuentos básicos de ley (17% jubilación + ley + obra social) + 2% sindicato + 0.5% faecys
    # Total descuentos aprox: 19.5%
    descuentos = bruto * 0.195
    neto = bruto - descuentos

    return {
        "bruto": round(bruto, 2),
        "neto": round(neto, 2),
        "detalle": {
            "basico": datos.basico,
            "antiguedad": round(monto_antiguedad, 2),
            "presentismo": round(monto_presentismo, 2),
            "descuentos_totales": round(descuentos, 2)
        }
    }
