document.addEventListener('DOMContentLoaded', () => {
  const particlesRoot = document.getElementById('systems-particles');

  const lottieRoot = document.getElementById('systems-lottie');
  if (window.lottie && lottieRoot) {
    try {
      window.lottie.loadAnimation({
        container: lottieRoot,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: '/assets/lottie/systems-pulse.json',
        rendererSettings: {
          preserveAspectRatio: 'xMidYMid slice'
        }
      });
    } catch (err) {
      console.warn('Systems pulse animation failed to load.', err);
    }
  }


  function buildParticles() {
    if (!particlesRoot) return;
    particlesRoot.innerHTML = '';
    const count = window.innerWidth < 860 ? 12 : 22;

    for (let i = 0; i < count; i += 1) {
      const particle = document.createElement('span');
      const size = (Math.random() * 18) + 4;
      const x = Math.random() * 100;
      const y = Math.random() * 100;
      const depth = (Math.random() * 0.22) - 0.11;
      const duration = (Math.random() * 18) + 18;
      const delay = Math.random() * -duration;

      particle.className = 'systems-particle';
      particle.style.setProperty('--x', `${x}%`);
      particle.style.setProperty('--y', `${y}%`);
      particle.style.setProperty('--size', `${size}px`);
      particle.style.setProperty('--depth', depth.toFixed(3));
      particle.style.setProperty('--duration', `${duration}s`);
      particle.style.setProperty('--delay', `${delay}s`);
      particlesRoot.appendChild(particle);
    }
  }

  buildParticles();
  window.addEventListener('resize', buildParticles);

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

    document.querySelectorAll('.systems-particle').forEach((node) => {
      const depth = parseFloat(node.style.getPropertyValue('--depth') || '0');
      const drift = window.scrollY * depth;
      node.style.setProperty('--scroll', `${drift}px`);
    });

    ticking = false;
  }

  function requestParallax() {
    if (ticking) return;
    window.requestAnimationFrame(updateParallax);
    ticking = true;
  }

  requestParallax();
  window.addEventListener('scroll', requestParallax, { passive: true });
  window.addEventListener('resize', requestParallax);

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
