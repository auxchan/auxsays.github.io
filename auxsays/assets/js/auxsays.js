document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Systems lottie
  if (window.lottie) {
    const lottieNode = document.getElementById('systems-lottie');
    if (lottieNode && !lottieNode.dataset.loaded) {
      const path = `${window.location.origin}/assets/lottie/systems-pulse.json`;
      try {
        window.lottie.loadAnimation({
          container: lottieNode,
          renderer: 'svg',
          loop: true,
          autoplay: true,
          path,
        });
        lottieNode.dataset.loaded = 'true';
      } catch (e) {}
    }
  }

  // particles
  function buildParticles(targetId, count, fg = false) {
    const host = document.getElementById(targetId);
    if (!host || host.dataset.loaded) return;
    host.dataset.loaded = 'true';
    for (let i = 0; i < count; i += 1) {
      const particle = document.createElement('span');
      particle.className = `systems-particle ${fg ? 'systems-particle--fg' : 'systems-particle--bg'}`;
      const size = fg ? 2 + Math.random() * 5 : 1 + Math.random() * 4;
      particle.style.setProperty('--size', `${size}px`);
      particle.style.setProperty('--x', `${Math.random() * 100}%`);
      particle.style.setProperty('--y', `${Math.random() * 100}%`);
      particle.style.setProperty('--drift-x', `${(Math.random() - 0.5) * 50}px`);
      particle.style.setProperty('--drift-y', `${40 + Math.random() * 70}px`);
      particle.style.setProperty('--duration', `${7 + Math.random() * 8}s`);
      particle.style.setProperty('--delay', `${Math.random() * 6}s`);
      host.appendChild(particle);
    }
  }
  if (!prefersReducedMotion) {
    buildParticles('systems-particles-bg', 28, false);
    buildParticles('systems-particles-fg', 12, true);
  }

  // reveals
  const reveals = document.querySelectorAll('.reveal-up');
  if (!prefersReducedMotion && reveals.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -6% 0px' });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('is-visible'));
  }

  // homepage coverage cards
  const coverageCards = Array.from(document.querySelectorAll('[data-card]'));
  const prefersTouch = window.matchMedia('(hover: none)').matches || window.innerWidth < 900;
  function setCardState(card, open) {
    if (!card) return;
    card.classList.toggle('is-open', open);
    const hit = card.querySelector('.coverage-hit');
    if (hit) hit.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function closeOthers(activeCard) {
    coverageCards.forEach((card) => { if (card !== activeCard) setCardState(card, false); });
  }
  coverageCards.forEach((card) => {
    const hit = card.querySelector('.coverage-hit');
    if (!hit) return;
    if (!prefersTouch) {
      card.addEventListener('mouseenter', () => { closeOthers(card); setCardState(card, true); });
      card.addEventListener('mouseleave', () => { setCardState(card, false); card.style.removeProperty('--tilt-x'); card.style.removeProperty('--tilt-y'); });
      card.addEventListener('mousemove', (event) => {
        const rect = card.getBoundingClientRect();
        const px = (event.clientX - rect.left) / rect.width;
        const py = (event.clientY - rect.top) / rect.height;
        const tiltX = (0.5 - py) * 2.5;
        const tiltY = (px - 0.5) * 2.5;
        card.style.setProperty('--tilt-x', `${tiltX}deg`);
        card.style.setProperty('--tilt-y', `${tiltY}deg`);
      });
    }
    hit.addEventListener('click', () => {
      const willOpen = !card.classList.contains('is-open');
      closeOthers(card);
      setCardState(card, willOpen);
    });
  });
  if (prefersTouch && coverageCards.length) setCardState(coverageCards[0], true);

  // article search filter
  const search = document.getElementById('article-search');
  const chips = document.querySelectorAll('.chip');
  const articleCards = document.querySelectorAll('.article-card');
  let activeFilter = 'all';
  function applyArticleFilters() {
    const query = (search?.value || '').toLowerCase().trim();
    articleCards.forEach((card) => {
      const haystack = [card.dataset.title || '', card.dataset.description || '', card.dataset.tags || ''].join(' ').toLowerCase();
      const categories = (card.dataset.categories || '').toLowerCase();
      const categoryMatch = activeFilter === 'all' || categories.includes(activeFilter);
      const queryMatch = !query || haystack.includes(query);
      card.style.display = categoryMatch && queryMatch ? '' : 'none';
    });
  }
  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      chips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      activeFilter = chip.dataset.filter;
      applyArticleFilters();
    });
  });
  search?.addEventListener('input', applyArticleFilters);

  // patch feed controls
  const patchFeed = document.getElementById('patch-feed');
  const patchArchiveFeed = document.getElementById('patch-archive-feed');
  const patchSearch = document.getElementById('patch-search');
  const filterChips = Array.from(document.querySelectorAll('#patch-filter-chips [data-filter]'));
  const statusChips = Array.from(document.querySelectorAll('#patch-status-chips [data-status]'));
  const sortChips = Array.from(document.querySelectorAll('#patch-sort-chips [data-sort]'));

  if (patchFeed && (filterChips.length || sortChips.length || statusChips.length || patchSearch)) {
    const allCards = Array.from(document.querySelectorAll('.patch-card'));
    let currentFilter = 'all';
    let currentStatus = 'all';
    let currentSort = 'latest';
    const riskRank = { negative: 3, moderate: 2, positive: 1, insufficient: 0, 'insufficient-data': 0 };

    const applyPatchFeed = () => {
      const query = (patchSearch?.value || '').toLowerCase().trim();
      const visible = allCards.filter((card) => {
        const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.summary].join(' ').toLowerCase();
        const type = (card.dataset.type || '').toLowerCase();
        const category = (card.dataset.category || '').toLowerCase();
        const status = (card.dataset.status || '').toLowerCase();
        const filterPass = currentFilter === 'all' || type.includes(currentFilter) || category.includes(currentFilter);
        const statusPass = currentStatus === 'all' || status.includes(currentStatus);
        const queryPass = !query || haystack.includes(query);
        return filterPass && statusPass && queryPass;
      });

      visible.sort((a, b) => {
        if (currentSort === 'product') return (a.dataset.product || '').localeCompare(b.dataset.product || '');
        if (currentSort === 'risk') {
          const delta = (riskRank[b.dataset.status] || 0) - (riskRank[a.dataset.status] || 0);
          if (delta !== 0) return delta;
        }
        return Number(b.dataset.date || 0) - Number(a.dataset.date || 0);
      });

      allCards.forEach((card) => card.classList.add('is-hidden'));
      visible.forEach((card) => {
        card.classList.remove('is-hidden');
        const target = card.dataset.kind === 'archived' ? patchArchiveFeed : patchFeed;
        target.appendChild(card);
      });
    };

    patchSearch?.addEventListener('input', applyPatchFeed);
    filterChips.forEach((chip) => chip.addEventListener('click', () => {
      filterChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentFilter = chip.dataset.filter;
      applyPatchFeed();
    }));
    statusChips.forEach((chip) => chip.addEventListener('click', () => {
      statusChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentStatus = chip.dataset.status;
      applyPatchFeed();
    }));
    sortChips.forEach((chip) => chip.addEventListener('click', () => {
      sortChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentSort = chip.dataset.sort;
      applyPatchFeed();
    }));
    applyPatchFeed();
  }
});
