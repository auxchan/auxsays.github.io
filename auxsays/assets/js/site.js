const manifestPath = '/assets/data/article-manifest.json';
const configPath = '/assets/data/site-config.json';

document.addEventListener('DOMContentLoaded', async () => {
  setActiveNav();
  initReveal();
  initLottieIcons();
  const config = await getSiteConfig();
  applyGlobalConfig(config);
  if (document.body.dataset.page === 'home') applyHomeConfig(config);
  if (document.body.dataset.page === 'portfolio') applyAboutConfig(config);
  if (document.body.dataset.page === 'home') await renderHomeFeatured();
  if (document.body.dataset.page === 'articles') await initArticlesPage();
});

function setActiveNav() {
  const page = document.body.dataset.page;
  document.querySelectorAll('[data-nav]').forEach(link => {
    if (link.dataset.nav === page) link.classList.add('is-active');
  });
}

function initReveal() {
  const items = [...document.querySelectorAll('.reveal')];
  if (!items.length) return;
  const io = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('in');
        io.unobserve(entry.target);
      }
    }
  }, { threshold: .12 });
  items.forEach((el, i) => {
    el.style.transitionDelay = `${Math.min(i * 50, 220)}ms`;
    io.observe(el);
  });
}

function initLottieIcons() {
  const cards = document.querySelectorAll('.pillar-card[data-lottie]');
  cards.forEach(card => {
    const fallback = card.querySelector('.icon-fallback');
    const holder = card.querySelector('.lottie-icon');
    if (!fallback || !holder) return;
    fallback.innerHTML = getFallbackIcon(card.dataset.fallback || 'grid');
    if (!window.lottie) return;
    try {
      const animation = window.lottie.loadAnimation({container: holder,renderer: 'svg',loop: false,autoplay: false,path: card.dataset.lottie});
      animation.addEventListener('DOMLoaded', () => card.classList.add('lottie-loaded'));
      const play = () => animation.playSegments([0, 120], true);
      const reset = () => animation.goToAndStop(0, true);
      card.addEventListener('mouseenter', play);
      card.addEventListener('focusin', play);
      card.addEventListener('mouseleave', reset);
      card.addEventListener('focusout', reset);
    } catch {}
  });
}

function getFallbackIcon(type) {
  const map = {
    bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2 5 13h5l-1 9 8-11h-5l1-9Z"/></svg>',
    bars: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 19V10"/><path d="M12 19V5"/><path d="M19 19v-8"/></svg>',
    orbit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="2.2"/><path d="M5 12c0-4.1 3-7 7-7s7 2.9 7 7-3 7-7 7-7-2.9-7-7Z"/><path d="M8 8l8 8"/></svg>',
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="4" width="6" height="6" rx="1.2"/><rect x="14" y="4" width="6" height="6" rx="1.2"/><rect x="4" y="14" width="6" height="6" rx="1.2"/><rect x="14" y="14" width="6" height="6" rx="1.2"/></svg>'
  };
  return map[type] || map.grid;
}

async function getManifest() {
  const res = await fetch(`${manifestPath}?v=${Date.now()}`);
  if (!res.ok) return [];
  return await res.json();
}
async function getSiteConfig() {
  const res = await fetch(`${configPath}?v=${Date.now()}`);
  if (!res.ok) return null;
  return await res.json();
}
function applyGlobalConfig(config){
  if(!config) return;
  document.querySelectorAll('#brand-name').forEach(el=>el.textContent=config.brand?.name||'AUXSAYS');
  document.querySelectorAll('#brand-tagline').forEach(el=>el.textContent=config.brand?.tagline||'');
}
function applyHomeConfig(config){
  if(!config?.home) return;
  setText('home-kicker', config.home.kicker);
  setText('home-headline', config.home.headline);
  setText('home-lead', config.home.lead);
  setText('coverage-intro', config.home.coverage_intro);
  const briefRoot=document.getElementById('home-brief');
  if(briefRoot){
    briefRoot.innerHTML=(config.home.brief||[]).map(item=>`<section class="panel brief-row"><div class="eyebrow">${escapeHtml(item.eyebrow||'')}</div><h3>${escapeHtml(item.title||'')}</h3><p>${escapeHtml(item.body||'')}</p></section>`).join('');
  }
  const pillars=document.getElementById('home-pillars');
  if(pillars){
    pillars.innerHTML=(config.home.pillars||[]).map((item,i)=>`<article class="pillar-card reveal" data-lottie="${item.lottie||''}" data-fallback="${item.fallback||'grid'}"><div class="pillar-head"><div class="pillar-icon"><div class="icon-fallback"></div><div class="lottie-icon"></div></div><span class="pillar-number">${String(i+1).padStart(2,'0')}</span></div><div class="pillar-copy"><h3>${escapeHtml(item.title||'')}</h3><p class="pillar-teaser">${escapeHtml(item.teaser||'')}</p><div class="pillar-body"><p>${escapeHtml(item.detail||'')}</p><a class="text-link" href="${item.url||'/articles/'}">${escapeHtml(item.linkLabel||'Read more →')}</a></div></div></article>`).join('');
    initReveal();
    initLottieIcons();
  }
}
function applyAboutConfig(config){
  if(!config?.about) return;
  setText('about-eyebrow', config.about.eyebrow);
  setText('about-title', config.about.title);
  setText('about-intro1', config.about.intro1);
  setText('about-intro2', config.about.intro2);
  setText('about-primary-title', config.about.primaryTitle);
  setText('about-primary-body', config.about.primaryBody);
  setText('about-secondary-title', config.about.secondaryTitle);
  setText('about-secondary-body', config.about.secondaryBody);
  setText('about-thesis', config.about.thesis);
  setText('about-interests', config.about.interests);
  const img=document.getElementById('about-portrait'); if(img && config.about.portrait) img.src=config.about.portrait;
  const tools=document.getElementById('about-tools'); if(tools) tools.innerHTML=(config.about.tools||[]).map(t=>`<li>${escapeHtml(t)}</li>`).join('');
}
function setText(id, value){ const el=document.getElementById(id); if(el && typeof value==='string') el.textContent=value; }

