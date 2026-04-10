document.addEventListener('DOMContentLoaded', () => {
  const coverageCards = Array.from(document.querySelectorAll('[data-card]'));
  const isTouch = window.matchMedia('(hover: none)').matches;

  function closeOthers(activeCard) {
    coverageCards.forEach((card) => {
      if (card !== activeCard) {
        card.classList.remove('is-open');
        const hit = card.querySelector('.coverage-hit');
        if (hit) hit.setAttribute('aria-expanded', 'false');
      }
    });
  }

  coverageCards.forEach((card) => {
    const hit = card.querySelector('.coverage-hit');
    if (!hit) return;

    if (!isTouch) {
      card.addEventListener('mouseenter', () => {
        closeOthers(card);
        card.classList.add('is-open');
        hit.setAttribute('aria-expanded', 'true');
      });

      card.addEventListener('mouseleave', () => {
        card.classList.remove('is-open');
        hit.setAttribute('aria-expanded', 'false');
      });
    }

    hit.addEventListener('click', () => {
      const willOpen = !card.classList.contains('is-open');
      closeOthers(card);
      card.classList.toggle('is-open', willOpen);
      hit.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
    });
  });

  const reveals = document.querySelectorAll('.reveal-up');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.14 });

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
    if (!ticking) {
      window.requestAnimationFrame(updateParallax);
      ticking = true;
    }
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
      const haystack = [card.dataset.title, card.dataset.description, card.dataset.tags].join(' ');
      const categoryMatch = activeFilter === 'all' || (card.dataset.categories || '').includes(activeFilter);
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
