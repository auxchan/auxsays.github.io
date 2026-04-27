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

  // patch feed controls
  const patchFeed = document.getElementById('patch-feed');
  const patchArchiveFeed = document.getElementById('patch-archive-feed');
  const patchSourceGrid = document.getElementById('patch-source-grid');
  const patchSearch = document.getElementById('patch-search');
  const filterChips = Array.from(document.querySelectorAll('#patch-filter-chips [data-filter]'));
  const statusChips = Array.from(document.querySelectorAll('#patch-status-chips [data-status]'));
  const sortChips = Array.from(document.querySelectorAll('#patch-sort-chips [data-sort]'));

  if ((patchFeed || patchSourceGrid) && (filterChips.length || sortChips.length || statusChips.length || patchSearch)) {
    const allCards = Array.from(document.querySelectorAll('.patch-card'));
    const sourceCards = Array.from(document.querySelectorAll('[data-source-card="true"]'));
    let currentFilter = 'all';
    let currentStatus = 'all';
    let currentSort = 'latest';
    const riskRank = { negative: 3, moderate: 2, positive: 1, insufficient: 0, 'insufficient-data': 0 };
    const priorityRank = { core: 3, edge: 2, expansion: 1 };

    const matchesCommonFilters = (card, query, includeStatus = true) => {
      const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.summary].join(' ').toLowerCase();
      const type = (card.dataset.type || '').toLowerCase();
      const category = (card.dataset.category || '').toLowerCase();
      const status = (card.dataset.status || '').toLowerCase();
      const filterPass = currentFilter === 'all' || type.includes(currentFilter) || category.includes(currentFilter);
      const statusPass = !includeStatus || currentStatus === 'all' || status.includes(currentStatus);
      const queryPass = !query || haystack.includes(query);
      return filterPass && statusPass && queryPass;
    };

    const applyPatchFeed = () => {
      const query = (patchSearch?.value || '').toLowerCase().trim();
      const visibleUpdates = [];
      const visibleSources = [];

      allCards.forEach((card) => {
        const isVisible = matchesCommonFilters(card, query, true);
        card.hidden = !isVisible;
        card.classList.toggle('is-hidden', !isVisible);
        if (isVisible) visibleUpdates.push(card);
      });

      visibleUpdates.sort((a, b) => {
        if (currentSort === 'product') return (a.dataset.product || '').localeCompare(b.dataset.product || '');
        if (currentSort === 'risk') {
          const delta = (riskRank[b.dataset.status] || 0) - (riskRank[a.dataset.status] || 0);
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
        if (isVisible) visibleSources.push(card);
      });

      if (patchSourceGrid) {
        if (currentSort === 'product') {
          visibleSources.sort((a, b) => (a.dataset.title || '').localeCompare(b.dataset.title || ''));
        } else if (currentSort === 'risk') {
          visibleSources.sort((a, b) => (priorityRank[b.dataset.priority] || 0) - (priorityRank[a.dataset.priority] || 0));
        }
        const sourceFragment = document.createDocumentFragment();
        visibleSources.forEach((card) => sourceFragment.appendChild(card));
        patchSourceGrid.appendChild(sourceFragment);
      }
    };

    const schedulePatchFeed = rafDebounce(applyPatchFeed);

    patchSearch?.addEventListener('input', schedulePatchFeed, { passive: true });
    filterChips.forEach((chip) => chip.addEventListener('click', () => {
      filterChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentFilter = chip.dataset.filter;
      schedulePatchFeed();
    }));
    statusChips.forEach((chip) => chip.addEventListener('click', () => {
      statusChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentStatus = chip.dataset.status;
      schedulePatchFeed();
    }));
    sortChips.forEach((chip) => chip.addEventListener('click', () => {
      sortChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentSort = chip.dataset.sort;
      schedulePatchFeed();
    }));
    applyPatchFeed();
  }
  // Patch Feed filters and full-card links: public Company / Software / Watchlist lanes.
  const normalizePatchLane = (value) => {
    const lane = String(value || '').trim().toLowerCase();
    if (lane === 'core') return 'company';
    if (lane === 'expansion') return 'software';
    if (lane === 'edge') return 'watchlist';
    return lane;
  };

  const normalizePatchStatus = (value) => {
    const status = String(value || '').trim().toLowerCase().replace(/\s+/g, '-');
    if (status === 'insufficient') return 'insufficient-data';
    return status;
  };

  const patchCardsForFiltering = document.querySelectorAll('.patch-source-card, .patch-card');

  const setPatchCardVisibility = (predicate) => {
    patchCardsForFiltering.forEach((card) => {
      const shouldShow = predicate(card);
      card.hidden = !shouldShow;
      card.classList.toggle('is-filter-hidden', !shouldShow);
      card.style.display = shouldShow ? '' : 'none';
    });
  };

  document.querySelectorAll('[data-priority]').forEach((button) => {
    button.addEventListener('click', () => {
      const selectedLane = normalizePatchLane(button.getAttribute('data-priority'));
      document.querySelectorAll('[data-priority]').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      if (!selectedLane || selectedLane === 'all') {
        setPatchCardVisibility(() => true);
        return;
      }
      setPatchCardVisibility((card) => normalizePatchLane(card.dataset.priority) === selectedLane);
    });
  });

  document.querySelectorAll('[data-status-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      const selectedStatus = normalizePatchStatus(button.getAttribute('data-status-filter'));
      document.querySelectorAll('[data-status-filter]').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      if (!selectedStatus || selectedStatus === 'all') {
        setPatchCardVisibility(() => true);
        return;
      }
      setPatchCardVisibility((card) => normalizePatchStatus(card.dataset.status) === selectedStatus);
    });
  });

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

  // Patch Feed filters repair: handles category, consensus, and public lane chips.
  const normalizeAuxPatchLane = (value) => {
    const lane = String(value || '').trim().toLowerCase();
    if (lane === 'core') return 'company';
    if (lane === 'expansion') return 'software';
    if (lane === 'edge') return 'watchlist';
    return lane;
  };

  const normalizeAuxPatchStatus = (value) => {
    const status = String(value || '').trim().toLowerCase().replace(/\s+/g, '-');
    if (status === 'insufficient') return 'insufficient-data';
    return status;
  };

  const auxPatchCards = document.querySelectorAll('.patch-source-card, .patch-card');
  const auxPatchState = {
    category: 'all',
    status: 'all',
    lane: 'all'
  };

  const applyAuxPatchFilters = () => {
    auxPatchCards.forEach((card) => {
      const cardCategory = String(card.dataset.category || card.dataset.type || '').toLowerCase();
      const cardStatus = normalizeAuxPatchStatus(card.dataset.status);
      const cardLane = normalizeAuxPatchLane(card.dataset.priority);
      const categoryOk = auxPatchState.category === 'all' || cardCategory === auxPatchState.category;
      const statusOk = auxPatchState.status === 'all' || cardStatus === auxPatchState.status;
      const laneOk = auxPatchState.lane === 'all' || cardLane === auxPatchState.lane;
      const show = categoryOk && statusOk && laneOk;
      card.hidden = !show;
      card.classList.toggle('is-filter-hidden', !show);
      card.style.display = show ? '' : 'none';
    });
  };

  document.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      auxPatchState.category = String(button.dataset.filter || 'all').toLowerCase();
      document.querySelectorAll('[data-filter]').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      applyAuxPatchFilters();
    });
  });

  document.querySelectorAll('[data-status], [data-status-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      auxPatchState.status = normalizeAuxPatchStatus(button.dataset.status || button.dataset.statusFilter || 'all');
      document.querySelectorAll('[data-status], [data-status-filter]').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      applyAuxPatchFilters();
    });
  });

  document.querySelectorAll('[data-lane-filter], [data-priority]').forEach((button) => {
    if (button.classList.contains('patch-source-card') || button.classList.contains('patch-card')) return;
    button.addEventListener('click', () => {
      auxPatchState.lane = normalizeAuxPatchLane(button.dataset.laneFilter || button.dataset.priority || 'all');
      document.querySelectorAll('[data-lane-filter], .patch-chip[data-priority]').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      applyAuxPatchFilters();
    });
  });

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
