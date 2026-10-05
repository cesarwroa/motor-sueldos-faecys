(() => {
  'use strict';
  const apiOrigin = 'https://calculadoradecomercio.com.ar';
  const profilesUrl = `${apiOrigin}/api/public-accounts.php`;
  const authUrl = `${apiOrigin}/api/`;
  const labels = {empleado:'Empleado', empresa:'Empresa', estudio:'Estudio contable', sindicato:'Sindicato'};
  const key = 'co_public_session_v1';
  let token = sessionStorage.getItem(key) || '';
  let account = null;
  let page = 1;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const options = selected => '<option value="">Seleccioná una opción</option>' + Object.entries(labels).map(([value,label]) => `<option value="${value}" ${value===selected?'selected':''}>${label}</option>`).join('');
  async function request(action, data, legacy=false, method=data?'POST':'GET') {
    const url = new URL(legacy?authUrl:profilesUrl); url.searchParams.set('action',action);
    if (action==='admin-users') url.searchParams.set('page',page);
    const res = await fetch(url, {method, headers:{'Content-Type':'application/json', ...(token?{Authorization:`Bearer ${token}`}:{})}, ...(data?{body:JSON.stringify(data)}:{})});
    const body = await res.json().catch(()=>({}));
    if (!res.ok || !body.ok) { const error = new Error(body.message || 'No se pudo completar la operación.'); error.status=res.status; throw error; }
    return body;
  }
  const style = document.createElement('style');
  style.textContent = `
  .co-account-bar{position:relative;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:12px 20px;background:#eff6ff;color:#15335a;font:14px system-ui;border-bottom:1px solid #bfdbfe}
  .co-account-bar button,.co-account-dialog button{cursor:pointer;border:1px solid #cbd5e1;border-radius:9px;padding:9px 13px;background:white;color:#15335a;font:inherit}
  .co-account-bar .co-primary,.co-account-dialog .co-primary{background:#2563eb;color:white;border-color:#2563eb}
  .co-account-dialog{width:min(620px,calc(100vw - 28px));max-height:90vh;overflow:auto;border:1px solid #cbd5e1;border-radius:16px;padding:24px;background:white;color:#172033;font:15px system-ui;box-shadow:0 16px 70px #0003}
  .co-account-dialog [data-close]{position:absolute;right:14px;top:14px;width:36px!important;height:36px;padding:4px!important;float:none!important}.co-account-dialog h2{padding-right:35px}.co-account-dialog::backdrop{background:#0f172a99}.co-account-dialog h2{font-size:23px;margin:0 0 8px}.co-account-dialog p{margin:10px 0;line-height:1.5}.co-account-dialog form{display:grid;gap:14px;margin-top:18px}
  .co-account-dialog label,.co-contact-profile label{display:grid;gap:6px;color:#334155;font:14px system-ui}.co-account-dialog input:not([type=checkbox]),.co-account-dialog select,.co-contact-profile input,.co-contact-profile select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#172033;font:inherit}
  .co-account-dialog .co-check{display:flex;gap:9px;align-items:flex-start}.co-account-dialog .co-check input{width:18px;height:18px;flex-shrink:0}.co-account-dialog .co-actions{display:flex;flex-wrap:wrap;gap:8px}.co-account-feedback{color:#9f1239;white-space:pre-wrap}.co-account-dialog [hidden],.co-contact-profile [hidden]{display:none!important}
  .co-contact-profile{display:grid;gap:12px;margin:12px 0;padding:14px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px}.co-account-user{border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:12px 0;overflow-wrap:anywhere}.co-account-dialog button:disabled{opacity:.6;cursor:wait}
  `;
  document.head.append(style);
  const bar=document.createElement('div'); bar.className='co-account-bar';
  document.body.prepend(bar);
  const dialog=document.createElement('dialog'); dialog.className='co-account-dialog'; dialog.setAttribute('aria-label','Cuenta de la calculadora'); document.body.append(dialog);
  let previousFocus=null;
  dialog.addEventListener('close',()=>previousFocus?.focus());
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  function renderBar(){
    bar.innerHTML=`<span><strong>${account?`Hola, ${esc(account.user.name)}`:'Creá tu cuenta en la calculadora'}</strong> · El uso sigue siendo gratuito y sin límites.</span><span class="co-actions">${account?'<button data-open="profile">Mi cuenta</button>':'<button data-open="login">Ingresar</button> <button class="co-primary" data-open="register">Registrarme</button>'}${account?.is_admin?' <button data-open="admin">Registros</button>':''} <button data-open="contact">Enviar consulta</button>${account?' <button data-logout>Salir</button>':''}</span>`;
    bar.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>open(b.dataset.open));
    bar.querySelector('[data-logout]')?.addEventListener('click',async()=>{
      try{await request('logout',{},true);}catch(error){open('profile'); feedback(error.message);return;}
      token=''; account=null; sessionStorage.removeItem(key); renderBar();
    });
  }
  function feedback(message){dialog.querySelector('[role=status]').textContent=message;}
  function profileFields(profile={}){
    return `<label>Tipo de cuenta<select name="account_type" required>${options(profile.account_type)}</select></label><label data-org ${!profile.account_type||profile.account_type==='empleado'?'hidden':''}>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(profile.organization_name)}"></label><label class="co-check"><input type="checkbox" name="newsletter_opt_in" ${Number(profile.newsletter_opt_in)?'checked':''}>Quiero recibir novedades sobre funciones, acuerdos, escalas y convenios. Puedo desactivar esta opción desde mi cuenta.</label>`;
  }
  function bindProfile(container){
    const select=container.querySelector('[name=account_type]'), org=container.querySelector('[data-org]');
    if(!select||!org)return;
    const update=()=>{const needed=!!select.value&&select.value!=='empleado';org.hidden=!needed;org.querySelector('input').required=needed;if(!needed)org.querySelector('input').value='';};
    select.addEventListener('change',update);update();
  }
  async function open(mode){
    if(!dialog.open){previousFocus=document.activeElement;dialog.showModal();}
    const close='<button type="button" data-close style="float:right" aria-label="Cerrar">×</button>';
    let content='';
    if(mode==='register') content=`<h2>Crear cuenta</h2><p>Elegí tu perfil. Durante esta etapa todos los cálculos siguen siendo gratuitos.</p><form><label>Nombre y apellido<input name="name" required maxlength="120" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" autocomplete="email"></label>${profileFields()}<label>Contraseña<input name="password" type="password" required minlength="10" maxlength="128" autocomplete="new-password" aria-describedby="co-password-help"></label><small id="co-password-help">Al menos 10 caracteres, con letras y números.</small><button class="co-primary">Crear cuenta</button></form><button data-switch="login">Ya tengo cuenta</button>`;
    if(mode==='login') content='<h2>Ingresar</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><label>Contraseña<input name="password" type="password" required maxlength="128" autocomplete="current-password"></label><button class="co-primary">Ingresar</button></form><p class="co-actions"><button data-switch="register">Crear cuenta</button><button data-switch="recovery">Olvidé mi contraseña</button></p>';
    if(mode==='recovery') content='<h2>Recuperar acceso</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><button class="co-primary">Enviar enlace</button></form>';
    if(mode==='profile') content=`<h2>Mi cuenta</h2><p>${esc(account?.user.email)}</p><p>Acceso gratuito y sin límites durante la implementación.${Number(account?.profile?.complimentary_unlimited)?' Tenés acceso de cortesía ilimitado asignado por el administrador.':''}</p><form>${profileFields(account?.profile||{})}<button class="co-primary">Guardar perfil</button></form>`;
    if(mode==='admin') content='<h2>Registros de la calculadora</h2><p>Los emails son los declarados al registrarse. En esta etapa no se verifica su titularidad.</p><div data-users>Cargando…</div>';
    if(mode==='contact') content=`<h2>Enviar consulta</h2><form><label>Nombre<input name="nombre" required maxlength="160" value="${esc(account?.user.name)}" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" value="${esc(account?.user.email)}" autocomplete="email"></label><label>Tipo de usuario<select name="account_type" required>${options(account?.profile?.account_type)}</select></label><label data-org ${!account?.profile?.account_type||account?.profile?.account_type==='empleado'?'hidden':''}>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(account?.profile?.organization_name)}"></label><label>Motivo<select name="motivo"><option>Consulta técnica</option><option>Consulta sobre una liquidación</option><option>Sugerencia</option></select></label><label>Mensaje<textarea name="mensaje" required maxlength="5000" rows="5" style="padding:10px;border:1px solid #cbd5e1;border-radius:8px"></textarea></label><input name="website" tabindex="-1" autocomplete="off" hidden><button class="co-primary">Enviar consulta</button></form>`;
    dialog.innerHTML=close+content+'<p class="co-account-feedback" role="status" aria-live="polite"></p>';
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    dialog.querySelectorAll('[data-switch]').forEach(b=>b.onclick=()=>open(b.dataset.switch));
    bindProfile(dialog);
    const form=dialog.querySelector('form');
    if(form)form.addEventListener('submit',async event=>{
      event.preventDefault(); const submit=form.querySelector('button');submit.disabled=true;feedback('');
      const values=Object.fromEntries(new FormData(form));values.newsletter_opt_in=!!form.querySelector('[name=newsletter_opt_in]')?.checked;
      try{
        if(mode==='register'){await request('register',values);await open('login');feedback('Cuenta creada. Ingresá con tu email y contraseña.');}
        if(mode==='login'){
          const result=await request('login',values,true);token=result.token;sessionStorage.setItem(key,token);
          try{account=await request('me');}catch(error){token='';sessionStorage.removeItem(key);throw error;}
          renderBar();if(!account.profile)await open('profile');else dialog.close();
        }
        if(mode==='profile'){await request('profile',values,false,'PUT');account=await request('me');renderBar();feedback('Perfil guardado.');}
        if(mode==='recovery'){const result=await request('forgot-password',values,true);feedback(result.message);}
        if(mode==='contact'){
          const fd=new FormData(form); const response=await fetch(`${apiOrigin}/send-contact.php`,{method:'POST',body:fd});
          const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.message||'No se pudo enviar.');
          form.hidden=true;feedback('Consulta enviada. Gracias por contactarnos.');
        }
      }catch(error){feedback(error.message);}finally{submit.disabled=false;}
    });
    if(mode==='admin')try{
      const result=await request('admin-users');const host=dialog.querySelector('[data-users]');
      host.innerHTML=`<p>${result.total} cuentas · Página ${result.page} de ${result.pages}</p>`+result.users.map(u=>`<article class="co-account-user"><strong>${esc(u.name)}</strong> · ${esc(labels[u.account_type])}<p>${esc(u.organization_name)||'Sin organización'}<br>${esc(u.email)}<br>Estado: ${esc(u.status)} · Registro: ${esc(u.created_at)} UTC<br>Novedades: ${Number(u.newsletter_opt_in)?'Aceptadas':'No aceptadas'}</p><button data-courtesy="${esc(u.id)}" data-enabled="${Number(u.complimentary_unlimited)?'false':'true'}">${Number(u.complimentary_unlimited)?'Revocar cortesía':'Otorgar acceso gratuito ilimitado'}</button></article>`).join('')+`<div class="co-actions"><button data-prev ${page<=1?'disabled':''}>Anterior</button><button data-next ${page>=result.pages?'disabled':''}>Siguiente</button></div>`;
      host.querySelectorAll('[data-courtesy]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await request('admin-courtesy',{user_id:b.dataset.courtesy,enabled:b.dataset.enabled==='true'},false,'PUT');await open('admin');}catch(error){feedback(error.message);b.disabled=false;}});
      host.querySelector('[data-prev]').onclick=()=>{page--;open('admin');};host.querySelector('[data-next]').onclick=()=>{page++;open('admin');};
    }catch(error){dialog.querySelector('[data-users]').textContent='';feedback(error.message);}
    dialog.querySelector('input,select')?.focus();
  }
  // El formulario React existente construye FormData: los campos adicionales se incluyen sin tocar su bundle.
  function enrichContactForms(){
    document.querySelectorAll('form').forEach(form=>{
      if(form.closest('.co-account-dialog')||form.querySelector('[name=account_type]')||!form.querySelector('[name=nombre]')||!form.querySelector('[name=mensaje]'))return;
      const group=document.createElement('div');group.className='co-contact-profile';
      group.innerHTML=`<label>Tipo de usuario<select name="account_type" required>${options(account?.profile?.account_type)}</select></label><label data-org hidden>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(account?.profile?.organization_name)}"></label>`;
      form.insertBefore(group,form.firstChild);bindProfile(group);
    });
  }
  const observer=new MutationObserver(enrichContactForms);observer.observe(document.body,{childList:true,subtree:true});
  renderBar();enrichContactForms();
  if(token)request('me').then(result=>{account=result;renderBar();}).catch(error=>{if(error.status===401||error.status===403){token='';sessionStorage.removeItem(key);}renderBar();});
})();
