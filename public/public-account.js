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
  let socialProviders = {google:false,facebook:false};
  const isCalculator = !document.getElementById('root') && location.pathname !== '/admin/app';
  let gate = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const socialLogos = {
    google:'<svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.17 7.09-10.32 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.9 23.9 0 0 0 0 24c0 3.87.93 7.53 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.9-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.17 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>',
    facebook:'<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="12" fill="#1877F2"/><path fill="#fff" d="M16.67 15.47l.53-3.47h-3.33V9.75c0-.95.46-1.88 1.96-1.88h1.51V4.92s-1.37-.23-2.67-.23c-2.72 0-4.5 1.65-4.5 4.64V12H7.15v3.47h3.02v8.36a12.08 12.08 0 0 0 3.7 0v-8.36z"/></svg>'
  };
  function socialButtonContent(provider,mode,enabled){
    const action=mode==='register'?'Registrate':'Ingresá';
    return socialLogos[provider]+`<span>${action} con ${provider==='google'?'Google':'Facebook'}${enabled?'':' · Próximamente'}</span>`;
  }
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
  .co-account-bar{margin-top:var(--co-header-height,0px);position:relative;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:12px 20px;background:#eff6ff;color:#15335a;font:14px system-ui;border-bottom:1px solid #bfdbfe}
  .co-calculator-locked{display:none!important}.co-access-gate{max-width:620px;margin:40px auto;padding:28px;border:1px solid #bfdbfe;border-radius:16px;background:#fff;font:16px system-ui;color:#172033}.co-access-gate h1{font-size:26px}.co-access-gate p{line-height:1.6}.co-access-gate button{padding:12px 18px;border-radius:9px;border:1px solid #2563eb;background:#2563eb;color:white;cursor:pointer;font:inherit;margin:6px}.co-access-gate [data-open=login]{background:white;color:#2563eb}
  button[data-social]{display:inline-flex!important;align-items:center;justify-content:center;gap:10px;min-height:42px}button[data-social] svg{flex-shrink:0}
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
  let observedHeader = null;
  const headerObserver = new ResizeObserver(() => syncHeader());
  function syncHeader(){
    const header=document.querySelector('#root header');
    if(header && header!==observedHeader){headerObserver.disconnect();observedHeader=header;headerObserver.observe(header);}
    const height=header && getComputedStyle(header).position==='fixed'?header.getBoundingClientRect().height:0;
    const value=`${Math.ceil(height)}px`;if(bar.style.getPropertyValue('--co-header-height')!==value)bar.style.setProperty('--co-header-height',value);
  }
  syncHeader();
  function syncAccess(){
    if(!isCalculator)return;
    const content=document.querySelector('body > .container');
    const locked=!account || (!account.profile && !account.is_admin);
    if(content){content.classList.toggle('co-calculator-locked',locked);content.inert=locked;}
    if(!gate){
      gate=document.createElement('section');gate.className='co-access-gate';
      gate.innerHTML='<h1>Ingresá para usar la calculadora</h1><p>Creá tu cuenta o ingresá con tu email. Las liquidaciones mensuales y finales siguen siendo gratuitas y sin límites.</p><button data-open="register">Crear cuenta gratis</button><button data-open="login">Ya tengo cuenta</button>';
      bar.after(gate);gate.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>open(b.dataset.open));
    }
    gate.hidden=!locked;
  }
  document.addEventListener('co-auth-required',()=>{
    token='';account=null;sessionStorage.removeItem(key);renderBar();open('login');feedback('Ingresá para continuar. El uso sigue siendo gratuito.');
  });
  const dialog=document.createElement('dialog'); dialog.className='co-account-dialog'; dialog.setAttribute('aria-label','Cuenta de la calculadora'); document.body.append(dialog);
  let previousFocus=null;
  dialog.addEventListener('close',()=>previousFocus?.focus());
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  function renderBar(){
    bar.innerHTML=`<span><strong>${account?`Hola, ${esc(account.user.name)}`:'Creá tu cuenta en la calculadora'}</strong> · El uso sigue siendo gratuito y sin límites.</span><span class="co-actions">${account?'<button data-open="profile">Mi cuenta</button>':'<button data-open="login">Ingresar</button> <button class="co-primary" data-open="register">Registrarme</button>'}${account?.is_admin?' <button data-open="admin">Registros y estadísticas</button> <button data-calculator-admin>Administrar calculadora</button>':''} <button data-open="contact">Enviar consulta</button>${account?' <button data-logout>Salir</button>':''}</span>`;
    syncAccess();
    bar.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>open(b.dataset.open));
    bar.querySelector('[data-calculator-admin]')?.addEventListener('click',async()=>{
      try{
        const calculator=new URL(window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
        const response=await fetch(new URL('/admin/login-session',calculator),{method:'POST',headers:{Authorization:`Bearer ${token}`}});
        const result=await response.json();if(!response.ok||!result.token)throw new Error(result.detail||'No se pudo abrir el panel.');
        const target=new URL('/admin/app',calculator);target.hash=new URLSearchParams({admin_token:result.token}).toString();location.assign(target.href);
      }catch(error){await open('profile');feedback(error.message);}
    });
    bar.querySelector('[data-logout]')?.addEventListener('click',async()=>{
      try{await request('logout',{},true);}catch(error){if(error.status!==401&&error.status!==403){open('profile');feedback(error.message);return;}}
      token=''; account=null; sessionStorage.removeItem(key);
      sessionStorage.removeItem('co_admin_token');localStorage.removeItem('co_admin_token');
      location.assign(`${apiOrigin}/#co_logout=1`);
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
    // Reutilizar la sesión vigente de esta pestaña, sin almacenarla de forma persistente.
    if(mode==='login' && token){
      try{
        account=await request('me');renderBar();
        if(!account.profile){mode='profile';}
        else if(document.getElementById('root')){
          const result=await request('handoff-create',{});
          const target=new URL('/',window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
          target.hash=new URLSearchParams({co_login:result.code}).toString();location.assign(target.href);return;
        }else{if(dialog.open)dialog.close();return;}
      }catch(error){if(error.status===401||error.status===403){token='';sessionStorage.removeItem(key);account=null;renderBar();}}
    }

    if(mode==='admin'){location.assign(document.getElementById('root')?'/admin-uso.html':'/admin/estadisticas');return;}

    if(!dialog.open){previousFocus=document.activeElement;dialog.showModal();}
    const close='<button type="button" data-close style="float:right" aria-label="Cerrar">×</button>';
    let content='';
    if(mode==='register') content=`<h2>Crear cuenta</h2><p>Elegí tu perfil. Durante esta etapa todos los cálculos siguen siendo gratuitos.</p><form><label>Nombre y apellido<input name="name" required maxlength="120" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" autocomplete="email"></label>${profileFields()}<label>Contraseña<input name="password" type="password" required minlength="10" maxlength="128" autocomplete="new-password" aria-describedby="co-password-help"></label><small id="co-password-help">Al menos 10 caracteres, con letras y números.</small><button class="co-primary">Crear cuenta</button></form><button data-switch="login">Ya tengo cuenta</button>`;
    if(mode==='login') content='<h2>Ingresar</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><label>Contraseña<input name="password" type="password" required maxlength="128" autocomplete="current-password"></label><button class="co-primary">Ingresar</button></form><p class="co-actions"><button data-switch="register">Crear cuenta</button><button data-switch="recovery">Olvidé mi contraseña</button></p>';
    if(mode==='recovery') content='<h2>Recuperar acceso</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><button class="co-primary">Enviar enlace</button></form>';
    if(mode==='profile') content=`<h2>Mi cuenta</h2><p>${esc(account?.user.email)}</p><p>Acceso gratuito ilimitado habilitado automáticamente durante esta etapa.</p><form>${profileFields(account?.profile||{})}<button class="co-primary">Guardar perfil</button></form>`;

    if(mode==='contact') content=`<h2>Enviar consulta</h2><form><label>Nombre<input name="nombre" required maxlength="160" value="${esc(account?.user.name)}" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" value="${esc(account?.user.email)}" autocomplete="email"></label><label>Tipo de usuario<select name="account_type" required>${options(account?.profile?.account_type)}</select></label><label data-org ${!account?.profile?.account_type||account?.profile?.account_type==='empleado'?'hidden':''}>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(account?.profile?.organization_name)}"></label><label>Motivo<select name="motivo"><option>Consulta técnica</option><option>Consulta sobre una liquidación</option><option>Sugerencia</option></select></label><label>Mensaje<textarea name="mensaje" required maxlength="5000" rows="5" style="padding:10px;border:1px solid #cbd5e1;border-radius:8px"></textarea></label><input name="website" tabindex="-1" autocomplete="off" hidden><button class="co-primary">Enviar consulta</button></form>`;
    dialog.innerHTML=close+content+'<p class="co-account-feedback" role="status" aria-live="polite"></p>';
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    dialog.querySelectorAll('[data-switch]').forEach(b=>b.onclick=()=>open(b.dataset.switch));
    if(mode==='login'||mode==='register'){
      const social=document.createElement('div');social.className='co-actions';social.style.margin='16px 0';
      social.innerHTML=['google','facebook'].map(provider=>`<button type="button" data-social="${provider}" data-social-mode="${mode}" ${socialProviders[provider]?'':'disabled'}>${socialButtonContent(provider,mode,!!socialProviders[provider])}</button>`).join('');
      dialog.querySelector('form').before(social);
      social.querySelectorAll('[data-social]').forEach(button=>button.onclick=()=>{
        const url=new URL(`${apiOrigin}/api/oauth.php`);url.searchParams.set('action','start');url.searchParams.set('provider',button.dataset.social);url.searchParams.set('target',isCalculator?'calculator':'landing');location.assign(url.href);
      });
    }
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
        if(mode==='profile'){
          await request('profile',values,false,'PUT');account=await request('me');renderBar();
          if(document.getElementById('root')){
            feedback('Perfil guardado. Abriendo la calculadora…');
            const result=await request('handoff-create',{});
            const target=new URL('/',window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
            target.hash=new URLSearchParams({co_login:result.code}).toString();
            location.assign(target.href);
          }else{dialog.close();}
        }
        if(mode==='recovery'){const result=await request('forgot-password',values,true);feedback(result.message);}
        if(mode==='contact'){
          const fd=new FormData(form); const response=await fetch(`${apiOrigin}/send-contact.php`,{method:'POST',body:fd});
          const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.message||'No se pudo enviar.');
          form.hidden=true;feedback('Consulta enviada. Gracias por contactarnos.');
        }
      }catch(error){feedback(error.message);}finally{submit.disabled=false;}
    });
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
  function enrichAdminModal(){
    document.querySelectorAll('[data-admin-submit]').forEach(submit=>{
      const form=submit.closest('form');if(!form||form.parentElement.querySelector('[data-admin-social]'))return;
      const group=document.createElement('div');group.className='co-actions';group.dataset.adminSocial='';group.style.cssText='display:flex;gap:8px;flex-wrap:wrap;margin:12px 0';
      group.innerHTML=['google','facebook'].map(provider=>`<button type="button" data-social="${provider}" data-social-mode="login" ${socialProviders[provider]?'':'disabled'} style="padding:10px;border:1px solid #cbd5e1;border-radius:8px">${socialButtonContent(provider,'login',!!socialProviders[provider])}</button>`).join('');
      form.before(group);
      group.querySelectorAll('[data-social]').forEach(button=>button.onclick=()=>{
        const url=new URL(`${apiOrigin}/api/oauth.php`);url.searchParams.set('action','start');url.searchParams.set('provider',button.dataset.social);url.searchParams.set('target','landing');location.assign(url.href);
      });
    });
  }
  const observer=new MutationObserver(()=>{enrichContactForms();enrichAdminModal();syncHeader();});observer.observe(document.body,{childList:true,subtree:true});
  // Un código de un solo uso permite pasar de la landing a Render sin volver a ingresar.
  document.addEventListener('click',async event=>{
    if(isCalculator || !account || event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
    const link=event.target.closest('a[href]');if(!link)return;
    const target=new URL(link.href,location.href);
    const calculator=new URL(window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
    if(target.origin!==calculator.origin || target.pathname!=='/')return;
    event.preventDefault();event.stopPropagation();
    try{const result=await request('handoff-create',{});target.hash=new URLSearchParams({co_login:result.code}).toString();location.assign(target.href);}
    catch(error){await open('login');feedback(error.message);}
  },true);
  renderBar();enrichContactForms();syncHeader();
  async function restoreSession(){
    const hash=new URLSearchParams(location.hash.slice(1));const code=hash.get('co_login');
    if(hash.get('co_logout')==='1'){
      hash.delete('co_logout');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      // La landing puede conservar otra sesión propia tras el traslado a Render.
      if(token){try{await request('logout',{},true);}catch(_){}}
      token='';account=null;sessionStorage.removeItem(key);sessionStorage.removeItem('co_admin_token');localStorage.removeItem('co_admin_token');renderBar();return;
    }
    const oauthError=hash.get('co_oauth_error');
    if(oauthError){
      const reference=hash.get('co_oauth_ref')||'';hash.delete('co_oauth_ref');
      hash.delete('co_oauth_error');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      await open('login');
      const messages={cancelled:'Cancelaste el acceso. Podés volver a intentarlo.',email_required:'El proveedor no compartió tu email. Usá el registro con email.',existing_account:'Ese email ya tiene una cuenta. Ingresá con email y contraseña.',account_inactive:'Tu cuenta no está activa. Contactá al administrador.'};
      feedback((messages[oauthError]||'No se pudo completar el acceso. Intentá nuevamente.')+(reference?` Referencia: ${reference}`:''));
    }
    if(code){
      hash.delete('co_login');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      try{const result=await request('handoff-redeem',{code});token=result.token;sessionStorage.setItem(key,token);}
      catch(error){await open('login');feedback(error.message);return;}
    }
    if(!token)return;
    try{account=await request('me');renderBar();if(!account.profile)await open('profile');}
    catch(error){if(error.status===401||error.status===403){token='';sessionStorage.removeItem(key);}renderBar();}
  }
  fetch(`${apiOrigin}/api/oauth.php?action=providers`).then(r=>r.json()).then(result=>{
    if(result.ok && result.providers){socialProviders=result.providers;if(document.querySelector('[data-social]')){document.querySelectorAll('[data-social]').forEach(b=>{const enabled=!!socialProviders[b.dataset.social];b.disabled=!enabled;b.innerHTML=socialButtonContent(b.dataset.social,b.dataset.socialMode||'login',enabled);});}}
  }).catch(()=>{});
  restoreSession();
})();
