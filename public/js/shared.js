export const U = {
  $(id){ return document.getElementById(id); },
  pf(v){ const n = parseFloat(v); return Number.isFinite(n) ? n : 0; },
  money(n){
    n = Number.isFinite(n) ? n : (parseFloat(n) || 0);
    return n.toLocaleString('es-AR',{style:'currency',currency:'ARS',minimumFractionDigits:2});
  },
  ym(s){ return String(s||'').slice(0,7); },
};

export async function api(path, opts={}){
  const res = await fetch(path, {
    headers: { 'Content-Type':'application/json', ...(opts.headers||{}) },
    ...opts,
  });
  const data = await res.json().catch(()=> ({}));
  if(!res.ok){
    const msg = data?.detail || res.statusText;
    throw new Error(msg);
  }
  return data;
}
