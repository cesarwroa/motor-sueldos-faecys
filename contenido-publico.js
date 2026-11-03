(() => {
  'use strict';
  const links = [['/guia-calculadora.html','Guía de uso'],['/acuerdos-escalas.html','Acuerdos y escalas'],['/novedades.php','Novedades'],['/quienes-somos.html','Quiénes somos'],['/contacto.html','Contacto']];
  let frame = null, pendingNews = null, newsState = null, measuredHeader = null;
  const anchor = (href, label) => { const a = document.createElement('a'); a.href = href; a.textContent = label; if(href==='/novedades.php')a.hidden=!(newsState?.items?.length); return a; };
  function secondaryNav() {
    const nav = document.createElement('nav'); nav.className = 'co-secondary-nav'; nav.setAttribute('aria-label','Guías e información');
    const inner = document.createElement('div'); inner.className = 'co-secondary-inner';
    links.forEach(([url,label]) => inner.append(anchor(url,label))); nav.append(inner); return nav;
  }
  function dateLabel(raw) {
    const value = String(raw || ''); const date = new Date(value.includes('T') ? value : value.replace(' ','T') + 'Z');
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('es-AR',{day:'numeric',month:'long',year:'numeric',timeZone:'America/Argentina/Buenos_Aires'});
  }
  function imageURL(raw) {
    try {
      const url = new URL(String(raw || ''), location.origin);
      if (!['https:','http:'].includes(url.protocol) || ![location.origin,'https://calculadoradecomercio.com.ar'].includes(url.origin)) return null;
      if (!/^\/uploads\/novedades\/[a-f0-9]{32}\.(?:jpg|png|gif|webp)$/.test(url.pathname)) return null;
      return url.href;
    } catch { return null; }
  }
  function paintNews() {
    const aside = document.querySelector('.co-home-news'); if (!aside || !newsState) return;
    const visible = !newsState.error && newsState.items.length > 0;
    aside.hidden = !visible;
    document.querySelector('.co-company-hero-host')?.classList.toggle('co-has-public-news', visible);
    document.querySelectorAll('nav a[href="/novedades.php"],.co-news-all').forEach(a => { a.hidden = !visible; });
    const target = aside.querySelector('[data-public-news]'); target.replaceChildren();
    if (!visible) return;
    if (newsState.error) {
      const p = document.createElement('p'); p.textContent = 'No se pudo cargar la última publicación.';
      const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'co-news-retry'; retry.textContent = 'Reintentar';
      retry.addEventListener('click', () => { newsState = null; loadNews(); }); target.append(p,retry); return;
    }
    const n = newsState.items[0];
    if (!n) { const p = document.createElement('p'); p.textContent = 'Todavía no hay novedades públicas publicadas.'; target.append(p); return; }
    const article = document.createElement('article'), h = document.createElement('h3'), time = document.createElement('time');
    const detail = '/novedades.php?id=' + encodeURIComponent(n.id);
    h.append(anchor(detail,n.title)); time.textContent = dateLabel(n.published_at);
    if (n.published_at) time.dateTime = String(n.published_at).replace(' ','T') + (String(n.published_at).includes('T') ? '' : 'Z');
    article.append(h,time);
    const url = imageURL(n.image_url);
    if (url) {
      const link = anchor(detail,''); link.className = 'co-news-image-link'; link.setAttribute('aria-label','Leer '+n.title);
      const img = document.createElement('img'); img.src = url; img.alt = String(n.title); img.decoding = 'async';
      img.addEventListener('error',() => link.remove(),{once:true}); link.append(img); article.append(link);
    }
    const p = document.createElement('p'), body = String(n.body || '');
    p.className = 'co-news-excerpt'; p.textContent = body.slice(0,170) + (body.length > 170 ? '…' : '');
    const more = anchor(detail,'Leer publicación completa'); more.className = 'co-news-read'; article.append(p,more); target.append(article);
  }
  function loadNews() {
    if (pendingNews) return;
    const target = document.querySelector('.co-home-news [data-public-news]'); if (!target) return;
    target.textContent = 'Cargando publicación…';
    pendingNews = fetch('/api/public-accounts.php?action=news-public',{signal:AbortSignal.timeout(15000),cache:'no-store'})
      .then(async r => { if (!r.ok) throw Error(); const data = await r.json(); if (!data.ok || !Array.isArray(data.news)) throw Error(); newsState = {items:data.news}; })
      .catch(() => { newsState = {error:true}; })
      .finally(() => { pendingNews = null; paintNews(); });
  }
  function enhance() {
    const header = document.querySelector('#root header');
    if (header) {
      if (!header.classList.contains('co-main-header')) header.classList.add('co-main-header');
      header.querySelectorAll('.co-editorial-menu').forEach(e => e.remove());
      if (!header.querySelector('.co-secondary-nav')) header.append(secondaryNav());
      const stamp = document.getElementById('coUpdateStamp');
      if (stamp && stamp.parentElement !== header) header.append(stamp);
      const nav = header.querySelector('.container > nav'); if (nav) nav.setAttribute('aria-label','Principal');
      if (measuredHeader !== header) {
        measuredHeader = header;
        new ResizeObserver(entries => document.documentElement.style.setProperty('--co-header-height',entries[0].target.offsetHeight+'px')).observe(header);
      }
    }
    const hero = document.querySelector('.co-company-hero-host'), showcase = document.querySelector('.co-hero-showcase');
    if (hero?.querySelector('.co-home-news') && !hero.classList.contains('co-home-news-layout')) hero.classList.add('co-home-news-layout');
    if (hero && showcase && !hero.querySelector('.co-home-news')) {
      const layout = hero.querySelector(':scope > .container');
      if (layout) {
        const aside = document.createElement('aside'); aside.className = 'co-home-news'; aside.hidden = true; aside.setAttribute('aria-labelledby','homeNewsTitle');
        const heading = document.createElement('h2'); heading.id = 'homeNewsTitle'; heading.textContent = 'Novedades';
        const target = document.createElement('div'); target.dataset.publicNews = ''; target.setAttribute('aria-live','polite'); target.textContent = 'Cargando publicación…';
        const all = anchor('/novedades.php','Ver todas las novedades'); all.className = 'co-news-all';
        aside.append(heading,target,all); layout.append(showcase,aside); hero.classList.add('co-home-news-layout');
        if (newsState) paintNews(); else loadNews();
      }
    }
    document.querySelectorAll('.co-editorial-news').forEach(e => e.remove());
    const footer = document.querySelector('#root footer');
    if (footer && !footer.querySelector('.co-editorial-footer')) {
      const nav = document.createElement('nav'); nav.className = 'co-editorial-footer'; nav.setAttribute('aria-label','Contenido e información institucional');
      [...links,['/privacidad.html','Privacidad'],['/condiciones.html','Condiciones de uso']].forEach(([url,label]) => nav.append(anchor(url,label))); footer.append(nav);
    }
  }
  document.addEventListener('click', e => {
    const t = e.target.closest('footer button,footer a'); if (!t || t.closest('.co-editorial-footer')) return;
    const label = t.textContent.normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
    const url = /privacidad/.test(label) ? '/privacidad.html' : /terminos|condiciones de uso/.test(label) ? '/condiciones.html' : /sobre nosotros|quienes somos/.test(label) ? '/quienes-somos.html' : null;
    if (url) { e.preventDefault(); e.stopPropagation(); location.assign(url); }
  },true);
  function schedule() { if (frame !== null) return; frame = requestAnimationFrame(() => { frame = null; enhance(); }); }
  new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']}); enhance();
  window.addEventListener('co-news-changed',loadNews);
  window.addEventListener('focus',loadNews);
  setInterval(loadNews,60000);

})();
