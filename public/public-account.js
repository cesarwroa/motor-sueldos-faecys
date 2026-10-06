(() => {
  'use strict';
  const apiOrigin = 'https://calculadoradecomercio.com.ar';
  const profilesUrl = `${apiOrigin}/api/public-accounts.php`;
  const authUrl = `${apiOrigin}/api/`;
  const labels = {empleado:'Empleado', empresa:'Empresa', estudio:'Estudio contable', sindicato:'Sindicato'};
  const key = 'co_public_session_v1';
  let token='';
  function rememberToken(value){
    token=value;
    try{if(value)localStorage.setItem(key,value);else localStorage.removeItem(key);}catch(_){}
    try{if(value)sessionStorage.setItem(key,value);else sessionStorage.removeItem(key);}catch(_){}
  }
  try{token=localStorage.getItem(key)||sessionStorage.getItem(key)||'';}catch(_){}
  if(token)rememberToken(token);
  let accountRequest=null;
  function fetchAccount(remember=false){
    if(!accountRequest)accountRequest=request(remember?'remember-session':'me',remember?{}:undefined).finally(()=>{accountRequest=null;});
    return accountRequest;
  }
  let account = null;
  let page = 1;
  let socialProviders = {google:false,facebook:false};
  let providersLoaded=false,providersFailed=false,providersPromise=null;
  try{const cached=JSON.parse(localStorage.getItem('co_providers_v1')||'null');if(cached?.expires>Date.now()&&typeof cached.providers?.google==='boolean'&&typeof cached.providers?.facebook==='boolean'){socialProviders=cached.providers;providersLoaded=true;}}catch(_){}
  const isCalculator = !document.getElementById('root') && location.pathname !== '/admin/app';
  let gate = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const socialLogos = {
    google:'<svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.17 7.09-10.32 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.9 23.9 0 0 0 0 24c0 3.87.93 7.53 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.9-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.17 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>',
    facebook:'<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="12" fill="#1877F2"/><path fill="#fff" d="M16.67 15.47l.53-3.47h-3.33V9.75c0-.95.46-1.88 1.96-1.88h1.51V4.92s-1.37-.23-2.67-.23c-2.72 0-4.5 1.65-4.5 4.64V12H7.15v3.47h3.02v8.36a12.08 12.08 0 0 0 3.7 0v-8.36z"/></svg>'
  };
  function socialButtonContent(provider,mode,enabled){
    if(!providersLoaded)return socialLogos[provider]+`<span>${providersFailed?'Reintentá la conexión':'Comprobando acceso'} con ${provider==='google'?'Google':'Facebook'}…</span>`;
    const action=mode==='register'?'Registrate':'Ingresá';
    return socialLogos[provider]+`<span>${action} con ${provider==='google'?'Google':'Facebook'}${enabled?'':' · Próximamente'}</span>`;
  }
  const options = selected => '<option value="">Seleccioná una opción</option>' + Object.entries(labels).map(([value,label]) => `<option value="${value}" ${value===selected?'selected':''}>${label}</option>`).join('');
  async function request(action, data, legacy=false, method=data?'POST':'GET') {
    const url = new URL(legacy?authUrl:profilesUrl); url.searchParams.set('action',action);
    if (action==='admin-users') url.searchParams.set('page',page);
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),16000);
    let res;
    try{res=await fetch(url,{method,signal:controller.signal,headers:{...(data?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{})},...(data?{body:JSON.stringify(data)}:{})});}
    catch(error){if(error.name==='AbortError')throw new Error('La conexión está tardando. Revisá tu conexión y volvé a intentar.');throw error;}
    finally{clearTimeout(timer);} 
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
  .co-account-dialog{box-sizing:border-box;width:calc(100% - 24px);max-width:620px;max-height:calc(var(--co-viewport-height,100dvh) - 24px);overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;border:1px solid #cbd5e1;border-radius:16px;padding:24px;background:white;color:#172033;font:15px system-ui;box-shadow:0 16px 70px #0003}
  .co-account-dialog [data-close]{position:absolute;right:14px;top:14px;width:36px!important;height:36px;padding:4px!important;float:none!important}.co-account-dialog h2{padding-right:35px}.co-account-dialog::backdrop{background:#0f172a99}.co-account-dialog h2{font-size:23px;margin:0 0 8px}.co-account-dialog p{margin:10px 0;line-height:1.5}.co-account-dialog form{display:grid;gap:14px;margin-top:18px}
  .co-account-dialog label,.co-contact-profile label{display:grid;gap:6px;color:#334155;font:14px system-ui}.co-account-dialog input:not([type=checkbox]),.co-account-dialog select,.co-contact-profile input,.co-contact-profile select{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#172033;font:inherit}
  .co-account-dialog .co-check{display:flex;gap:9px;align-items:flex-start}.co-account-dialog .co-check input{width:18px;height:18px;flex-shrink:0}.co-account-dialog .co-actions{display:flex;flex-wrap:wrap;gap:8px}.co-account-feedback{color:#9f1239;white-space:pre-wrap}.co-account-dialog [hidden],.co-contact-profile [hidden]{display:none!important}
  .co-contact-profile{display:grid;gap:12px;margin:12px 0;padding:14px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px}.co-account-user{border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:12px 0;overflow-wrap:anywhere}.co-account-dialog button:disabled{opacity:.6;cursor:wait}
  `;
  style.textContent+=`
  .co-account-dialog,.co-account-bar{-webkit-text-size-adjust:100%;text-size-adjust:100%}
  .co-account-dialog input:not([type=checkbox]),.co-account-dialog select,.co-account-dialog textarea{font-size:16px;min-height:44px}
  .co-account-dialog .co-social-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0}
  .co-account-dialog .co-social-actions button{width:100%;min-width:0;min-height:48px;font:600 15px/1.35 system-ui}
  .co-account-dialog .co-social-actions svg{width:20px;height:20px;flex:0 0 20px}
  .co-account-dialog button{min-height:44px}.co-account-dialog [data-close]{width:44px!important;height:44px;padding:4px!important;font-size:24px}
  body:has(.co-account-dialog[open]){overflow:hidden}
  @media(max-width:600px){
    .co-account-dialog{position:fixed;inset:auto;top:calc(var(--co-viewport-top,0px) + 12px);left:12px;right:12px;margin:0 auto;width:calc(100% - 24px);max-width:none;padding:20px;border-radius:14px;font-size:15px;line-height:1.4}
    .co-account-dialog h2{font-size:23px;line-height:1.25;padding-right:44px;margin-bottom:12px}
    .co-account-dialog .co-social-actions{grid-template-columns:minmax(0,1fr);margin:12px 0}
    .co-account-dialog .co-actions{gap:10px}.co-account-dialog form{gap:12px;margin-top:14px}
    .co-account-dialog .co-actions button{flex:1 1 140px}.co-account-dialog [data-close]{flex:none}
    .co-account-dialog label{font-size:14px}.co-account-dialog p{margin:10px 0}
    .co-account-bar{padding:12px;gap:10px}.co-account-bar>.co-actions{display:flex;gap:8px;flex-wrap:wrap}.co-account-bar button{min-height:44px;padding:9px 12px}
  }`;
  document.head.append(style);
  function syncDialogViewport(){
    const viewport=window.visualViewport;
    const values={'--co-viewport-height':`${Math.floor(viewport?.height||window.innerHeight)}px`,'--co-viewport-top':`${Math.max(0,Math.floor(viewport?.offsetTop||0))}px`};
    for(const [name,value] of Object.entries(values))if(document.documentElement.style.getPropertyValue(name)!==value)document.documentElement.style.setProperty(name,value);
  }
  syncDialogViewport();window.addEventListener('resize',syncDialogViewport,{passive:true});window.visualViewport?.addEventListener('resize',syncDialogViewport,{passive:true});window.visualViewport?.addEventListener('scroll',syncDialogViewport,{passive:true});
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
      gate.innerHTML='<h1>Ingresá para usar la calculadora</h1><p>Creá tu cuenta o ingresá con tu email.</p><button data-open="register">Crear cuenta</button><button data-open="login">Ya tengo cuenta</button>';
      bar.after(gate);gate.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>open(b.dataset.open));
    }
    gate.hidden=!locked;
  }
  document.addEventListener('co-auth-required',()=>{
    token='';account=null;rememberToken('');renderBar();open('login');feedback('Ingresá para continuar.');
  });
  const dialog=document.createElement('dialog'); dialog.className='co-account-dialog'; dialog.setAttribute('aria-label','Cuenta de la calculadora'); document.body.append(dialog);
  let previousFocus=null;
  dialog.addEventListener('close',()=>previousFocus?.focus({preventScroll:true}));
  dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
  function renderBar(){
    bar.innerHTML=`<span><strong>${account?`Hola, ${esc(account.user.name)}`:'Creá tu cuenta en la calculadora'}</strong></span><span class="co-actions">${account?'<button data-open="profile">Mi cuenta</button> <button data-open="news">Novedades</button>':'<button data-open="login">Ingresar</button> <button class="co-primary" data-open="register">Registrarme</button>'}${account?.is_admin?' <button data-open="admin">Registros y estadísticas</button> <button data-open="news-admin">Administrar novedades</button> <button data-calculator-admin>Administrar calculadora</button>':''} <button data-open="contact">Enviar consulta</button>${account?' <button data-logout>Salir</button>':''}</span>`;
    syncAccess();
    if(typeof newsPanel!=='undefined')loadNews();
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
      try{await request('logout',{});}catch(error){if(error.status!==401&&error.status!==403){open('profile');feedback(error.message);return;}}
      token=''; account=null; rememberToken('');
      sessionStorage.removeItem('co_pending_link_v1');sessionStorage.removeItem('co_admin_token');localStorage.removeItem('co_admin_token');
      location.assign(`${apiOrigin}/#co_logout=1`);
    });
  }
  function renderLinkButtons(){
    const group=dialog.querySelector('[data-link-providers]');if(!group)return;
    group.innerHTML=(account?.identities||[]).map(provider=>`<span style="display:inline-flex;align-items:center;gap:10px;padding:8px">${socialLogos[provider]||''}${provider==='google'?'Google':'Facebook'}</span>`).join('')||'<span>Email y contraseña</span>';
  }
  async function confirmPendingLink(){
    const pending=sessionStorage.getItem('co_pending_link_v1');if(!pending)return;
    const response=await fetch(`${apiOrigin}/api/oauth.php?action=confirm-link`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({ticket:pending})});
    const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.message||'No se pudo confirmar la cuenta.');
    sessionStorage.removeItem('co_pending_link_v1');
  }
  function feedback(message){dialog.querySelector('[role=status]').textContent=message;}
  function profileFields(profile={}){
    return `<label>Tipo de cuenta<select name="account_type" required>${options(profile.account_type)}</select></label><label data-org ${!profile.account_type||profile.account_type==='empleado'?'hidden':''}>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(profile.organization_name)}"></label><label class="co-check"><input type="checkbox" name="newsletter_opt_in" ${Number(profile.newsletter_opt_in)?'checked':''}>Quiero recibir novedades sobre funciones, acuerdos, escalas y convenios. Puedo desactivar los emails o dar de baja mi cuenta cuando quiera.</label>`;
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
        await confirmPendingLink();if(!account)account=await fetchAccount();renderBar();
        if(!account.profile){mode='profile';}
        else if(document.getElementById('root')){
          const result=await request('handoff-create',{});
          const target=new URL('/',window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
          target.hash=new URLSearchParams({co_login:result.code}).toString();location.assign(target.href);return;
        }else{if(dialog.open)dialog.close();return;}
      }catch(error){if(error.status===401||error.status===403){token='';rememberToken('');account=null;renderBar();}}
    }

    if(mode==='admin'){location.assign(document.getElementById('root')?'/admin-uso.html?v=20261006-perfiles-2':'/admin/estadisticas?v=20261006-perfiles-2');return;}

    if(!dialog.open){previousFocus=document.activeElement;dialog.showModal();}
    if(mode==='news'){await showNewsInbox();return;}
    if(mode==='news-admin'){await showNewsAdmin();return;}
    const close='<button type="button" data-close style="float:right" aria-label="Cerrar">×</button>';
    let content='';
    if(mode==='register') content=`<h2>Crear cuenta</h2><p>Elegí tu perfil para crear tu cuenta.</p><form><label>Nombre y apellido<input name="name" required maxlength="120" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" autocomplete="email"></label>${profileFields()}<label>Contraseña<input name="password" type="password" required minlength="10" maxlength="128" autocomplete="new-password" aria-describedby="co-password-help"></label><small id="co-password-help">Al menos 10 caracteres, con letras y números.</small><button class="co-primary">Crear cuenta</button></form><button data-switch="login">Ya tengo cuenta</button>`;
    if(mode==='login') content='<h2>Ingresar</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><label>Contraseña<input name="password" type="password" required maxlength="128" autocomplete="current-password"></label><button class="co-primary">Ingresar</button></form><p class="co-actions"><button data-switch="register">Crear cuenta</button><button data-switch="recovery">Olvidé mi contraseña</button></p>';
    if(mode==='recovery') content='<h2>Recuperar acceso</h2><form><label>Email<input name="email" type="email" required autocomplete="email"></label><button class="co-primary">Enviar enlace</button></form>';
    if(mode==='profile') content=`<h2>Mi cuenta</h2><p>${esc(account?.user.email)}</p><form>${profileFields(account?.profile||{})}<button class="co-primary">Guardar perfil</button></form>${account?.is_admin?'':'<hr><p>Podés dar de baja tu cuenta cuando quieras. Se deshabilitará el acceso y se cerrarán todas tus sesiones. No recibirás más novedades por email. Esta baja no elimina los registros de liquidaciones existentes.</p><button class="co-danger" data-deactivate>Darme de baja</button>'}`;

    if(mode==='contact') content=`<h2>Enviar consulta</h2><form><label>Nombre<input name="nombre" required maxlength="160" value="${esc(account?.user.name)}" autocomplete="name"></label><label>Email<input name="email" type="email" required maxlength="220" value="${esc(account?.user.email)}" autocomplete="email"></label><label>Tipo de usuario<select name="account_type" required>${options(account?.profile?.account_type)}</select></label><label data-org ${!account?.profile?.account_type||account?.profile?.account_type==='empleado'?'hidden':''}>Nombre de la empresa, estudio o sindicato<input name="organization_name" maxlength="190" value="${esc(account?.profile?.organization_name)}"></label><label>Motivo<select name="motivo"><option>Consulta técnica</option><option>Consulta sobre una liquidación</option><option>Sugerencia</option></select></label><label>Mensaje<textarea name="mensaje" required maxlength="5000" rows="5" style="padding:10px;border:1px solid #cbd5e1;border-radius:8px"></textarea></label><input name="website" tabindex="-1" autocomplete="off" hidden><button class="co-primary">Enviar consulta</button></form>`;
    dialog.innerHTML=close+content+'<p class="co-account-feedback" role="status" aria-live="polite"></p>';
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();
    dialog.querySelectorAll('[data-switch]').forEach(b=>b.onclick=()=>open(b.dataset.switch));
    if(mode==='login'||mode==='register'){
      const social=document.createElement('div');social.className='co-social-actions';
      social.innerHTML=['google','facebook'].map(provider=>`<button type="button" data-social="${provider}" data-social-mode="${mode}" ${socialProviders[provider]||(!providersLoaded&&providersFailed)?'':'disabled'}>${socialButtonContent(provider,mode,!!socialProviders[provider])}</button>`).join('');
      dialog.querySelector('form').before(social);
      social.querySelectorAll('[data-social]').forEach(button=>button.onclick=()=>startSocialLogin(button));
    }
    if(mode==='profile'){
      const section=document.createElement('section');section.innerHTML='<p>Métodos de ingreso de tu cuenta:</p><div class="co-actions" data-link-providers></div>';
      dialog.querySelector('form').after(section);renderLinkButtons();
    }
    dialog.querySelector('[data-deactivate]')?.addEventListener('click',()=>{
      dialog.innerHTML='<button data-close aria-label="Cerrar">×</button><h2>Dar de baja mi cuenta</h2><p>Se deshabilitará tu acceso y dejarás de recibir emails. Para confirmar, escribí DARME DE BAJA.</p><form><label>Confirmación<input name="confirmation" required autocomplete="off"></label><button class="co-danger">Confirmar baja</button></form><button data-cancel>Conservar mi cuenta</button><p class="co-account-feedback" role="status"></p>';
      dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-cancel]').onclick=()=>open('profile');
      dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const result=await request('deactivate',{confirmation:e.target.elements.confirmation.value});token='';account=null;rememberToken('');sessionStorage.removeItem('co_pending_link_v1');sessionStorage.removeItem('co_admin_token');localStorage.removeItem('co_admin_token');renderBar();dialog.innerHTML='<h2>Cuenta dada de baja</h2><p>'+esc(result.message)+'</p><button data-close>Cerrar</button>';dialog.querySelector('[data-close]').onclick=()=>dialog.close();}catch(error){feedback(error.message);b.disabled=false;}};
    });
    bindProfile(dialog);
    const form=dialog.querySelector('form');
    if(form)form.addEventListener('submit',async event=>{
      event.preventDefault(); const submit=form.querySelector('button');submit.disabled=true;feedback('');
      const values=Object.fromEntries(new FormData(form));values.newsletter_opt_in=!!form.querySelector('[name=newsletter_opt_in]')?.checked;
      try{
        if(mode==='register'){await request('register',values);await open('login');feedback('Cuenta creada. Ingresá con tu email y contraseña.');}
        if(mode==='login'){
          values.remember_session=true;feedback('Ingresando…');const result=await request('login',values,true);rememberToken(result.token);
          try{await confirmPendingLink();account=await fetchAccount();}catch(error){token='';rememberToken('');throw error;}
          renderBar();if(!account.profile)await open('profile');else dialog.close();
        }
        if(mode==='profile'){
          await request('profile',values,false,'PUT');account=await fetchAccount();renderBar();
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
    dialog.scrollTop=0;syncDialogViewport();
    if(window.matchMedia('(max-width:600px)').matches)dialog.querySelector('[data-close]')?.focus({preventScroll:true});
    else dialog.querySelector('input,select')?.focus({preventScroll:true});
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
      group.innerHTML=['google','facebook'].map(provider=>`<button type="button" data-social="${provider}" data-social-mode="login" ${socialProviders[provider]||(!providersLoaded&&providersFailed)?'':'disabled'} style="padding:10px;border:1px solid #cbd5e1;border-radius:8px">${socialButtonContent(provider,'login',!!socialProviders[provider])}</button>`).join('');
      form.before(group);
      group.querySelectorAll('[data-social]').forEach(button=>button.onclick=()=>startSocialLogin(button));
    });
  }
  const observer=new MutationObserver(()=>{enrichContactForms();enrichAdminModal();syncHeader();});observer.observe(document.body,{childList:true,subtree:true});
  // Trasladar la sesión entre landing y calculadora en ambos sentidos.
  document.addEventListener('click',async event=>{
    if(!token || event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;
    const link=event.target.closest('a[href]');if(!link)return;
    let target=new URL(link.href,location.href);
    const calculator=new URL(window.CALCULADORA_URL||'https://app.calculadoradecomercio.com.ar/');
    if(document.getElementById('root')){
      if(target.origin!==calculator.origin || target.pathname!=='/')return;
    }else{
      if(![apiOrigin,'https://www.calculadoradecomercio.com.ar'].includes(target.origin) || target.pathname!=='/')return;
      target=new URL(apiOrigin+'/'+target.search);
    }
    event.preventDefault();event.stopPropagation();
    try{const result=await request('handoff-create',{});target.hash=new URLSearchParams({co_login:result.code}).toString();location.assign(target.href);}
    catch(error){await open('login');feedback(error.message);}
  },true);
  let newsItems=[], newsGeneration=0, newsModal=null;
  const newsPanel=document.createElement('section');newsPanel.className='co-news-panel';bar.after(newsPanel);
  const newsStyle=document.createElement('style');newsStyle.textContent=`.co-news-panel{font:15px system-ui;color:#172033;max-width:1000px;margin:12px auto;padding:0 18px}.co-news-card{padding:18px;margin:12px 0;border:1px solid #bfdbfe;border-radius:12px;background:#f8fbff}.co-news-card img,.co-news-card video,.co-news-preview img,.co-news-preview video{width:100%;max-height:420px;object-fit:contain;border-radius:8px}.co-news-card iframe,.co-news-preview iframe{width:100%;aspect-ratio:16/9;border:0}.co-news-text{white-space:pre-wrap;overflow-wrap:anywhere}.co-account-dialog textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px;font:inherit}.co-news-card button{padding:8px;border:1px solid #cbd5e1;border-radius:8px;background:white;cursor:pointer}.co-news-modal{width:min(760px,calc(100vw - 28px))}.co-news-preview{padding:16px;border:1px solid #bfdbfe;border-radius:10px;margin:12px 0}.co-danger{color:#be123c!important;border-color:#be123c!important}`;document.head.append(newsStyle);
  function newsContent(n){
    const image=/^https:\/\/calculadoradecomercio\.com\.ar\/uploads\/novedades\/[a-f0-9]{32}\.(jpg|png|gif|webp)$/.test(n.image_url||'')?`<img src="${esc(n.image_url)}" alt="Imagen de ${esc(n.title)}" loading="lazy">`:'';
    let video='';
    if(/^https:\/\/www\.youtube-nocookie\.com\/embed\/[A-Za-z0-9_-]{11}$/.test(n.video_url||''))video=`<iframe src="${esc(n.video_url)}" title="Video de ${esc(n.title)}" loading="lazy" allowfullscreen></iframe>`;
    else if(/^https:\/\/calculadoradecomercio\.com\.ar\/uploads\/novedades\/[a-f0-9]{32}\.(mp4|webm)$/.test(n.video_url||''))video=`<video src="${esc(n.video_url)}" controls preload="metadata"></video>`;
    return `<h2>${esc(n.title)}</h2><p class="co-news-text">${esc(n.body)}</p>${image}${video}`;
  }
  async function loadNews(auto=true){
    const generation=++newsGeneration;if(!account){newsItems=[];newsPanel.replaceChildren();return;}
    try{const result=await request('news-feed');if(generation!==newsGeneration||!account)return;newsItems=result.news;
      newsPanel.innerHTML=newsItems.filter(n=>!n.read_at&&n.display_mode==='card').map(n=>`<article class="co-news-card">${newsContent(n)}<button data-read-news="${esc(n.id)}">Marcar como leída</button></article>`).join('');
      newsPanel.querySelectorAll('[data-read-news]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await request('news-read',{id:b.dataset.readNews});await loadNews(false);}catch(e){b.disabled=false;b.textContent='No se pudo marcar. Reintentar';}});
      const pending=newsItems.find(n=>!n.read_at&&n.display_mode==='modal');if(auto&&pending&&!dialog.open&&account.profile)showNewsModal(pending);
    }catch(_){/* Las novedades no interrumpen la calculadora. */}
  }
  function showNewsModal(n){
    if(newsModal?.open)return;
    newsModal=document.createElement('dialog');newsModal.className='co-account-dialog co-news-modal';newsModal.setAttribute('aria-label','Novedad de la calculadora');
    newsModal.innerHTML=newsContent(n)+'<p class="co-actions"><button data-later>Más tarde</button><button class="co-primary" data-read>Entendido, marcar como leída</button></p><p role="status"></p>';document.body.append(newsModal);const focus=document.activeElement;
    newsModal.onclose=()=>{newsModal.remove();focus?.focus();};newsModal.querySelector('[data-later]').onclick=()=>newsModal.close();
    newsModal.querySelector('[data-read]').onclick=async event=>{event.target.disabled=true;try{await request('news-read',{id:n.id});newsModal.close();await loadNews(false);}catch(e){event.target.disabled=false;newsModal.querySelector('[role=status]').textContent=e.message;}};newsModal.showModal();
  }
  async function showNewsInbox(){
    await loadNews(false);dialog.innerHTML='<button data-close aria-label="Cerrar">×</button><h2>Novedades</h2>'+(newsItems.length?newsItems.map(n=>`<article class="co-news-card">${newsContent(n)}${n.read_at?'<small>Leída</small>':`<button data-read-news="${esc(n.id)}">Marcar como leída</button>`}</article>`).join(''):'<p>No hay novedades disponibles.</p>')+'<p class="co-account-feedback" role="status"></p>';
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelectorAll('[data-read-news]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await request('news-read',{id:b.dataset.readNews});await showNewsInbox();}catch(e){feedback(e.message);b.disabled=false;}});
  }
  async function showNewsAdmin(edit=null){
    if(!account?.is_admin)return;
    dialog.innerHTML='<button data-close aria-label="Cerrar">×</button><h2>Administrar novedades</h2><p>Creá un borrador, revisá la vista previa y publicalo. Los emails se envían solo a cuentas activas que aceptaron novedades.</p>'+`<form data-news-editor><input type="hidden" name="id" value="${esc(edit?.id)}"><label>Título<input name="title" maxlength="160" required value="${esc(edit?.title)}"></label><label>Texto<textarea name="body" rows="5" maxlength="10000">${esc(edit?.body)}</textarea></label><label>Imagen<input type="file" data-news-file="image_url" accept="image/jpeg,image/png,image/gif,image/webp"></label><input type="hidden" name="image_url" value="${esc(edit?.image_url)}"><button type="button" data-remove-media="image_url">Quitar imagen</button><label>Video (MP4 o WebM, hasta 20 MB)<input type="file" data-news-file="video_url" accept="video/mp4,video/webm"></label><label>O enlace de YouTube<input name="video_url" maxlength="500" value="${esc(edit?.video_url)}" placeholder="https://www.youtube.com/watch?v=..."></label><button type="button" data-remove-media="video_url">Quitar video</button><label>Destinatarios<select name="audience"><option value="all">Todos los perfiles</option>${Object.entries(labels).map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select></label><label>Canal<select name="channel"><option value="system">Por sistema</option><option value="email">Por email</option><option value="both">Email y sistema</option></select></label><label>Cómo se muestra en el sistema<select name="display_mode"><option value="card">Tarjeta debajo del acceso</option><option value="modal">Ventana al ingresar hasta marcarla como leída</option></select></label><p>El video en el email aparece como enlace para abrirlo.</p><div class="co-actions"><button type="button" data-preview>Vista previa</button><button class="co-primary">Guardar borrador</button><button type="button" data-new>Nueva novedad</button></div></form><section class="co-news-preview" hidden></section><p class="co-account-feedback" role="status" aria-live="polite"></p><h3>Novedades guardadas</h3><section data-news-list>Cargando…</section>`;
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();const form=dialog.querySelector('form');
    for(const name of ['audience','channel','display_mode'])if(edit)form.elements[name].value=edit[name];
    let uploading=0;const values=()=>Object.fromEntries(new FormData(form));
    function normalizedPreview(){const n=values();const m=n.video_url.match(/^https:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube-nocookie\.com\/embed\/)([A-Za-z0-9_-]{11})(?:[?&].*)?$/);if(m)n.video_url=`https://www.youtube-nocookie.com/embed/${m[1]}`;return n;}
    dialog.querySelector('[data-preview]').onclick=()=>{const preview=dialog.querySelector('.co-news-preview');preview.hidden=false;preview.innerHTML=newsContent(normalizedPreview());};
    dialog.querySelector('[data-new]').onclick=()=>showNewsAdmin();
    dialog.querySelectorAll('[data-remove-media]').forEach(b=>b.onclick=()=>{form.elements[b.dataset.removeMedia].value='';form.querySelector(`[data-news-file="${b.dataset.removeMedia}"]`).value='';});
    form.querySelectorAll('[data-news-file]').forEach(input=>input.onchange=async()=>{
      const file=input.files[0];if(!file)return;if(file.size>20*1024*1024){feedback('El archivo debe pesar hasta 20 MB.');input.value='';return;}
      uploading++;feedback('Subiendo archivo…');const fd=new FormData();fd.append('file',file);
      try{const response=await fetch(`${profilesUrl}?action=news-upload`,{method:'POST',headers:{Authorization:`Bearer ${token}`},body:fd});const result=await response.json();if(!response.ok||!result.ok)throw new Error(result.message||'No se pudo subir.');form.elements[input.dataset.newsFile].value=result.url;feedback('Archivo subido. Podés revisar la vista previa.');}catch(e){feedback(e.message);}finally{uploading--;}
    });
    form.onsubmit=async event=>{event.preventDefault();if(uploading){feedback('Esperá a que termine la subida.');return;}const submit=form.querySelector('button.co-primary');submit.disabled=true;try{const result=await request('news-save',values());form.elements.id.value=result.id;feedback('Borrador guardado. Revisá la vista previa antes de publicar.');await listNews();}catch(e){feedback(e.message);}finally{submit.disabled=false;}};
    async function listNews(){
      const result=await request('news-list');const list=dialog.querySelector('[data-news-list]');if(!list)return;
      list.innerHTML=result.news.map(n=>`<article class="co-account-user"><strong>${esc(n.title)}</strong><p>${esc(({draft:'Borrador',published:'Publicada',archived:'Archivada'})[n.status])} · ${esc(({system:'Sistema',email:'Email',both:'Email y sistema'})[n.channel])}</p>${n.channel!=='system'?`<p>Emails: ${Number(n.sent)} aceptados por el servidor, ${Number(n.pending)} pendientes, ${Number(n.failed)} fallidos, ${Number(n.uncertain)} sin confirmación, ${Number(n.skipped)} omitidos.</p>`:''}<div class="co-actions"><button data-review="${esc(n.id)}">Ver</button>${n.status==='draft'?`<button data-edit="${esc(n.id)}">Editar</button><button data-publish="${esc(n.id)}">Publicar${n.channel!=='system'?' y enviar emails':''}</button>`:''}${n.status==='published'&&Number(n.pending)>0?`<button data-send="${esc(n.id)}">Continuar envío de emails</button>`:''}${n.status==='published'&&Number(n.failed)>0?`<button data-retry="${esc(n.id)}">Reintentar emails fallidos</button>`:''}${n.status!=='archived'?`<button data-archive="${esc(n.id)}">Archivar</button>`:''}</div></article>`).join('')||'<p>Todavía no hay novedades.</p>';
      const find=id=>result.news.find(n=>n.id===id);
      list.querySelectorAll('[data-review]').forEach(b=>b.onclick=()=>{const p=dialog.querySelector('.co-news-preview');p.hidden=false;p.innerHTML=newsContent(find(b.dataset.review));p.scrollIntoView({block:'nearest'});});
      list.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>showNewsAdmin(find(b.dataset.edit)));
      async function send(id){let result;do{feedback('Enviando emails por lotes. Mantené abierta esta ventana…');result=await request('news-send',{id});}while(result.pending>0&&result.processed>0);feedback('Proceso de envío terminado. Revisá los contadores: aceptado por el servidor no confirma la llegada a la bandeja.');}
      list.querySelectorAll('[data-publish]').forEach(b=>b.onclick=async()=>{const n=find(b.dataset.publish);if(!confirm(`¿Publicar "${n.title}"${n.channel!=='system'?' y enviar emails a quienes aceptaron novedades':''}?`))return;b.disabled=true;try{await request('news-publish',{id:n.id});if(n.channel!=='system')await send(n.id);else feedback('Novedad publicada.');await listNews();await loadNews(false);}catch(e){feedback(e.message+' Si el envío quedó pendiente, usá Continuar envío.');b.disabled=false;}});
      list.querySelectorAll('[data-send]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await send(b.dataset.send);await listNews();}catch(e){feedback(e.message);b.disabled=false;}});
      list.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await request('news-retry-failed',{id:b.dataset.retry});await send(b.dataset.retry);await listNews();}catch(e){feedback(e.message);b.disabled=false;}});
      list.querySelectorAll('[data-archive]').forEach(b=>b.onclick=async()=>{if(!confirm('¿Archivar la novedad y cancelar los emails pendientes?'))return;b.disabled=true;try{await request('news-archive',{id:b.dataset.archive});await listNews();await loadNews(false);}catch(e){feedback(e.message);b.disabled=false;}});
    }
    try{await listNews();}catch(e){feedback(e.message);}
  }

  renderBar();enrichContactForms();syncHeader();
  async function restoreSession(){
    const hash=new URLSearchParams(location.hash.slice(1));const code=hash.get('co_login');const linked=hash.get('co_linked');
    const pending=hash.get('co_link_pending');
    if(pending){
      hash.delete('co_link_pending');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      sessionStorage.setItem('co_pending_link_v1',pending);
      await open('login');feedback('Ya tenés una cuenta con este email. Confirmá con Google o tu contraseña una sola vez; después podrás entrar directamente con Facebook.');return;
    }
    if(linked)sessionStorage.removeItem('co_pending_link_v1');
    if(linked){hash.delete('co_linked');}
    if(hash.get('co_logout')==='1'){
      hash.delete('co_logout');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      // La landing puede conservar otra sesión propia tras el traslado a Render.
      if(token){try{await request('logout',{});}catch(_){}}
      token='';account=null;rememberToken('');sessionStorage.removeItem('co_pending_link_v1');sessionStorage.removeItem('co_admin_token');localStorage.removeItem('co_admin_token');renderBar();return;
    }
    const oauthError=hash.get('co_oauth_error');
    if(oauthError){
      const reference=hash.get('co_oauth_ref')||'';hash.delete('co_oauth_ref');
      hash.delete('co_oauth_error');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      await open('login');
      const messages={cancelled:'Cancelaste el acceso. Podés volver a intentarlo.',email_required:'El proveedor no compartió tu email. Usá el registro con email.',existing_account:'Ese email ya tiene una cuenta. Confirmá con Google o tu contraseña para habilitar también el ingreso con Facebook.',account_inactive:'Tu cuenta no está activa. Contactá al administrador.',email_mismatch:'Elegí la cuenta del proveedor que tiene el mismo email que tu cuenta de la calculadora.',identity_in_use:'Ese acceso ya está vinculado a otra cuenta. No se realizó ningún cambio.',link_expired:'La confirmación venció. Iniciá nuevamente con Facebook.'};
      feedback((messages[oauthError]||'No se pudo completar el acceso. Intentá nuevamente.')+(reference?` Referencia: ${reference}`:''));
    }
    if(code){
      hash.delete('co_login');history.replaceState(null,'',location.pathname+location.search+(hash.toString()?'#'+hash.toString():''));
      try{const result=await request('handoff-redeem',{code});rememberToken(result.token);}
      catch(error){await open('login');feedback(error.message);return;}
    }
    if(!token)return;
    try{account=await fetchAccount(true);renderBar();if(!account.profile||linked)await open('profile');if(linked)feedback(`${linked==='facebook'?'Facebook':'Google'} vinculado. Ya podés ingresar con cualquiera de tus accesos vinculados.`);}
    catch(error){if(error.status===401||error.status===403){token='';rememberToken('');}renderBar();}
  }
  function startSocialLogin(button){
    if(!providersLoaded){providersPromise=null;providersFailed=false;button.disabled=true;loadProviders();return;}
    if(!socialProviders[button.dataset.social])return;
    const group=button.parentElement;group.querySelectorAll('[data-social]').forEach(b=>b.disabled=true);
    if(button.closest('.co-account-dialog'))feedback('Abriendo el acceso…');
    const url=new URL(`${apiOrigin}/api/oauth.php`);url.searchParams.set('action','start');url.searchParams.set('provider',button.dataset.social);url.searchParams.set('target',isCalculator?'calculator':'landing');
    const pending=sessionStorage.getItem('co_pending_link_v1');if(pending)url.searchParams.set('confirm',pending);location.assign(url.href);
  }
  function loadProviders(){
    if(providersPromise)return providersPromise;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    providersPromise=fetch(`${apiOrigin}/api/oauth.php?action=providers`,{signal:controller.signal}).then(r=>{if(!r.ok)throw new Error('Providers unavailable');return r.json();}).then(result=>{
      if(!result.ok||!result.providers)throw new Error('Providers unavailable');
      socialProviders=result.providers;providersLoaded=true;providersFailed=false;
      try{localStorage.setItem('co_providers_v1',JSON.stringify({providers:socialProviders,expires:Date.now()+600000}));}catch(_){}
      renderLinkButtons();document.querySelectorAll('[data-social]').forEach(b=>{const enabled=!!socialProviders[b.dataset.social];b.disabled=!enabled;b.innerHTML=socialButtonContent(b.dataset.social,b.dataset.socialMode||'login',enabled);b.onclick=()=>startSocialLogin(b);});
    }).catch(()=>{
      providersFailed=true;
      if(!providersLoaded)document.querySelectorAll('[data-social]').forEach(b=>{b.disabled=false;b.innerHTML=socialButtonContent(b.dataset.social,b.dataset.socialMode||'login',false);b.onclick=()=>startSocialLogin(b);});
    }).finally(()=>clearTimeout(timer));return providersPromise;
  }
  window.addEventListener('storage',event=>{
    if(event.key!==key)return;
    token=event.newValue||'';account=null;
    try{if(token)sessionStorage.setItem(key,token);else sessionStorage.removeItem(key);}catch(_){}
    renderBar();if(!token&&dialog.open)dialog.close();if(token)restoreSession();
  });
  loadProviders();
  restoreSession();
})();
