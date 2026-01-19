import { U, api } from './shared.js';

let META = null;

function setError(id, msg){
  const el = U.$(id);
  if(el) el.textContent = msg || '';
}

function fillSelect(sel, items){
  sel.innerHTML = '';
  for(const it of items){
    const o = document.createElement('option');
    o.value = it;
    o.textContent = it;
    sel.appendChild(o);
  }
}

function currentMonthsKey(){
  return `${U.$('rama').value}||${U.$('agrup').value}||${U.$('categoria').value}`;
}

function refreshAgrup(){
  const rama = U.$('rama').value;
  const agrupNames = Object.keys(META.tree[rama] || {});
  fillSelect(U.$('agrup'), agrupNames.length ? agrupNames : ['—']);
  refreshCategorias();
}

function refreshCategorias(){
  const rama = U.$('rama').value;
  const agrup = U.$('agrup').value;
  const cats = (META.tree[rama] || {})[agrup] || [];
  fillSelect(U.$('categoria'), cats.length ? cats : ['—']);
  refreshMeses();
}

function refreshMeses(){
  const months = META.months[currentMonthsKey()] || [];
  fillSelect(U.$('mes'), months.length ? months : ['']);
}

function setTab(tab){
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab===tab));
  U.$('panel-mensual').style.display = tab==='mensual' ? '' : 'none';
  U.$('panel-final').style.display = tab==='final' ? '' : 'none';
}

function renderRows(tbodyId, rows){
  const tb = U.$(tbodyId);
  tb.innerHTML = '';
  for(const r of rows){
    const tr = document.createElement('tr');
    const td = (txt, right=false)=>{
      const e = document.createElement('td');
      if(right) e.className='right';
      e.textContent = txt;
      return e;
    };
    tr.appendChild(td(r.concepto));
    tr.appendChild(td(r.rem ? U.money(r.rem) : '', true));
    tr.appendChild(td(r.nr_or_ind ? U.money(r.nr_or_ind) : '', true));
    tr.appendChild(td(r.desc ? U.money(r.desc) : '', true));
    tb.appendChild(tr);
  }
}

async function calcularMensual(){
  setError('errM','');
  try{
    const payload = {
      rama: U.$('rama').value,
      agrup: U.$('agrup').value,
      categoria: U.$('categoria').value,
      mes: U.$('mes').value,
      anios_antig: U.pf(U.$('anios_antig').value),
      osecac: U.$('osecac').checked,
      afiliado: U.$('afiliado').checked,
      sind_pct: U.pf(U.$('sind_pct').value),
      incluir_sac_proporcional: U.$('inc_sac').checked,
      adelanto: U.pf(U.$('adelanto').value),
    };
    const out = await api('/api/calc/mensual', { method:'POST', body: JSON.stringify(payload) });

    const rows = [];
    rows.push({ concepto:'Básico', rem: out.escala.basico, nr_or_ind:0, desc:0 });
    if(out.conceptos.antig_rem) rows.push({ concepto:'Antigüedad', rem: out.conceptos.antig_rem, nr_or_ind:0, desc:0 });
    rows.push({ concepto:'Presentismo', rem: out.conceptos.presentismo_rem, nr_or_ind:0, desc:0 });
    if(out.conceptos.sac_rem) rows.push({ concepto:'SAC proporcional (Rem.)', rem: out.conceptos.sac_rem, nr_or_ind:0, desc:0 });

    const nr = out.escala.no_rem || 0;
    const sf = out.escala.suma_fija || 0;
    if(nr) rows.push({ concepto:'No Remunerativo', rem:0, nr_or_ind:nr, desc:0 });
    if(sf) rows.push({ concepto:'Suma fija NR', rem:0, nr_or_ind:sf, desc:0 });
    if(out.conceptos.antig_nr) rows.push({ concepto:'Antigüedad s/ NR', rem:0, nr_or_ind: out.conceptos.antig_nr, desc:0 });
    if(out.conceptos.presentismo_nr) rows.push({ concepto:'Presentismo s/ NR', rem:0, nr_or_ind: out.conceptos.presentismo_nr, desc:0 });
    if(out.conceptos.sac_nr) rows.push({ concepto:'SAC proporcional (NR)', rem:0, nr_or_ind: out.conceptos.sac_nr, desc:0 });

    // descuentos
    const d = out.detalles_descuentos;
    rows.push({ concepto:'Jubilación 11%', rem:0, nr_or_ind:0, desc:d.jubilacion_11 });
    rows.push({ concepto:'PAMI 3%', rem:0, nr_or_ind:0, desc:d.pami_3 });
    rows.push({ concepto:'Obra Social 3%', rem:0, nr_or_ind:0, desc:d.obra_social_3 });
    rows.push({ concepto:'FAECYS 0,5%', rem:0, nr_or_ind:0, desc:d.faecys_0_5 });
    if(d.sindicato) rows.push({ concepto:'Sindicato', rem:0, nr_or_ind:0, desc:d.sindicato });
    if(d.osecac_100) rows.push({ concepto:'OSECAC $100', rem:0, nr_or_ind:0, desc:d.osecac_100 });
    if(d.adelanto) rows.push({ concepto:'Adelanto', rem:0, nr_or_ind:0, desc:d.adelanto });

    renderRows('tbodyMensual', rows);
    U.$('m_totRem').textContent = U.money(out.totales.total_rem);
    U.$('m_totNR').textContent = U.money(out.totales.total_no_rem);
    U.$('m_totDed').textContent = U.money(out.totales.descuentos);
    U.$('m_neto').textContent = U.money(out.totales.neto);
  } catch(e){
    setError('errM', 'Error: '+e.message);
  }
}

