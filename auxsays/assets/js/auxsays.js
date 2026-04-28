document.addEventListener('DOMContentLoaded', () => {
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
  const desktopMotionQuery = window.matchMedia('(min-width: 900px)');
  const prefersReducedMotion = motionQuery.matches;
  const prefersFinePointer = finePointerQuery.matches;
  const allowAmbientMotion = !prefersReducedMotion && desktopMotionQuery.matches;

  // Systems lottie: keep the premium ambient layer, but avoid running it on touch/mobile
  // where it competes with scrolling. Particles have been removed sitewide.
  if (window.lottie && allowAmbientMotion) {
    const lottieNode = document.getElementById('systems-lottie');
    if (lottieNode && !lottieNode.dataset.loaded) {
      const path = `${window.location.origin}/assets/lottie/systems-pulse.json`;
      try {
        const animation = window.lottie.loadAnimation({
          container: lottieNode,
          renderer: 'svg',
          loop: true,
          autoplay: true,
          path,
        });
        lottieNode.dataset.loaded = 'true';
        document.addEventListener('visibilitychange', () => {
          if (document.hidden) animation.pause();
          else animation.play();
        });
      } catch (e) {}
    }
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
    }, { threshold: 0.08, rootMargin: '0px 0px -4% 0px' });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('is-visible'));
  }

  // homepage coverage cards
  const coverageCards = Array.from(document.querySelectorAll('[data-card]'));
  const prefersTouch = !prefersFinePointer || window.innerWidth < 900;
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
  if (prefersTouch && coverageCards.length) setCardState(coverageCards[0], true);

  const rafDebounce = (fn) => {
    let frame = 0;
    return (...args) => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = 0;
        fn(...args);
      });
    };
  };

  // article search filter
  const search = document.getElementById('article-search');
  const chips = document.querySelectorAll('.chip');
  const articleCards = Array.from(document.querySelectorAll('.article-card'));
  let activeFilter = 'all';
  const applyArticleFilters = () => {
    const query = (search?.value || '').toLowerCase().trim();
    articleCards.forEach((card) => {
      const haystack = [card.dataset.title || '', card.dataset.description || '', card.dataset.tags || ''].join(' ').toLowerCase();
      const categories = (card.dataset.categories || '').toLowerCase();
      const categoryMatch = activeFilter === 'all' || categories.includes(activeFilter);
      const queryMatch = !query || haystack.includes(query);
      card.hidden = !(categoryMatch && queryMatch);
    });
  };
  const scheduleArticleFilters = rafDebounce(applyArticleFilters);
  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      chips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      activeFilter = chip.dataset.filter;
      scheduleArticleFilters();
    });
  });
  search?.addEventListener('input', scheduleArticleFilters, { passive: true });

  // patch feed controls: single normalized filter/sort/click system.
  const patchFeed = document.getElementById('patch-feed');
  const patchArchiveFeed = document.getElementById('patch-archive-feed');
  const patchSourceGrid = document.getElementById('patch-source-grid');
  const patchSearch = document.getElementById('patch-search');
  const patchSourceSelect = document.getElementById('patch-source-select');
  const filterChips = Array.from(document.querySelectorAll('#patch-filter-chips [data-filter]'));
  const statusChips = Array.from(document.querySelectorAll('#patch-status-chips [data-status]'));
  const sortChips = Array.from(document.querySelectorAll('#patch-sort-chips [data-sort]'));
  const priorityChips = Array.from(document.querySelectorAll('#patch-priority-chips [data-priority]'));

  const normalizeLane = (value) => {
    const lane = String(value || '').trim().toLowerCase();
    if (lane === 'core') return 'company';
    if (lane === 'expansion') return 'software';
    if (lane === 'edge') return 'watchlist';
    return lane;
  };
  const normalizeStatus = (value) => {
    const status = String(value || '').trim().toLowerCase().replace(/\s+/g, '-');
    if (status === 'insufficient') return 'insufficient-data';
    return status;
  };

  if ((patchFeed || patchSourceGrid) && (filterChips.length || sortChips.length || statusChips.length || priorityChips.length || patchSourceSelect || patchSearch)) {
    const allCards = Array.from(document.querySelectorAll('.patch-card'));
    const sourceCards = Array.from(document.querySelectorAll('[data-source-card="true"]'));
    let currentFilter = 'all';
    let currentStatus = 'all';
    let currentSort = 'latest';
    let currentLane = 'all';
    let currentSource = 'all';
    const riskRank = { negative: 3, moderate: 2, positive: 1, 'insufficient-data': 0, insufficient: 0 };
    const priorityRank = { company: 3, software: 2, watchlist: 1, core: 3, expansion: 2, edge: 1 };

    const matchesCommonFilters = (card, query, includeStatus = true) => {
      const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.summary].join(' ').toLowerCase();
      const sourceId = String(card.dataset.sourceId || '').toLowerCase();
      const type = String(card.dataset.type || '').toLowerCase();
      const category = String(card.dataset.category || '').toLowerCase();
      const status = normalizeStatus(card.dataset.status);
      const lane = normalizeLane(card.dataset.priority);
      const filterPass = currentFilter === 'all' || type.includes(currentFilter) || category.includes(currentFilter);
      const statusPass = !includeStatus || currentStatus === 'all' || status === currentStatus || status.includes(currentStatus);
      const lanePass = currentLane === 'all' || lane === currentLane;
      const sourcePass = currentSource === 'all' || sourceId === currentSource;
      const queryPass = !query || haystack.includes(query);
      return filterPass && statusPass && lanePass && sourcePass && queryPass;
    };

    const applyPatchFeed = () => {
      const query = (patchSearch?.value || '').toLowerCase().trim();
      const visibleUpdates = [];
      const visibleSources = [];

      allCards.forEach((card) => {
        const isVisible = matchesCommonFilters(card, query, true);
        card.hidden = !isVisible;
        card.classList.toggle('is-hidden', !isVisible);
        card.classList.toggle('is-filter-hidden', !isVisible);
        card.style.display = isVisible ? '' : 'none';
        if (isVisible) visibleUpdates.push(card);
      });

      visibleUpdates.sort((a, b) => {
        if (currentSort === 'company') return (a.dataset.company || '').localeCompare(b.dataset.company || '');
        if (currentSort === 'software' || currentSort === 'product') return (a.dataset.product || '').localeCompare(b.dataset.product || '');
        if (currentSort === 'risk') {
          const delta = (riskRank[normalizeStatus(b.dataset.status)] || 0) - (riskRank[normalizeStatus(a.dataset.status)] || 0);
          if (delta !== 0) return delta;
        }
        return Number(b.dataset.date || 0) - Number(a.dataset.date || 0);
      });

      const currentFragment = document.createDocumentFragment();
      const archiveFragment = document.createDocumentFragment();
      visibleUpdates.forEach((card) => {
        if (card.dataset.kind === 'archived') archiveFragment.appendChild(card);
        else currentFragment.appendChild(card);
      });
      if (patchFeed) patchFeed.appendChild(currentFragment);
      if (patchArchiveFeed) patchArchiveFeed.appendChild(archiveFragment);

      sourceCards.forEach((card) => {
        const isVisible = currentStatus === 'all' && matchesCommonFilters(card, query, false);
        card.hidden = !isVisible;
        card.classList.toggle('is-hidden', !isVisible);
        card.classList.toggle('is-filter-hidden', !isVisible);
        card.style.display = isVisible ? '' : 'none';
        if (isVisible) visibleSources.push(card);
      });

      if (patchSourceGrid) {
        if (currentSort === 'company') {
          visibleSources.sort((a, b) => (a.dataset.company || '').localeCompare(b.dataset.company || ''));
        } else if (currentSort === 'software' || currentSort === 'product') {
          visibleSources.sort((a, b) => (a.dataset.title || '').localeCompare(b.dataset.title || ''));
        } else if (currentSort === 'risk') {
          visibleSources.sort((a, b) => (priorityRank[normalizeLane(b.dataset.priority)] || 0) - (priorityRank[normalizeLane(a.dataset.priority)] || 0));
        }
        const sourceFragment = document.createDocumentFragment();
        visibleSources.forEach((card) => sourceFragment.appendChild(card));
        patchSourceGrid.appendChild(sourceFragment);
      }
    };

    const schedulePatchFeed = rafDebounce(applyPatchFeed);

    patchSearch?.addEventListener('input', schedulePatchFeed, { passive: true });
    patchSourceSelect?.addEventListener('change', () => {
      currentSource = String(patchSourceSelect.value || 'all').toLowerCase();
      schedulePatchFeed();
    });
    filterChips.forEach((chip) => chip.addEventListener('click', () => {
      filterChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentFilter = String(chip.dataset.filter || 'all').toLowerCase();
      schedulePatchFeed();
    }));
    statusChips.forEach((chip) => chip.addEventListener('click', () => {
      statusChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentStatus = normalizeStatus(chip.dataset.status || 'all');
      schedulePatchFeed();
    }));
    priorityChips.forEach((chip) => chip.addEventListener('click', () => {
      priorityChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentLane = normalizeLane(chip.dataset.priority || 'all');
      schedulePatchFeed();
    }));
    sortChips.forEach((chip) => chip.addEventListener('click', () => {
      sortChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentSort = String(chip.dataset.sort || 'latest').toLowerCase();
      schedulePatchFeed();
    }));
    applyPatchFeed();
  }

  // Company software selector: keep all cards visible, but promote the selected software to the first slot.
  document.querySelectorAll('[data-software-selector]').forEach((selector) => {
    const chips = Array.from(selector.querySelectorAll('[data-product-select]'));
    const grid = selector.parentElement ? selector.parentElement.querySelector('[data-product-grid]') : null;
    if (!grid || !chips.length) return;

    const cards = Array.from(grid.querySelectorAll('[data-product-card]'));
    const originalOrder = cards.slice();

    const renderOrder = (selectedId) => {
      const normalized = String(selectedId || 'all');
      const ordered = originalOrder.slice();
      if (normalized !== 'all') {
        const selectedCard = ordered.find((card) => card.dataset.productCard === normalized);
        if (selectedCard) {
          const remaining = ordered.filter((card) => card !== selectedCard);
          ordered.splice(0, ordered.length, selectedCard, ...remaining);
        }
      }
      ordered.forEach((card, index) => {
        card.classList.toggle('is-selected-software', normalized !== 'all' && card.dataset.productCard === normalized);
        card.style.order = String(index);
      });
    };

    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        chips.forEach((item) => item.classList.remove('is-active'));
        chip.classList.add('is-active');
        renderOrder(chip.dataset.productSelect || 'all');
      });
    });

    renderOrder('all');
  });

  // Card click-through: make source/product cards clickable while preserving explicit links/buttons.
  document.querySelectorAll('[data-card-href]').forEach((card) => {
    const openCard = () => {
      const href = card.getAttribute('data-card-href');
      if (href) window.location.href = href;
    };
    card.addEventListener('click', (event) => {
      if (event.target.closest('a, button, input, select, textarea')) return;
      openCard();
    });
    card.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (event.target.closest('a, button, input, select, textarea')) return;
      event.preventDefault();
      openCard();
    });
  });


});
