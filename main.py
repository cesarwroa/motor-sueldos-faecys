from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from escalas import get_meta, get_payload

app = FastAPI(title="Motor Sueldos FAECYS", version="v3")

# CORS (para que el HTML pueda llamar al backend desde cualquier dominio)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Motor Sueldos (Backend OK)</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:24px;line-height:1.35}
    select,button{padding:10px 12px;font-size:16px;margin:6px 0;min-width:280px}
    pre{background:#111;color:#eee;padding:12px;border-radius:10px;overflow:auto}
    .row{display:flex;gap:16px;flex-wrap:wrap}
    .card{border:1px solid #ddd;border-radius:12px;padding:16px;max-width:900px}
  </style>
</head>
<body>
  <h2>✅ Backend activo</h2>
  <div class="card">
    <p>Este es un <b>verificador</b>. Si acá ves las ramas/categorías, el problema ya no es Render ni el servidor.</p>
    <div class="row">
      <div>
        <div><b>Rama</b></div>
        <select id="rama"></select>
      </div>
      <div>
        <div><b>Agrup</b></div>
        <select id="agrup"></select>
      </div>
      <div>
        <div><b>Categoría</b></div>
        <select id="cat"></select>
      </div>
    </div>
    <button id="btn">Probar /calcular</button>
    <pre id="out">cargando…</pre>
  </div>

<script>
(async function(){
  const out = document.getElementById("out");
  try{
    const meta = await (await fetch("/meta")).json();
    const ramaSel = document.getElementById("rama");
    const agrupSel = document.getElementById("agrup");
    const catSel = document.getElementById("cat");

    function fillSelect(sel, items){
      sel.innerHTML = "";
      for(const it of items){
        const o=document.createElement("option");
        o.value=it; o.textContent=it;
        sel.appendChild(o);
      }
    }

    fillSelect(ramaSel, meta.ramas || []);
    function refreshAgrup(){
      const r = ramaSel.value;
      fillSelect(agrupSel, (meta.agrups && meta.agrups[r]) ? meta.agrups[r] : ["—"]);
      refreshCat();
    }
    function refreshCat(){
      const r = ramaSel.value;
      const a = agrupSel.value;
      const list = (meta.cats && meta.cats[r] && meta.cats[r][a]) ? meta.cats[r][a] : [];
      fillSelect(catSel, list);
    }
    ramaSel.addEventListener("change", refreshAgrup);
    agrupSel.addEventListener("change", refreshCat);
    refreshAgrup();

    out.textContent = JSON.stringify({meta_preview: {ramas: meta.ramas}}, null, 2);

    document.getElementById("btn").onclick = async () => {
      const body = { rama: ramaSel.value, agrup: agrupSel.value, categoria: catSel.value };
      const res = await fetch("/calcular", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body)});
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    };
  }catch(e){
    out.textContent = "ERROR: " + (e && e.message ? e.message : String(e));
  }
})();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def home():
    return INDEX_HTML

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/meta")
def meta():
    return get_meta()

@app.get("/payload")
def payload():
    return get_payload()

@app.post("/calcular")
async def calcular(req: Request):
    """
    Placeholder: evita 404 y permite ir reemplazándolo por el motor real.
    """
    body = await req.json()
    return {"ok": True, "received": body, "note": "Endpoint listo. Acá va el motor de cálculo real."}
