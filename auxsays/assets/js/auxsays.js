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
        rendererSettings: {
          preserveAspectRatio: 'xMidYMid slice'
        }
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

    const bgCount = window.innerWidth < 860 ? 10 : 14;
    const fgCount = window.innerWidth < 860 ? 3 : 5;

    for (let i = 0; i < bgCount; i += 1) {
      const p = document.createElement('span');
      const size = (Math.random() * 10) + 4;
      p.className = 'systems-particle systems-particle--bg';
      p.style.setProperty('--x', `${Math.random() * 100}%`);
      p.style.setProperty('--y', `${Math.random() * 100}%`);
      p.style.setProperty('--size', `${size}px`);
      p.style.setProperty('--drift-x', `${(Math.random() * 28 - 14).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-18 - Math.random() * 28).toFixed(1)}px`);
      p.style.setProperty('--duration', `${16 + Math.random() * 18}s`);
      p.style.setProperty('--delay', `${-Math.random() * 18}s`);
      bgRoot.appendChild(p);
    }

    for (let i = 0; i < fgCount; i += 1) {
      const p = document.createElement('span');
      const size = (Math.random() * 16) + 14;
      p.className = 'systems-particle systems-particle--fg';
      p.style.setProperty('--x', `${6 + Math.random() * 88}%`);
      p.style.setProperty('--y', `${12 + Math.random() * 78}%`);
      p.style.setProperty('--size', `${size}px`);
      p.style.setProperty('--drift-x', `${(Math.random() * 38 - 19).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-34 - Math.random() * 40).toFixed(1)}px`);
      p.style.setProperty('--duration', `${12 + Math.random() * 10}s`);
      p.style.setProperty('--delay', `${-Math.random() * 10}s`);
      fgRoot.appendChild(p);
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


(function () {
  const iconRoots = document.querySelectorAll('.coverage-icon-lottie[data-lottie-path]');
  if (!window.lottie || !iconRoots.length) return;

  iconRoots.forEach((root) => {
    try {
      const anim = window.lottie.loadAnimation({
        container: root,
        renderer: 'svg',
        loop: true,
        autoplay: true,
        path: root.dataset.lottiePath,
        rendererSettings: { preserveAspectRatio: 'xMidYMid meet' }
      });
      if (anim && anim.setSpeed) anim.setSpeed(0.78);
      const card = root.closest('.coverage-card');
      if (card && anim && anim.setDirection) {
        card.addEventListener('mouseenter', () => anim.setDirection(1));
        card.addEventListener('mouseleave', () => anim.setDirection(1));
      }
    } catch (err) {
      console.warn('Coverage icon animation failed to load.', err);
    }
  });
})();
