from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from escalas import get_meta, get_payload, find_row


app = FastAPI(title="Motor Sueldos FAECYS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CalcularIn(BaseModel):
    rama: str
    agrup: str
    categoria: str
    mes: str


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    # Minimal UI to validate that meta/payload load OK in Render.
    return """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Motor Sueldos FAECYS</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial;max-width:980px;margin:24px auto;padding:0 12px}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    label{display:block;font-size:12px;margin:8px 0 4px;color:#333}
    select,button{padding:10px 12px;font-size:14px}
    pre{background:#f6f6f6;padding:12px;border-radius:8px;overflow:auto}
    .card{border:1px solid #ddd;border-radius:10px;padding:12px;margin-top:12px}
  </style>
</head>
<body>
  <h1>Motor Sueldos FAECYS</h1>
  <p>Si acá ves ramas/categorías, el servidor ya está trayendo el maestro correctamente.</p>

  <div class="row">
    <div>
      <label>Rama</label>
      <select id="rama"></select>
    </div>
    <div>
      <label>Agrupamiento</label>
      <select id="agrup"></select>
    </div>
    <div>
      <label>Categoría</label>
      <select id="cat"></select>
    </div>
    <div>
      <label>Mes</label>
      <select id="mes"></select>
    </div>
  </div>

  <div class="row" style="margin-top:12px">
    <button id="btn">Probar /calcular</button>
  </div>

  <div class="card">
    <strong>Respuesta</strong>
    <pre id="out">Cargando…</pre>
  </div>

<script>
let META = null;

function setOptions(sel, arr){
  sel.innerHTML = "";
  (arr || []).forEach(v => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    sel.appendChild(o);
  });
}

async function init(){
  const out = document.getElementById("out");
  try{
    META = await (await fetch("/meta")).json();

    const ramaSel = document.getElementById("rama");
    const agrSel  = document.getElementById("agrup");
    const catSel  = document.getElementById("cat");
    const mesSel  = document.getElementById("mes");

    setOptions(ramaSel, META.ramas);
    setOptions(mesSel, META.meses);

    function refreshAgr(){
      const r = ramaSel.value;
      setOptions(agrSel, (META.agrupamientos && META.agrupamientos[r]) || ["—"]);
      refreshCat();
    }

    function refreshCat(){
      const r = ramaSel.value;
      const a = agrSel.value;
      const key = `${r}||${a}`;
      setOptions(catSel, (META.categorias && META.categorias[key]) || []);
    }

    ramaSel.addEventListener("change", refreshAgr);
    agrSel.addEventListener("change", refreshCat);

    refreshAgr();

    out.textContent = "Listo. Elegí valores y apretá Probar.";
  }catch(e){
    out.textContent = "Error cargando /meta: " + (e?.message || e);
  }
}

document.getElementById("btn").addEventListener("click", async ()=>{
  const out = document.getElementById("out");
  const payload = {
    rama: document.getElementById("rama").value,
    agrup: document.getElementById("agrup").value,
    categoria: document.getElementById("cat").value,
    mes: document.getElementById("mes").value
  };
  try{
    const res = await fetch("/calcular", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const data = await res.json();
    out.textContent = JSON.stringify(data, null, 2);
  }catch(e){
    out.textContent = "Error llamando /calcular: " + (e?.message || e);
  }
});

init();
</script>
</body>
</html>
"""


@app.get("/meta")
def meta():
    return get_meta()


@app.get("/payload")
def payload():
    return get_payload()


@app.post("/calcular")
def calcular(inp: CalcularIn):
    row = find_row(inp.rama, inp.agrup, inp.categoria, inp.mes)
    if not row:
        raise HTTPException(status_code=404, detail="No se encontró combinación Rama/Agrup/Categoría/Mes en el maestro")
    # Por ahora devolvemos base (esto te destraba el front: 200 OK y datos reales)
    return {
        "ok": True,
        "rama": inp.rama,
        "agrup": inp.agrup,
        "categoria": inp.categoria,
        "mes": inp.mes,
        "basico": row["basico"],
        "no_rem_1": row["no_rem_1"],
        "no_rem_2": row["no_rem_2"],
        "nota": "Este endpoint es el esqueleto. El cálculo completo del recibo se integra después.",
    }
