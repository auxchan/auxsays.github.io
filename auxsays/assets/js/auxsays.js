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

  // My Patch Watchlist: the visitor's own product list, local to this browser.
  //
  // Local-first by design -- no account, no backend, no API. The only thing stored is a list of
  // canonical product ids, which is the identity the whole site already keys on, so a watch made
  // on a patch page is the same watch the feed filters by. Nothing here is personal information
  // and nothing leaves the browser.
  const WATCHLIST_KEY = 'auxsays.patchWatchlist.v1';
  // Product ids are slugs (`obs-studio`, `microsoft-windows-11`). Anything else in storage was not
  // written by this feature, so it is ignored rather than trusted.
  const PRODUCT_ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;

  const readWatchlist = () => {
    // Storage can be unavailable (private mode, blocked cookies, embedded webview) and its contents
    // can be anything a previous version or another tab wrote. Every failure degrades to "nothing
    // watched" rather than throwing, because a broken list must never break the page around it.
    let raw = null;
    try {
      raw = window.localStorage.getItem(WATCHLIST_KEY);
    } catch (error) {
      return new Set();
    }
    if (!raw) return new Set();
    let parsed = null;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return new Set();
    }
    if (!Array.isArray(parsed)) return new Set();
    const clean = new Set();
    parsed.forEach((entry) => {
      // Strings only. Coercing first would let `[1,2,3]` through, because "1" is slug-shaped --
      // and a number in this list is malformed data, never a product id.
      if (typeof entry !== 'string') return;
      const id = entry.trim().toLowerCase();
      if (PRODUCT_ID_RE.test(id)) clean.add(id);
    });
    return clean;
  };

  const writeWatchlist = (ids) => {
    try {
      window.localStorage.setItem(WATCHLIST_KEY, JSON.stringify(Array.from(ids).sort()));
      return true;
    } catch (error) {
      // Fail soft: the in-memory state still drives this page, it just will not survive a reload.
      return false;
    }
  };

  const watchlistCount = () => readWatchlist().size;
  const isWatched = (productId) => readWatchlist().has(String(productId || '').trim().toLowerCase());

  const setWatched = (productId, watched) => {
    const id = String(productId || '').trim().toLowerCase();
    if (!PRODUCT_ID_RE.test(id)) return false;
    const ids = readWatchlist();
    // A Set makes a repeated watch a no-op, so the same product cannot appear twice in storage.
    if (watched) ids.add(id); else ids.delete(id);
    writeWatchlist(ids);
    return watched;
  };

  const watchToggles = () => Array.from(document.querySelectorAll('[data-watch-product]'));

  const syncWatchControls = () => {
    const ids = readWatchlist();
    watchToggles().forEach((button) => {
      const id = String(button.dataset.watchProduct || '').trim().toLowerCase();
      const name = button.dataset.watchLabel || 'this product';
      const watched = ids.has(id);
      button.setAttribute('aria-pressed', watched ? 'true' : 'false');
      button.classList.toggle('is-watching', watched);
      // The accessible name carries the product, so a screen reader hears which product it is
      // rather than ten identical "Watch product" buttons.
      button.setAttribute('aria-label', watched ? `Watching ${name}. Select to stop watching.` : `Watch ${name}`);
      const text = button.querySelector('[data-watch-text]');
      if (text) text.textContent = watched ? (button.dataset.watchTextOn || 'Watching') : (button.dataset.watchTextOff || 'Watch product');
    });
    document.querySelectorAll('[data-watchlist-count]').forEach((node) => {
      node.textContent = String(ids.size);
    });
    document.dispatchEvent(new CustomEvent('auxsays:watchlist-change', { detail: { size: ids.size } }));
  };

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-watch-product]');
    if (!button) return;
    // Several of these sit inside cards that are themselves links; watching must not navigate.
    event.preventDefault();
    event.stopPropagation();
    const id = button.dataset.watchProduct;
    setWatched(id, !isWatched(id));
    syncWatchControls();
  });

  // Another tab changed the list: reflect it here rather than showing two different truths.
  window.addEventListener('storage', (event) => {
    if (event.key === WATCHLIST_KEY) syncWatchControls();
  });

  if (watchToggles().length || document.querySelector('[data-watchlist-count]')) syncWatchControls();

  // Homepage: surface the visitor's products inside Patch Signals without becoming a second feed.
  // Watched signals are marked and moved to the front; nothing is removed, so a first-time visitor
  // with no local state sees exactly what they saw before, and everyone still discovers the major
  // updates outside their own list.
  const homeSignalList = document.querySelector('[data-home-signal-list]');
  if (homeSignalList) {
    const applyHomeWatchlist = () => {
      const ids = readWatchlist();
      const items = Array.from(homeSignalList.querySelectorAll('[data-home-patch-signal]'));
      const watched = [];
      items.forEach((item) => {
        const hit = ids.has(String(item.dataset.productId || '').trim().toLowerCase());
        item.classList.toggle('is-watched', hit);
        const flag = item.querySelector('[data-home-watch-flag]');
        if (flag) flag.hidden = !hit;
        if (hit) watched.push(item);
      });
      // Move watched items to the front, preserving their order relative to each other.
      watched.reverse().forEach((item) => homeSignalList.prepend(item));
      const note = document.querySelector('[data-home-watchlist-note]');
      if (note) note.hidden = watched.length === 0;
    };
    applyHomeWatchlist();
    document.addEventListener('auxsays:watchlist-change', applyHomeWatchlist);
  }

  // Patch Feed controls: company/software hierarchy filters, compact type/category controls, and sorting.
  const patchFeed = document.getElementById('patch-feed');
  const patchArchiveFeed = document.getElementById('patch-archive-feed');
  const patchSourceGrid = document.getElementById('patch-source-grid');
  const patchSearch = document.getElementById('patch-search');
  const patchCompanySelect = document.getElementById('patch-company-select');
  const patchSoftwareSelect = document.getElementById('patch-software-select');
  const filterChips = Array.from(document.querySelectorAll('#patch-filter-chips [data-filter]'));
  const sortChips = Array.from(document.querySelectorAll('#patch-sort-chips [data-sort]'));
  const priorityChips = Array.from(document.querySelectorAll('#patch-priority-chips [data-priority]'));

  const normalizeLane = (value) => {
    const lane = String(value || '').trim().toLowerCase();
    if (lane === 'core') return 'company';
    if (lane === 'expansion') return 'software';
    // `edge` is a COVERAGE TIER -- how deeply AUXSAYS tracks a company -- and it used to display as
    // "Watchlist". That word now belongs to the visitor's own product list, and one name cannot
    // mean both the site's classification and the reader's personal selection.
    if (lane === 'edge') return 'emerging';
    return lane;
  };
  const normalizeStatus = (value) => {
    const status = String(value || '').trim().toLowerCase().replace(/\s+/g, '-');
    if (status === 'insufficient') return 'insufficient-data';
    return status;
  };

  if ((patchFeed || patchSourceGrid) && (filterChips.length || sortChips.length || priorityChips.length || patchCompanySelect || patchSoftwareSelect || patchSearch)) {
    const allCards = Array.from(document.querySelectorAll('.patch-card'));
    const sourceCards = Array.from(document.querySelectorAll('[data-source-card="true"]'));
    let currentFilter = 'all';
    let currentSort = 'latest';
    let currentLane = 'all';
    let currentCompany = 'all';
    let currentSoftware = 'all';
    let watchlistOnly = false;
    let watchedIds = readWatchlist();
    const riskRank = { negative: 3, moderate: 2, positive: 1, 'insufficient-data': 0, insufficient: 0 };
    const priorityRank = { company: 3, software: 2, emerging: 1, core: 3, expansion: 2, edge: 1 };

    const includesToken = (tokens, token) => {
      if (!token || token === 'all') return true;
      return String(tokens || '').toLowerCase().split(/\s+/).includes(String(token).toLowerCase());
    };

    const matchesUpdateFilters = (card, query) => {
      const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.summary].join(' ').toLowerCase();
      const type = String(card.dataset.type || '').toLowerCase();
      const category = String(card.dataset.category || '').toLowerCase();
      const lane = normalizeLane(card.dataset.priority);
      const companyId = String(card.dataset.companyId || '').toLowerCase();
      const productId = String(card.dataset.productId || '').toLowerCase();
      const filterPass = currentFilter === 'all' || type.includes(currentFilter) || category.includes(currentFilter);
      const lanePass = currentLane === 'all' || lane === currentLane;
      const companyPass = currentCompany === 'all' || companyId === currentCompany;
      const softwarePass = currentSoftware === 'all' || productId === currentSoftware;
      const queryPass = !query || haystack.includes(query);
      // My Watchlist is the visitor's own list, so it filters on the canonical product id and
      // nothing else -- not the title, the logo, the company or the slug.
      const watchlistPass = !watchlistOnly || watchedIds.has(productId);
      return filterPass && lanePass && companyPass && softwarePass && queryPass && watchlistPass;
    };

    const matchesCompanyFilters = (card, query) => {
      const haystack = [card.dataset.title, card.dataset.product, card.dataset.company, card.dataset.summary].join(' ').toLowerCase();
      const type = String(card.dataset.type || '').toLowerCase();
      const category = String(card.dataset.category || '').toLowerCase();
      const lane = normalizeLane(card.dataset.priority);
      const companyId = String(card.dataset.companyId || '').toLowerCase();
      const productIds = String(card.dataset.products || '').toLowerCase();
      const filterPass = currentFilter === 'all' || type.includes(currentFilter) || category.includes(currentFilter);
      const lanePass = currentLane === 'all' || currentLane === 'company' || lane === currentLane;
      const companyPass = currentCompany === 'all' || companyId === currentCompany;
      const softwarePass = currentSoftware === 'all' || includesToken(productIds, currentSoftware);
      const queryPass = !query || haystack.includes(query);
      // NO watchlist gate here, deliberately. These are the company DISCOVERY cards -- the only
      // place to ADD products -- and they ship with data-product-id="", so filtering them by the
      // visitor's list would empty the grid exactly when someone is trying to build that list.
      return filterPass && lanePass && companyPass && softwarePass && queryPass;
    };

    const applyPatchFeed = () => {
      const query = (patchSearch?.value || '').toLowerCase().trim();
      watchedIds = readWatchlist();
      const visibleUpdates = [];
      const visibleSources = [];

      allCards.forEach((card) => {
        const isVisible = matchesUpdateFilters(card, query);
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

      // Two different silences, two different answers. "You have not chosen anything yet" needs a
      // way to start choosing; "nothing is happening to your products" is good news and must not
      // read as a broken page.
      const emptyPanel = document.getElementById('patch-watchlist-empty');
      if (emptyPanel) {
        const showEmpty = watchlistOnly && visibleUpdates.length === 0;
        emptyPanel.hidden = !showEmpty;
        if (showEmpty) {
          const nothingWatched = watchedIds.size === 0;
          emptyPanel.querySelectorAll('[data-watchlist-empty="none-watched"]').forEach((n) => { n.hidden = !nothingWatched; });
          emptyPanel.querySelectorAll('[data-watchlist-empty="no-matches"]').forEach((n) => { n.hidden = nothingWatched; });
        }
      }

      sourceCards.forEach((card) => {
        const isVisible = matchesCompanyFilters(card, query);
        card.hidden = !isVisible;
        card.classList.toggle('is-hidden', !isVisible);
        card.classList.toggle('is-filter-hidden', !isVisible);
        card.style.display = isVisible ? '' : 'none';
        if (isVisible) visibleSources.push(card);
      });

      if (patchSourceGrid) {
        if (currentSort === 'latest') {
          visibleSources.sort((a, b) => {
            const dateDelta = Number(b.dataset.date || 0) - Number(a.dataset.date || 0);
            if (dateDelta !== 0) return dateDelta;
            const countDelta = Number(b.dataset.updateCount || 0) - Number(a.dataset.updateCount || 0);
            if (countDelta !== 0) return countDelta;
            return (a.dataset.company || '').localeCompare(b.dataset.company || '');
          });
        } else if (currentSort === 'software' || currentSort === 'product') {
          visibleSources.sort((a, b) => (a.dataset.product || '').localeCompare(b.dataset.product || '') || (a.dataset.company || '').localeCompare(b.dataset.company || ''));
        } else if (currentSort === 'risk') {
          visibleSources.sort((a, b) => (priorityRank[normalizeLane(b.dataset.watchPriority || b.dataset.priority)] || 0) - (priorityRank[normalizeLane(a.dataset.watchPriority || a.dataset.priority)] || 0) || (a.dataset.company || '').localeCompare(b.dataset.company || ''));
        } else {
          visibleSources.sort((a, b) => (a.dataset.company || '').localeCompare(b.dataset.company || ''));
        }
        const sourceFragment = document.createDocumentFragment();
        visibleSources.forEach((card, index) => {
          card.style.order = String(index);
          sourceFragment.appendChild(card);
        });
        patchSourceGrid.appendChild(sourceFragment);
      }
    };

    const schedulePatchFeed = rafDebounce(applyPatchFeed);

    patchSearch?.addEventListener('input', schedulePatchFeed, { passive: true });
    patchCompanySelect?.addEventListener('change', () => {
      currentCompany = String(patchCompanySelect.value || 'all').toLowerCase();
      schedulePatchFeed();
    });
    patchSoftwareSelect?.addEventListener('change', () => {
      currentSoftware = String(patchSoftwareSelect.value || 'all').toLowerCase();
      schedulePatchFeed();
    });
    filterChips.forEach((chip) => chip.addEventListener('click', () => {
      filterChips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      currentFilter = String(chip.dataset.filter || 'all').toLowerCase();
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

    // My Watchlist is a toggle, not a member of a one-of-many chip row: it narrows whatever the
    // other filters already selected rather than replacing them, so the visitor can still search
    // or sort inside their own list.
    const watchlistChip = document.querySelector('[data-watchlist-filter]');
    watchlistChip?.addEventListener('click', () => {
      watchlistOnly = !watchlistOnly;
      watchlistChip.classList.toggle('is-active', watchlistOnly);
      watchlistChip.setAttribute('aria-pressed', watchlistOnly ? 'true' : 'false');
      schedulePatchFeed();
    });

    document.querySelector('[data-watchlist-action="clear"]')?.addEventListener('click', () => {
      writeWatchlist(new Set());
      syncWatchControls();
      schedulePatchFeed();
    });

    // Watching a product from a discovery card re-filters immediately; the list the visitor is
    // looking at is the list they are building.
    document.addEventListener('auxsays:watchlist-change', schedulePatchFeed);

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