async function calcularFinal(){
  setError('errF','');
  try{
    const payload = {
      tipo: U.$('lf_tipo').value,
      fecha_ingreso: U.$('lf_ingreso').value,
      fecha_egreso: U.$('lf_egreso').value,
      mejor_salario: U.pf(U.$('lf_mejor').value),
      vac_no_gozadas_dias: U.pf(U.$('lf_vac').value),
      incluir_sac_vac: U.$('lf_sac_vac').checked,
      preaviso_dias: U.pf(U.$('lf_preaviso').value),
      incluir_sac_preaviso: U.$('lf_sac_pre').checked,
    };
    const out = await api('/api/calc/final', { method:'POST', body: JSON.stringify(payload) });

    // enforce "final limpia" in UI: only indemnizatorio column
    const c = out.conceptos;
    const rows = [];
    if(c.vacaciones_no_gozadas) rows.push({ concepto:'Vacaciones no gozadas', rem:0, nr_or_ind:c.vacaciones_no_gozadas, desc:0 });
    if(c.sac_sobre_vacaciones) rows.push({ concepto:'SAC s/ Vacaciones', rem:0, nr_or_ind:c.sac_sobre_vacaciones, desc:0 });
    if(c.indemnizacion_art_245) rows.push({ concepto:'Indemnización Art. 245', rem:0, nr_or_ind:c.indemnizacion_art_245, desc:0 });
    if(c.indemnizacion_art_248) rows.push({ concepto:'Indemnización Art. 248', rem:0, nr_or_ind:c.indemnizacion_art_248, desc:0 });
    if(c.preaviso) rows.push({ concepto:'Preaviso', rem:0, nr_or_ind:c.preaviso, desc:0 });
    if(c.sac_sobre_preaviso) rows.push({ concepto:'SAC s/ Preaviso', rem:0, nr_or_ind:c.sac_sobre_preaviso, desc:0 });

    renderRows('tbodyFinal', rows);
    U.$('f_totInd').textContent = U.money(out.totales.total_indemnizatorio);
    U.$('f_neto').textContent = U.money(out.totales.neto);
    U.$('f_anios').textContent = String(out.meta.anios_indemnizatorios);
  } catch(e){
    setError('errF', 'Error: '+e.message);
  }
}

async function init(){
  META = await api('/api/meta');
  const ramas = Object.keys(META.tree || {});
  fillSelect(U.$('rama'), ramas);
  refreshAgrup();

  U.$('rama').addEventListener('change', refreshAgrup);
  U.$('agrup').addEventListener('change', refreshCategorias);
  U.$('categoria').addEventListener('change', refreshMeses);

  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', ()=> setTab(t.dataset.tab)));
  U.$('btnCalcularMensual').addEventListener('click', calcularMensual);
  U.$('btnCalcularFinal').addEventListener('click', calcularFinal);
}

init().catch(e => {
  setError('errM', 'Error cargando meta: '+e.message);
});