async function renderHomeFeatured() {
  const root = document.getElementById('home-featured-articles');
  if (!root) return;
  const items = await getManifest();
  const featured = items.filter(i => i.featured).slice(0, 3);
  root.innerHTML = featured.map(cardHtml).join('');
}

async function initArticlesPage() {
  const items = await getManifest();
  const searchInput = document.getElementById('search-input');
  const categorySelect = document.getElementById('category-select');
  const sortSelect = document.getElementById('sort-select');
  const tagRoot = document.getElementById('tag-filters');
  const grid = document.getElementById('articles-grid');
  const count = document.getElementById('articles-count');
  const reset = document.getElementById('reset-filters');
  let activeTag = '';
  [...new Set(items.map(x => x.category).filter(Boolean))].sort().forEach(category => {
    const option = document.createElement('option'); option.value = category; option.textContent = category; categorySelect.appendChild(option);
  });
  const tags = [...new Set(items.flatMap(x => x.tags || []))].sort();
  tagRoot.innerHTML = tags.map(tag => `<button class="filter-link" type="button" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`).join('');
  tagRoot.addEventListener('click', e => {
    const chip = e.target.closest('[data-tag]'); if (!chip) return;
    const value = chip.dataset.tag; activeTag = activeTag === value ? '' : value;
    tagRoot.querySelectorAll('.filter-link').forEach(c => c.classList.toggle('active', c.dataset.tag === activeTag)); render();
  });
  [searchInput, categorySelect, sortSelect].forEach(el => el.addEventListener('input', render));
  reset.addEventListener('click', () => {
    searchInput.value=''; categorySelect.value=''; sortSelect.value='newest'; activeTag=''; tagRoot.querySelectorAll('.filter-link').forEach(c => c.classList.remove('active')); render();
  });
  function render(){
    let filtered=[...items]; const q=searchInput.value.toLowerCase().trim(); const category=categorySelect.value; const sort=sortSelect.value;
    if(q) filtered=filtered.filter(item => [item.title,item.excerpt,item.category,item.app,...(item.tags||[])].join(' ').toLowerCase().includes(q));
    if(category) filtered=filtered.filter(item => item.category===category);
    if(activeTag) filtered=filtered.filter(item => (item.tags||[]).includes(activeTag));
    if(sort==='newest') filtered.sort((a,b)=> new Date(b.date||0)-new Date(a.date||0));
    if(sort==='oldest') filtered.sort((a,b)=> new Date(a.date||0)-new Date(b.date||0));
    if(sort==='title') filtered.sort((a,b)=> a.title.localeCompare(b.title));
    count.textContent=`${filtered.length} article${filtered.length===1?'':'s'} loaded`;
    grid.innerHTML=filtered.map(cardHtml).join('') || '<div class="panel search-panel"><h3>No matches</h3><p>Try a broader search or reset filters.</p></div>';
  }
  render();
}

function cardHtml(item) {
  const tags = (item.tags || []).slice(0, 3).join(' • ');
  return `<article class="article-card reveal"><a class="article-cover" href="${item.path}"><img src="${item.cover}" alt="${escapeHtml(item.title)}"></a><div class="article-body"><div class="meta-row"><span>${escapeHtml(item.category || 'Article')}</span><span>${escapeHtml(item.app || '')}</span><span>${escapeHtml(item.date || '')}</span></div><h3><a href="${item.path}">${escapeHtml(item.title)}</a></h3><p>${escapeHtml(item.excerpt || '')}</p>${tags ? `<div class="tags-line">${escapeHtml(tags)}</div>` : ''}<div class="article-footer"><span class="muted">Open article</span><a class="text-link" href="${item.path}">Read →</a></div></div></article>`;
}
function escapeHtml(value = '') {return String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');}
