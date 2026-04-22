document.addEventListener('DOMContentLoaded', () => {
  const lottieRoot = document.getElementById('systems-lottie');
  if (window.lottie && lottieRoot) {
    try {
      window.lottie.loadAnimation({
        container: lottieRoot,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: '/assets/lottie/systems-pulse.json',
        rendererSettings: { preserveAspectRatio: 'xMidYMid slice' }
      });
    } catch (err) {
      console.warn('Systems pulse animation failed to load.', err);
    }
  }

  function buildParticles() {
    const bgRoot = document.getElementById('systems-particles-bg');
    const fgRoot = document.getElementById('systems-particles-fg');
    if (!bgRoot || !fgRoot) return;
    bgRoot.innerHTML = '';
    fgRoot.innerHTML = '';
    const bgCount = window.innerWidth < 860 ? 8 : 12;
    const fgCount = window.innerWidth < 860 ? 2 : 4;
    for (let i = 0; i < bgCount; i += 1) {
      const p = document.createElement('span');
      const size = (Math.random() * 8) + 4;
      p.className = 'systems-particle systems-particle--bg';
      p.style.setProperty('--x', `${Math.random() * 100}%`);
      p.style.setProperty('--y', `${Math.random() * 100}%`);
      p.style.setProperty('--size', `${size}px`);
      p.style.setProperty('--drift-x', `${(Math.random() * 24 - 12).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-16 - Math.random() * 22).toFixed(1)}px`);
      p.style.setProperty('--duration', `${18 + Math.random() * 18}s`);
      p.style.setProperty('--delay', `${-Math.random() * 18}s`);
      bgRoot.appendChild(p);
    }
    for (let i = 0; i < fgCount; i += 1) {
      const p = document.createElement('span');
      const size = (Math.random() * 12) + 10;
      p.className = 'systems-particle systems-particle--fg';
      p.style.setProperty('--x', `${8 + Math.random() * 84}%`);
      p.style.setProperty('--y', `${14 + Math.random() * 72}%`);
      p.style.setProperty('--size', `${size}px`);
      p.style.setProperty('--drift-x', `${(Math.random() * 24 - 12).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-24 - Math.random() * 24).toFixed(1)}px`);
      p.style.setProperty('--duration', `${14 + Math.random() * 10}s`);
      p.style.setProperty('--delay', `${-Math.random() * 10}s`);
      fgRoot.appendChild(p);
    }
  }
  buildParticles();
  window.addEventListener('resize', buildParticles);

  // coverage cards
  const coverageCards = Array.from(document.querySelectorAll('[data-card]'));
  const prefersTouch = window.matchMedia('(hover: none)').matches || window.innerWidth < 900;
  function setCardState(card, open) {
    if (!card) return;
    card.classList.toggle('is-open', open);
    const hit = card.querySelector('.coverage-hit');
    if (hit) hit.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function closeOthers(activeCard) {
    coverageCards.forEach((card) => {
      if (card !== activeCard) setCardState(card, false);
    });
  }
  coverageCards.forEach((card) => {
    const hit = card.querySelector('.coverage-hit');
    if (!hit) return;
    if (!prefersTouch) {
      card.addEventListener('mouseenter', () => { closeOthers(card); setCardState(card, true); });
      card.addEventListener('mouseleave', () => { setCardState(card, false); });
    }
    hit.addEventListener('click', () => {
      const willOpen = !card.classList.contains('is-open');
      closeOthers(card);
      setCardState(card, willOpen);
    });
  });
  if (prefersTouch && coverageCards.length) setCardState(coverageCards[0], true);

  // coverage lottie icons
  if (window.lottie) {
    document.querySelectorAll('.coverage-lottie[data-lottie]').forEach((node) => {
      const name = node.dataset.lottie;
      try {
        window.lottie.loadAnimation({
          container: node,
          renderer: 'svg',
          loop: true,
          autoplay: true,
          path: `/assets/lottie/${name}.json`
        });
      } catch (err) {
        console.warn('Coverage icon failed to load', name, err);
      }
    });
  }

  // reveal
  const reveals = document.querySelectorAll('.reveal-up');
  if (reveals.length) {
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -5% 0px' });
    reveals.forEach((el) => revealObserver.observe(el));
  }

  // parallax
  const parallaxNodes = document.querySelectorAll('[data-parallax]');
  let ticking = false;
  function updateParallax() {
    const vh = window.innerHeight;
    parallaxNodes.forEach((node) => {
      const speed = parseFloat(node.dataset.parallax || '0');
      const rect = node.getBoundingClientRect();
      const delta = (rect.top + rect.height / 2 - vh / 2) * speed;
      node.style.transform = `translate3d(0, ${delta}px, 0)`;
    });
    ticking = false;
  }
  function requestParallax() {
    if (ticking) return;
    window.requestAnimationFrame(updateParallax);
    ticking = true;
  }
  if (parallaxNodes.length) {
    requestParallax();
    window.addEventListener('scroll', requestParallax, { passive: true });
    window.addEventListener('resize', requestParallax);
  }

  // article filters
  const articleSearch = document.getElementById('article-search');
  const articleChips = document.querySelectorAll('.chip');
  const articleCards = document.querySelectorAll('.article-card');
  let activeFilter = 'all';
  function applyArticleFilters() {
    const query = (articleSearch?.value || '').toLowerCase().trim();
    articleCards.forEach((card) => {
      const haystack = [card.dataset.title || '', card.dataset.description || '', card.dataset.tags || ''].join(' ').toLowerCase();
      const categories = (card.dataset.categories || '').toLowerCase();
      const categoryMatch = activeFilter === 'all' || categories.includes(activeFilter);
      const queryMatch = !query || haystack.includes(query);
      card.style.display = categoryMatch && queryMatch ? '' : 'none';
    });
  }
  articleChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      articleChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      activeFilter = chip.dataset.filter;
      applyArticleFilters();
    });
  });
  articleSearch?.addEventListener('input', applyArticleFilters);

  // patch feed filters
  const pfGrid = document.getElementById('patchfeed-grid');
  const pfSearch = document.getElementById('patchfeed-search');
  const pfCards = pfGrid ? Array.from(pfGrid.querySelectorAll('.pf-card')) : [];
  const pfFilterButtons = Array.from(document.querySelectorAll('[data-filter]'));
  const pfSortButtons = Array.from(document.querySelectorAll('[data-sort]'));
  let patchFilter = 'all';
  let patchSort = 'latest';

  function sortPatchCards(cards) {
    const sorted = [...cards];
    if (patchSort === 'alpha') sorted.sort((a,b) => (a.dataset.product || '').localeCompare(b.dataset.product || ''));
    else if (patchSort === 'risk') sorted.sort((a,b) => Number(b.dataset.risk || 0) - Number(a.dataset.risk || 0) || Number(b.dataset.date||0)-Number(a.dataset.date||0));
    else sorted.sort((a,b) => Number(b.dataset.date || 0) - Number(a.dataset.date || 0));
    return sorted;
  }

  function applyPatchFeed() {
    if (!pfGrid) return;
    const query = (pfSearch?.value || '').toLowerCase().trim();
    const filtered = pfCards.filter((card) => {
      const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.version].join(' ').toLowerCase();
      const filterSpace = (card.dataset.filter || '').toLowerCase();
      const matchSearch = !query || haystack.includes(query);
      const matchFilter = patchFilter === 'all' || filterSpace.includes(patchFilter);
      return matchSearch && matchFilter;
    });
    pfGrid.innerHTML = '';
    sortPatchCards(filtered).forEach((card) => pfGrid.appendChild(card));
  }

  pfSearch?.addEventListener('input', applyPatchFeed);
  pfFilterButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      pfFilterButtons.forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      patchFilter = btn.dataset.filter;
      applyPatchFeed();
    });
  });
  pfSortButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      pfSortButtons.forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      patchSort = btn.dataset.sort;
      applyPatchFeed();
    });
  });
});
