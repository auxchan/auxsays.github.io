document.addEventListener('DOMContentLoaded', () => {
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
      card.addEventListener('mouseenter', () => {
        closeOthers(card);
        setCardState(card, true);
      });

      card.addEventListener('mouseleave', () => {
        setCardState(card, false);
      });
    }

    hit.addEventListener('click', () => {
      const willOpen = !card.classList.contains('is-open');
      closeOthers(card);
      setCardState(card, willOpen);
    });
  });

  if (prefersTouch && coverageCards.length) {
    setCardState(coverageCards[0], true);
  }

  const reveals = document.querySelectorAll('.reveal-up');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);
    });
  }, {
    threshold: 0.14,
    rootMargin: '0px 0px -5% 0px'
  });

  reveals.forEach((el) => revealObserver.observe(el));

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

  const search = document.getElementById('article-search');
  const chips = document.querySelectorAll('.chip');
  const articleCards = document.querySelectorAll('.article-card');
  let activeFilter = 'all';

  function applyFilters() {
    const query = (search?.value || '').toLowerCase().trim();

    articleCards.forEach((card) => {
      const haystack = [
        card.dataset.title || '',
        card.dataset.description || '',
        card.dataset.tags || ''
      ].join(' ').toLowerCase();

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
      applyFilters();
    });
  });

  search?.addEventListener('input', applyFilters);
});
