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
      p.style.setProperty('--drift-x', `${(Math.random() * 18 - 9).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-12 - Math.random() * 18).toFixed(1)}px`);
      p.style.setProperty('--duration', `${18 + Math.random() * 16}s`);
      p.style.setProperty('--delay', `${-Math.random() * 18}s`);
      bgRoot.appendChild(p);
    }

    for (let i = 0; i < fgCount; i += 1) {
      const p = document.createElement('span');
      const size = (Math.random() * 12) + 10;
      p.className = 'systems-particle systems-particle--fg';
      p.style.setProperty('--x', `${8 + Math.random() * 84}%`);
      p.style.setProperty('--y', `${10 + Math.random() * 76}%`);
      p.style.setProperty('--size', `${size}px`);
      p.style.setProperty('--drift-x', `${(Math.random() * 24 - 12).toFixed(1)}px`);
      p.style.setProperty('--drift-y', `${(-20 - Math.random() * 18).toFixed(1)}px`);
      p.style.setProperty('--duration', `${14 + Math.random() * 10}s`);
      p.style.setProperty('--delay', `${-Math.random() * 10}s`);
      fgRoot.appendChild(p);
    }
  }

  buildParticles();
  window.addEventListener('resize', buildParticles);

  const iconMap = {
    'free-ai': '/assets/lottie/free-ai.json',
    'content-workflows': '/assets/lottie/content-workflows.json',
    'automation': '/assets/lottie/automation.json',
    'patch-feed': '/assets/lottie/lms-systems.json'
  };

  if (window.lottie) {
    document.querySelectorAll('[data-lottie-icon]').forEach((node) => {
      const key = node.dataset.lottieIcon;
      const path = iconMap[key];
      if (!path) return;
      const holder = document.createElement('span');
      holder.className = 'lottie-icon';
      node.appendChild(holder);
      try {
        const anim = window.lottie.loadAnimation({
          container: holder,
          renderer: 'svg',
          loop: true,
          autoplay: true,
          path
        });
        const card = node.closest('.coverage-card');
        if (card) {
          card.addEventListener('mouseenter', () => anim.setSpeed(1));
          card.addEventListener('mouseleave', () => anim.setSpeed(0.8));
        }
      } catch (err) {
        console.warn('Coverage icon animation failed.', key, err);
      }
    });
  }

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
      card.addEventListener('mouseleave', () => setCardState(card, false));
    }

    hit.addEventListener('click', () => {
      const willOpen = !card.classList.contains('is-open');
      closeOthers(card);
      setCardState(card, willOpen);
    });
  });

  if (prefersTouch && coverageCards.length) setCardState(coverageCards[0], true);

  const reveals = document.querySelectorAll('.reveal-up');
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);
    });
  }, { threshold: 0.14, rootMargin: '0px 0px -5% 0px' });
  reveals.forEach((el) => revealObserver.observe(el));

  const search = document.getElementById('article-search');
  const chips = document.querySelectorAll('.chip');
  const articleCards = document.querySelectorAll('.article-card');
  let activeFilter = 'all';

  function applyFilters() {
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
      applyFilters();
    });
  });

  search?.addEventListener('input', applyFilters);
});
