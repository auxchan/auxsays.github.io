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

  // PAINTING AND BROADCASTING ARE SEPARATE, and they have to be. A listener that repaints in
  // response to the change event must not re-broadcast it: the dispatch below is synchronous, so a
  // listener calling the broadcasting version re-enters itself until the stack overflows. The
  // dashboard re-renders its cards on every change and paints the new buttons, so it calls this.
  const paintWatchControls = () => {
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
  };

  const syncWatchControls = () => {
    paintWatchControls();
    document.dispatchEvent(new CustomEvent('auxsays:watchlist-change',
      { detail: { size: readWatchlist().size } }));
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

  // My Installed Versions: which tracked build the reader is actually running.
  //
  // The reader never types a version. They pick a record AUXSAYS already tracks, so what is stored
  // is a real patch identity -- product, version, and the build where the product has one -- and
  // never a guess a semantic-version parser made. That is why there is no parser here.
  const INSTALLED_KEY = 'auxsays.installedVersions.v1';

  const readInstalled = () => {
    // Same fail-soft contract as the watchlist: storage can be unavailable and its contents can be
    // anything. A broken entry is dropped, never thrown, because Patch Stack must still render.
    let raw = null;
    try {
      raw = window.localStorage.getItem(INSTALLED_KEY);
    } catch (error) {
      return {};
    }
    if (!raw) return {};
    let parsed = null;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      return {};
    }
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const clean = {};
    Object.keys(parsed).forEach((key) => {
      const id = String(key || '').trim().toLowerCase();
      const entry = parsed[key];
      if (!PRODUCT_ID_RE.test(id) || !entry || typeof entry !== 'object') return;
      const version = String(entry.v == null ? '' : entry.v).trim();
      const url = String(entry.u == null ? '' : entry.u).trim();
      if (!version) return;
      clean[id] = {
        v: version,
        b: String(entry.b == null ? '' : entry.b).trim(),
        d: String(entry.d == null ? '' : entry.d).trim(),
        u: url.startsWith('/') && !url.startsWith('//') ? url : '',
      };
    });
    return clean;
  };

  const writeInstalled = (map) => {
    try {
      window.localStorage.setItem(INSTALLED_KEY, JSON.stringify(map));
      return true;
    } catch (error) {
      return false;
    }
  };

  const setInstalled = (productId, entry) => {
    const id = String(productId || '').trim().toLowerCase();
    if (!PRODUCT_ID_RE.test(id)) return false;
    const map = readInstalled();
    if (entry === null) delete map[id];
    else map[id] = entry;
    writeInstalled(map);
    document.dispatchEvent(new CustomEvent('auxsays:installed-change', { detail: { id } }));
    return true;
  };

  // The version string carries the only channel signal this repo actually has: three records in
  // 1,200 set a channel label, so a channel taxonomy would have to be invented, and inventing one
  // is explicitly not this feature's job. `beta` is therefore computed at build time from the same
  // textual signal `lib/patch_decision.version_is_beta` uses, and is consumed here, not re-derived.
  // How many releases an upgrade path shows before it starts counting the rest.
  const PATH_LIMIT = 10;

  // PARALLEL SERVICING LINES, read off the record data. No version parsing, no arithmetic: only
  // equality between `update_version` strings and the order the records already have.
  //
  // Windows ships 26H1, 25H2, 24H2 and 23H2 side by side, so "newer by date" is not "later in a
  // sequence" there. PowerPoint is also build-aware but its versions run one after another, so it
  // IS a sequence. Build-awareness alone therefore cannot tell them apart, and grouping every
  // build-aware product by version would shatter PowerPoint's real chronology into 17 singletons.
  //
  // What separates them is structural: a line that STOPS and RESTARTS further down a date-ordered
  // window was running beside another one the whole time. Measured over the shipped payload, that
  // fires for Windows (4 versions in non-contiguous blocks) and for nothing else -- PowerPoint's
  // 17 versions are 17 contiguous blocks.
  const parallelLines = (recs) => {
    const blocks = new Map();
    let prev = null;
    recs.forEach((rec) => {
      const version = rec[0];
      if (version !== prev) blocks.set(version, (blocks.get(version) || 0) + 1);
      prev = version;
    });
    let interleaved = false;
    blocks.forEach((count) => { if (count > 1) interleaved = true; });
    if (interleaved) return true;
    // Interleaving needs a line to appear twice. Two lines that each appear once in the window are
    // still parallel if they shipped on the same DAY -- but that signal only means anything where
    // the version names a LINE. Every non-build-aware product here has a distinct version per
    // record, so co-publication there is just two releases in one day, which GitHub does 18 times.
    if (!recs.some((rec) => String(rec[1] || '') !== '')) return false;
    const byDate = new Map();
    let coPublished = false;
    recs.forEach((rec) => {
      const date = String(rec[2] || '');
      if (!date) return;
      if (!byDate.has(date)) byDate.set(date, rec[0]);
      else if (byDate.get(date) !== rec[0]) coPublished = true;
    });
    return coPublished;
  };

  // Render-ready chronology: oldest first, with every adjacency the record data CANNOT order
  // flagged rather than quietly presented as a step. `startDate` is the reader's own release, so
  // the flag also covers the first step -- the collision that actually happens, because a reader
  // can sit in a tied-date group with the record right above them.
  const asSequence = (records, startDate) => {
    let prevDate = String(startDate || '');
    return records.slice().reverse().map((rec) => {
      const date = String(rec[2] || '');
      const tied = !!(prevDate && date && date === prevDate);
      prevDate = date;
      return { rec: rec, tied: tied };
    });
  };

  // The set of releases newer than the reader, presented in the only shape the data supports.
  const newerView = (newerRecs, allRecs, startDate, truncatedStart) => {
    const hidden = Math.max(0, newerRecs.length - PATH_LIMIT);
    const shown = newerRecs.slice(0, PATH_LIMIT);
    if (parallelLines(allRecs)) {
      // Grouped by line, with NO endpoint. `recs[0]` is the newest record by date, which on a
      // parallel product can sit on an OLDER line than the reader's -- naming it as the end of a
      // path would draw an arrow pointing backwards, underneath a sentence saying no clear update
      // exists. Each group is internally ordered, which is safe: inside one line every record in
      // the corpus has a distinct date.
      const order = [];
      const groups = new Map();
      shown.forEach((rec) => {
        if (!groups.has(rec[0])) { groups.set(rec[0], []); order.push(rec[0]); }
        groups.get(rec[0]).push(rec);
      });
      return {
        pathKind: 'newer',
        parallel: true,
        lines: order.map((version) => ({ version: version, steps: asSequence(groups.get(version), '') })),
        path: [],
        hidden: hidden,
        truncatedStart: !!truncatedStart,
      };
    }
    return {
      pathKind: 'newer',
      parallel: false,
      lines: [],
      path: asSequence(shown, startDate),
      hidden: hidden,
      truncatedStart: !!truncatedStart,
    };
  };

  const installedState = (entry, product) => {
    const recs = Array.isArray(product && product.recs) ? product.recs : [];
    if (!entry) return { state: '' };
    // rec shape: [version, build, date, url, beta]
    // Nothing tracked means nothing to compare against. Reporting "newer releases exist" here
    // would be an assertion about records that do not exist.
    if (!recs.length) return { state: '' };
    const sameIdentity = (r) => r[0] === entry.v && String(r[1] || '') === String(entry.b || '');
    const index = recs.findIndex(sameIdentity);

    if (index < 0) {
      // Absent from the tracked list. Only call that "no longer tracked" when it SHOULD have been
      // in the window we published: anything older than the window is simply older, and saying it
      // vanished would be a confident wrong answer.
      const oldest = recs.length ? String(recs[recs.length - 1][2] || '') : '';
      // STRICTLY newer than the oldest record published. An EQUAL date means a sibling record
      // straddles the window boundary and is still tracked; calling it vanished was a
      // confident wrong answer about a page the reader had just claimed.
      if (entry.d && oldest && entry.d > oldest) {
        // The reader's release should have been in this window and is not. There is no position to
        // measure anything from, so there is no chronology to show -- only the fact itself.
        return { state: 'INSTALLED VERSION NO LONGER TRACKED', pathKind: '' };
      }
      // Older than everything published here. Every listed record is newer than the reader, but
      // releases between theirs and this window exist and are not listed, so the run is marked
      // truncated rather than presented as complete.
      return Object.assign(
        { state: 'NEWER TRACKED VERSION EXISTS', latest: recs[0], mine: null },
        newerView(recs, recs, '', true)
      );
    }
    if (index === 0) return { state: 'CURRENT', latest: recs[0], mine: recs[0], pathKind: '' };

    const newer = recs.slice(0, index);
    const installedIsBeta = !!recs[index][4];
    // "Never point a stable reader AT a beta" is satisfied by choosing a stable target, not by
    // refusing to speak because a beta sits in between. Vetoing on any newer beta made the states
    // non-monotonic: DaVinci 20.3.3 read UPDATE AVAILABLE while 20.3.2, further behind, did not.
    const newerStable = newer.filter((r) => !r[4]);
    if (installedIsBeta || !newerStable.length) {
      return Object.assign(
        { state: 'NEWER TRACKED VERSION EXISTS', latest: recs[0], mine: recs[index] },
        newerView(newer, recs, entry.d, false)
      );
    }
    // Build-aware products run parallel trains: 26H1 is not "an update" to 25H2, it is a different
    // servicing line. Only a newer build of the SAME version is an unambiguous update.
    const buildAware = recs.some((r) => String(r[1] || '') !== '');
    const sameTrain = newerStable.filter((r) => r[0] === entry.v);
    if (buildAware && !sameTrain.length) {
      return Object.assign(
        { state: 'NEWER TRACKED VERSION EXISTS', latest: recs[0], mine: recs[index] },
        newerView(newer, recs, entry.d, false)
      );
    }
    // The state was train-aware but the record displayed next to it was not, so 16 of 24 Windows
    // builds named another servicing train under the one sentence promising the same one.
    //
    // The applicable run is the SAME list the target is drawn from, so the path cannot end anywhere
    // other than the release this state already named. Betas are not steps on it; they are counted
    // so the panel can say so instead of silently dropping them.
    const applicable = buildAware ? sameTrain : newerStable;
    const hidden = Math.max(0, applicable.length - PATH_LIMIT);
    return {
      state: 'UPDATE AVAILABLE',
      latest: applicable[0] || recs[0],
      // The reader's OWN record, so the panel can open on it with the same per-release data every
      // other row carries instead of re-deriving identity from the stored entry.
      mine: recs[index],
      // Only a train-scoped target needs the narrower label: it is the newest on the reader's line,
      // not the newest tracked, and on Windows those are different records.
      latestScope: buildAware ? 'line' : '',
      pathKind: 'upgrade',
      parallel: false,
      lines: [],
      path: asSequence(applicable.slice(0, PATH_LIMIT), entry.d),
      hidden: hidden,
      truncatedStart: false,
      omittedBetas: newer.length - newerStable.length,
    };
  };

  const paintInstalledControls = () => {
    const map = readInstalled();
    document.querySelectorAll('[data-iv-here]').forEach((button) => {
      const id = String(button.dataset.ivHere || '').trim().toLowerCase();
      const entry = map[id];
      const isThis = !!entry && entry.v === (button.dataset.ivV || '')
        && String(entry.b || '') === String(button.dataset.ivB || '');
      button.setAttribute('aria-pressed', isThis ? 'true' : 'false');
      button.classList.toggle('is-installed', isThis);
      const text = button.querySelector('[data-iv-here-text]');
      if (text) text.textContent = isThis ? 'This is your version' : 'I am on this version';
      // Visible words FIRST, so voice control matches what the reader can actually see.
      button.setAttribute('aria-label', isThis
        ? 'This is your version. Select to clear it.'
        : 'I am on this version. Save this release as your installed version.');
    });
    // Product history: mark the row the reader saved. Subtle, and added by the client so the
    // history table itself stays what it was.
    document.querySelectorAll('tr[data-record-url]').forEach((row) => {
      const id = String(row.dataset.recordProduct || '').trim().toLowerCase();
      const entry = map[id];
      const mine = !!entry && entry.u && entry.u === row.dataset.recordUrl;
      row.classList.toggle('is-your-version', mine);
      let marker = row.querySelector('[data-iv-marker]');
      if (mine && !marker) {
        const cell = row.querySelector('.patch-cell-version');
        if (cell) {
          marker = document.createElement('span');
          marker.className = 'patch-iv-yours';
          marker.setAttribute('data-iv-marker', '');
          marker.textContent = 'Your version';
          cell.appendChild(marker);
        }
      } else if (!mine && marker) {
        marker.remove();
      }
    });
  };

  document.addEventListener('click', (event) => {
    const here = event.target.closest('[data-iv-here]');
    if (!here) return;
    event.preventDefault();
    const id = here.dataset.ivHere;
    const already = here.getAttribute('aria-pressed') === 'true';
    setInstalled(id, already ? null : {
      v: here.dataset.ivV || '',
      b: here.dataset.ivB || '',
      d: here.dataset.ivD || '',
      u: here.dataset.ivU || '',
    });
  });

  document.addEventListener('auxsays:installed-change', paintInstalledControls);
  window.addEventListener('storage', (event) => {
    // Broadcast rather than paint. This painter only touches the patch-page button and history
    // rows, neither of which exists on the dashboard -- so painting alone left a second tab
    // reading "Current version not set" over storage that had one. A dispatch writes nothing, so
    // there is no loop.
    if (event.key === INSTALLED_KEY) {
      document.dispatchEvent(new CustomEvent('auxsays:installed-change', { detail: { id: '' } }));
    }
  });
  if (document.querySelector('[data-iv-here], tr[data-record-url]')) paintInstalledControls();

  // My Patch Stack: a dashboard over the SAME watchlist, rendered from a payload Jekyll built.
  //
  // It lives in this closure deliberately, so it reuses `readWatchlist`/`setWatched` rather than
  // re-implementing the id validation and fail-soft storage rules a second time. Unwatch buttons
  // carry `data-watch-product`, so the delegated handler above already drives them and the page
  // re-renders off the same `auxsays:watchlist-change` event every other surface listens to.
  const stackNode = document.getElementById('patch-stack-data');
  if (stackNode) {
    let catalogue = [];
    try {
      const parsed = JSON.parse(stackNode.textContent || '[]');
      if (Array.isArray(parsed)) catalogue = parsed;
    } catch (error) {
      catalogue = [];
    }
    const byId = new Map(catalogue.filter((p) => p && p.id).map((p) => [String(p.id).toLowerCase(), p]));

    const strip = document.querySelector('[data-stack-strip]');
    const emptyPanel = document.querySelector('[data-stack-empty]');
    const body = document.querySelector('[data-stack-body]');
    const attentionGrid = document.querySelector('[data-stack-attention-grid]');
    const attentionNone = document.querySelector('[data-stack-attention-none]');
    const allGrid = document.querySelector('[data-stack-all-grid]');
    const chooserTags = document.querySelector('[data-stack-chooser-tags]');

    // An elevated signal is something the record ALREADY says. Nothing here invents a verdict or
    // promotes negative sentiment into one: rank 0-2 is AVOID / WAIT / TEST FIRST as the shared
    // verdict order defines them, and the official counts are the vendor's own.
    //
    // MONITORING DEGRADED is deliberately NOT an attention trigger. It is the ordinary state for
    // most records, so including it would put almost every product in a section whose only job is
    // to be short. Collection that has stopped or is blocked does qualify.
    const attentionOf = (entry) => {
      if (!entry || !entry.href) return '';
      if (entry.rank === 0 || entry.rank === 1 || entry.rank === 2) return entry.verdict;
      if ((entry.oa || 0) > 0) return `${entry.oa} active vendor issue${entry.oa === 1 ? '' : 's'}`;
      if ((entry.os || 0) > 0) return `${entry.os} safeguard hold${entry.os === 1 ? '' : 's'}`;
      if (entry.mon === 'COLLECTION BLOCKED') return 'Collection blocked';
      if (entry.mon === 'COLLECTION STALE') return 'Collection stale';
      return '';
    };

    const esc = (value) => String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

    // `esc` handles quoting, not schemes. Every href here is a site path, so anything that is not
    // one is dropped rather than rendered as a link.
    const safeHref = (value) => {
      const url = String(value == null ? '' : value).trim();
      return url.startsWith('/') && !url.startsWith('//') ? url : '';
    };

    const cardHtml = (entry, reason) => {
      const name = esc(entry.name || entry.id);
      const hist = esc(safeHref(entry.hist));
      const parts = [];
      parts.push(`<article class="panel patch-stack-card" data-stack-card="${esc(entry.id)}">`);
      parts.push('<div class="patch-stack-card__head">');
      parts.push(`<h3 class="patch-stack-card__name">${hist ? `<a href="${hist}">${name}</a>` : name}</h3>`);
      if (entry.href) {
        parts.push(`<span class="patch-verdict patch-verdict--rank${Number(entry.rank)}">${esc(entry.verdict)}</span>`);
      }
      parts.push('</div>');
      if (entry.href) {
        parts.push(`<p class="patch-stack-card__patch"><a href="${esc(safeHref(entry.href))}">${esc(entry.ver)}</a>`
          + (entry.date ? ` <span>Released ${esc(entry.date)}</span>` : '') + '</p>');
        const meta = [];
        meta.push(`${Number(entry.n) || 0} confirmed report${Number(entry.n) === 1 ? '' : 's'}`);
        if (entry.ev) meta.push(esc(entry.ev));
        if (entry.checked) meta.push(`Evidence checked ${esc(entry.checked)}`);
        if (entry.mon === 'COLLECTION BLOCKED') meta.push('Collection blocked');
        else if (entry.mon === 'COLLECTION STALE') meta.push('Collection stale');
        else if (entry.mon === 'MONITORING DEGRADED') meta.push('Monitoring degraded');
        parts.push(`<ul class="patch-stack-card__meta"><li>${meta.join('</li><li>')}</li></ul>`);
      } else {
        parts.push('<p class="patch-stack-card__patch patch-stack-card__patch--none">No tracked patch records yet.</p>');
      }
      if (reason) parts.push(`<p class="patch-stack-card__reason">Needs attention: ${esc(reason)}</p>`);
      parts.push(installedHtml(entry));
      parts.push('<div class="patch-card-links patch-stack-card__links">');
      if (entry.href) parts.push(`<a class="patch-source-link patch-source-link--primary" href="${esc(safeHref(entry.href))}">View patch →</a>`);
      if (hist) parts.push(`<a class="patch-source-link" href="${hist}">Product history →</a>`);
      parts.push(`<button type="button" class="patch-stack-unwatch" data-watch-product="${esc(entry.id)}"`
        + ` data-watch-label="${name}" data-watch-text-off="Watch product" data-watch-text-on="Watching"`
        + ` aria-pressed="true"><span data-watch-text>Watching</span></button>`);
      parts.push('</div></article>');
      return parts.join('');
    };

    const STATE_COPY = {
      'CURRENT': 'You are on the newest tracked release.',
      'UPDATE AVAILABLE': 'AUXSAYS tracks a newer stable release than yours.',
      'NEWER TRACKED VERSION EXISTS': 'Newer releases are tracked, but none is a clear update to the one you run.',
      'INSTALLED VERSION NO LONGER TRACKED': 'AUXSAYS no longer tracks the release you saved.',
    };

    const recLabel = (rec) => {
      const version = esc(rec[0]);
      const build = String(rec[1] || '') ? ` <span class="patch-iv-build">Build ${esc(rec[1])}</span>` : '';
      const beta = rec[4] ? ' <span class="patch-iv-beta">Beta / preview</span>' : '';
      const date = rec[2] ? ` <span class="patch-iv-date">${esc(rec[2])}</span>` : '';
      return `${version}${build}${date}${beta}`;
    };

    // What a release says about itself, straight out of the payload. Nothing is combined, scored or
    // averaged: each line is one field the record already carries.
    const recMeta = (rec) => {
      const bits = [];
      const reports = Number(rec[7]) || 0;
      bits.push(`${reports} confirmed report${reports === 1 ? '' : 's'}`);
      if (rec[8]) bits.push(esc(rec[8]));
      const active = Number(rec[9]) || 0;
      if (active > 0) bits.push(`${active} active vendor issue${active === 1 ? '' : 's'}`);
      // The notes themselves live on the patch page. This says only that the vendor's own notes
      // were captured for this release, which is a field, not a summary of them.
      if (rec[10]) bits.push('Official notes captured');
      return bits;
    };

    // ROLE is carried in TEXT, not only in the styling, so the two releases that matter are still
    // identifiable without colour.
    const ROLE_TEXT = { mine: 'Your version', target: 'Current target' };

    const stepHtml = (step, role, showTie) => {
      const rec = step.rec;
      const href = esc(safeHref(rec[3]));
      const out = [`<li class="patch-iv-step${role ? ` patch-iv-step--${role}` : ''}">`];
      if (showTie) {
        // Same publish date as the entry above it. The repository records no order inside a tied
        // date, so presenting these as consecutive steps would be inventing one.
        out.push('<p class="patch-iv-tied">Published the same day as the release above —'
          + ' AUXSAYS does not record an order within a shared date.</p>');
      }
      out.push('<p class="patch-iv-step__head">');
      if (role) out.push(`<span class="patch-iv-role">${ROLE_TEXT[role]}</span>`);
      out.push(href ? `<a href="${href}">${recLabel(rec)}</a>` : recLabel(rec));
      out.push('</p>');
      if (rec[5]) {
        out.push(`<p class="patch-iv-step__verdict"><span class="patch-verdict patch-verdict--rank${Number(rec[6])}">`
          + `${esc(rec[5])}</span></p>`);
      }
      const meta = recMeta(rec);
      if (meta.length) out.push(`<ul class="patch-iv-step__meta"><li>${meta.join('</li><li>')}</li></ul>`);
      out.push('</li>');
      return out.join('');
    };

    // THE UPGRADE PATH. Every record shown here, and the order they are shown in, comes from
    // `installedState` -- the same call that produced the state and the target above it. Nothing is
    // re-decided here, so the panel cannot disagree with the sentence it sits under.
    const pathHtml = (product, entry, info) => {
      if (!info || (info.pathKind !== 'upgrade' && info.pathKind !== 'newer')) return '';
      const steps = info.path || [];
      const lines = info.lines || [];
      if (!steps.length && !lines.length) return '';
      const upgrade = info.pathKind === 'upgrade';
      const name = esc(product.name || product.id);
      const hist = esc(safeHref(product.hist));
      const out = [`<details class="patch-iv-path" data-iv-path="${esc(product.id)}">`];
      // The accessible name opens with the visible words (WCAG 2.5.3) and then names the product,
      // because a reader hears this summary once per card.
      out.push(`<summary><span class="patch-iv-path__label">${upgrade
        ? 'What changed since my version'
        : 'Newer tracked releases'}</span><span class="patch-iv-for"> — ${name}</span></summary>`);

      if (info.truncatedStart) {
        out.push('<p class="patch-iv-note">Your release is older than the ones listed here, so the'
          + ' releases in between are not shown.</p>');
      }

      // The notice opens a tied RUN rather than repeating on every member of it. GitHub publishes
      // nine changelog entries on one day, which printed the same disclaimer eight times and buried
      // the releases it was explaining.
      const runOpeners = (steps) => steps.map((step, index) =>
        step.tied && !(index > 0 && steps[index - 1].tied));

      out.push('<ol class="patch-iv-steps">');
      if (info.mine) out.push(stepHtml({ rec: info.mine, tied: false }, 'mine', false));
      else {
        out.push('<li class="patch-iv-step patch-iv-step--mine"><p class="patch-iv-step__head">'
          + `<span class="patch-iv-role">${ROLE_TEXT.mine}</span>${esc(entry.v)}`
          + (entry.b ? ` <span class="patch-iv-build">Build ${esc(entry.b)}</span>` : '') + '</p></li>');
      }

      if (upgrade || !info.parallel) {
        const openers = runOpeners(steps);
        steps.forEach((step, index) => {
          out.push(stepHtml(step, upgrade && index === steps.length - 1 ? 'target' : '', openers[index]));
        });
      }
      out.push('</ol>');

      if (info.parallel) {
        // Grouped by servicing line, with no endpoint. These lines run beside the reader's rather
        // than after it, so there is no "next" release among them to point at.
        out.push('<p class="patch-iv-note">These run as separate servicing lines rather than steps'
          + ' after your release, so AUXSAYS does not place them in one sequence.</p>');
        lines.forEach((line) => {
          out.push(`<h4 class="patch-iv-line">${esc(line.version)}</h4>`);
          out.push('<ol class="patch-iv-steps patch-iv-steps--line">');
          const lineOpeners = runOpeners(line.steps);
          line.steps.forEach((step, index) => out.push(stepHtml(step, '', lineOpeners[index])));
          out.push('</ol>');
        });
      }

      if (Number(info.omittedBetas) > 0) {
        out.push(`<p class="patch-iv-note">${Number(info.omittedBetas)} preview release`
          + `${Number(info.omittedBetas) === 1 ? ' is' : 's are'} tracked between these dates and`
          + ' not shown here. AUXSAYS does not treat a preview as a step you have to take.</p>');
      }
      if (Number(info.hidden) > 0) {
        out.push(`<p class="patch-iv-note">+ ${Number(info.hidden)} additional tracked release`
          + `${Number(info.hidden) === 1 ? '' : 's'}`
          + (hist ? ` — <a href="${hist}">open the full history</a>` : '') + '.</p>');
      }
      out.push('</details>');
      return out.join('');
    };

    const installedHtml = (product) => {
      const recs = Array.isArray(product.recs) ? product.recs : [];
      const id = esc(product.id);
      if (!recs.length) return '';
      const entry = readInstalled()[String(product.id).toLowerCase()];
      const out = ['<div class="patch-iv">'];

      if (!entry) {
        out.push('<p class="patch-iv-prompt">Current version <span>not set</span></p>');
      } else {
        const info = installedState(entry, product);
        const state = info.state;
        const latest = info.latest;
        out.push('<dl class="patch-iv-compare">');
        out.push(`<dt>Your version</dt><dd>${esc(entry.v)}`
          + (entry.b ? ` <span class="patch-iv-build">Build ${esc(entry.b)}</span>` : '') + '</dd>');
        if (latest) {
          // A train-scoped target is the newest release on the READER'S line, which on Windows is a
          // different record from the newest tracked one -- 25H2 26200.9550 while 26H1 28000.3086
          // also exists. Calling that "Latest tracked" was accurate only by luck.
          out.push(`<dt>${info.latestScope === 'line' ? 'Latest on your line' : 'Latest tracked'}</dt>`
            + `<dd>${esc(latest[0])}`
            + (String(latest[1] || '') ? ` <span class="patch-iv-build">Build ${esc(latest[1])}</span>` : '') + '</dd>');
        }
        out.push('</dl>');
        // The STATE is a relationship between two records. The VERDICT stays whatever the patch
        // record already says -- being several releases behind is not itself advice to update.
        out.push(`<p class="patch-iv-state patch-iv-state--${esc(String(state).toLowerCase().replace(/[^a-z]+/g, '-'))}">`
          + `<strong>${esc(state)}</strong> ${esc(STATE_COPY[state] || '')}</p>`);
        out.push(pathHtml(product, entry, info));
      }

      const shown = recs.slice(0, 24);
      out.push('<details class="patch-iv-picker">');
      const productName = esc(product.name || product.id);
      out.push(`<summary>${entry ? 'Change version' : 'Select version'}`
        + `<span class="patch-iv-for"> for ${productName}</span></summary>`);
      out.push('<ul class="patch-iv-list">');
      shown.forEach((rec) => {
        const current = entry && rec[0] === entry.v && String(rec[1] || '') === String(entry.b || '');
        out.push(`<li><button type="button" class="patch-iv-option${current ? ' is-current' : ''}"`
          + ` data-iv-set="${id}" data-iv-v="${esc(rec[0])}" data-iv-b="${esc(rec[1] || '')}"`
          + ` data-iv-d="${esc(rec[2] || '')}" data-iv-u="${esc(safeHref(rec[3]))}"`
          + `${current ? ' aria-current="true"' : ''}>${recLabel(rec)}</button></li>`);
      });
      out.push('</ul>');
      if (Number(product.more) > 0 && product.hist) {
        out.push(`<p class="patch-iv-more">${Number(product.more)} older tracked release`
          + `${Number(product.more) === 1 ? '' : 's'} not listed — `
          + `<a href="${esc(safeHref(product.hist))}">open the full history</a> and use `
          + `<em>I am on this version</em> on the release you run.</p>`);
      }
      out.push('</details>');
      if (entry) {
        // WCAG 2.5.3: the accessible name must CONTAIN the visible label. "Clear your saved version
        // for X" reads well but does not contain "Clear version", so voice control could not act on
        // the words printed on the button.
        out.push(`<button type="button" class="patch-iv-clear" data-iv-clear="${id}"`
          + ` aria-label="Clear version for ${esc(product.name || product.id)}">Clear version</button>`);
      }
      out.push('</div>');
      return out.join('');
    };

    const renderStack = () => {
      const watched = Array.from(readWatchlist())
        .map((id) => byId.get(id))
        .filter(Boolean)                              // unknown ids in storage simply have no card
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')));

      const isEmpty = watched.length === 0;
      if (emptyPanel) emptyPanel.hidden = !isEmpty;
      if (body) body.hidden = isEmpty;
      if (strip) strip.hidden = isEmpty;

      if (isEmpty) {
        if (chooserTags && !chooserTags.childElementCount) {
          chooserTags.innerHTML = catalogue
            .filter((p) => p && p.id)
            // A product with no record yet is still watchable -- the card has a branch for it --
            // so the chooser lists all of them and simply leads with the ones that have patches.
            .sort((a, b) => (a.href ? 0 : 1) - (b.href ? 0 : 1)
              || String(a.name || '').localeCompare(String(b.name || '')))
            .map((p) => `<button type="button" class="patch-watch-tag" data-watch-product="${esc(p.id)}"`
              + ` data-watch-label="${esc(p.name)}" aria-pressed="false">`
              + `<span class="patch-watch-tag__mark" aria-hidden="true"></span>${esc(p.name)}</button>`)
            .join('');
        }
        return;
      }

      const flagged = watched.map((entry) => [entry, attentionOf(entry)]).filter(([, reason]) => reason);
      const withEvidence = watched.filter((entry) => (Number(entry.n) || 0) > 0);

      if (attentionGrid) attentionGrid.innerHTML = flagged.map(([entry, reason]) => cardHtml(entry, reason)).join('');
      if (attentionNone) attentionNone.hidden = flagged.length > 0;
      // Every watched product appears under Your Products, including the flagged ones, so the list
      // is the whole stack rather than the leftovers.
      if (allGrid) allGrid.innerHTML = watched.map((entry) => cardHtml(entry, '')).join('');

      const setCount = (selector, value) => {
        const node = document.querySelector(selector);
        if (node) node.textContent = String(value);
      };
      const installedMap = readInstalled();
      const versionsSet = watched.filter((entry) => installedMap[String(entry.id).toLowerCase()]);
      const haveNewer = versionsSet.filter((entry) => {
        const state = installedState(installedMap[String(entry.id).toLowerCase()], entry).state;
        return state === 'UPDATE AVAILABLE' || state === 'NEWER TRACKED VERSION EXISTS';
      });
      setCount('[data-stack-count-watched]', watched.length);
      setCount('[data-stack-count-attention]', flagged.length);
      setCount('[data-stack-count-evidence]', withEvidence.length);
      setCount('[data-stack-count-versions]', versionsSet.length);
      setCount('[data-stack-count-newer]', haveNewer.length);
    };

    document.addEventListener('click', (event) => {
      const setter = event.target.closest('[data-iv-set]');
      if (setter) {
        event.preventDefault();
        setInstalled(setter.dataset.ivSet, {
          v: setter.dataset.ivV || '',
          b: setter.dataset.ivB || '',
          d: setter.dataset.ivD || '',
          u: setter.dataset.ivU || '',
        });
        return;
      }
      const clearer = event.target.closest('[data-iv-clear]');
      if (clearer) {
        event.preventDefault();
        setInstalled(clearer.dataset.ivClear, null);
      }
    });

    document.addEventListener('auxsays:installed-change', () => {
      // renderStack() replaces both grids, so the control that fired this event is destroyed
      // mid-activation -- and unlike the watchlist path, the trigger here is ALWAYS inside the
      // replaced subtree. Without this a keyboard reader lands back on <body> with every picker
      // slammed shut, and has to Tab from the top of the document to change what they just set.
      const active = document.activeElement;
      const wantSet = active && active.dataset ? active.dataset.ivSet : '';
      const wantClear = active && active.dataset ? active.dataset.ivClear : '';
      const wantV = active && active.dataset ? String(active.dataset.ivV || '') : '';
      const wantB = active && active.dataset ? String(active.dataset.ivB || '') : '';
      // A watched product renders TWICE -- once under Needs attention, once under Your products --
      // so a card id alone does not identify the copy the reader is in. Keying by grid as well
      // keeps an expanded panel expanded in the copy they opened it in, and stops focus teleporting
      // them into the other grid on every change.
      const copyKey = (node) => {
        const card = node && node.closest ? node.closest('[data-stack-card]') : null;
        if (!card) return '';
        return `${card.closest('[data-stack-attention-grid]') ? 'attention' : 'all'}|${card.dataset.stackCard}`;
      };
      // Both disclosures in the card, not just the picker. The upgrade panel is opened by the very
      // control whose activation re-renders the card, so leaving it out collapses it every time.
      const DISCLOSURES = ['.patch-iv-picker', '.patch-iv-path'];
      const openKeys = new Set();
      document.querySelectorAll('[data-stack-card]').forEach((card) => {
        const key = `${card.closest('[data-stack-attention-grid]') ? 'attention' : 'all'}|${card.dataset.stackCard}`;
        DISCLOSURES.forEach((selector) => {
          if (card.querySelector(`${selector}[open]`)) openKeys.add(`${key}|${selector}`);
        });
      });
      const activeCopy = copyKey(active);

      renderStack();
      paintWatchControls();

      document.querySelectorAll('[data-stack-card]').forEach((card) => {
        const key = `${card.closest('[data-stack-attention-grid]') ? 'attention' : 'all'}|${card.dataset.stackCard}`;
        DISCLOSURES.forEach((selector) => {
          const node = card.querySelector(selector);
          if (node && openKeys.has(`${key}|${selector}`)) node.open = true;
        });
      });
      const sameOption = (node) => String(node.dataset.ivV || '') === wantV
        && String(node.dataset.ivB || '') === wantB;
      const sameCopy = (node) => !activeCopy || copyKey(node) === activeCopy;
      const options = wantSet
        ? Array.from(document.querySelectorAll('[data-iv-set="' + wantSet + '"]'))
        : [];
      const mine = options.filter(sameCopy);
      const clearSummaries = wantClear
        ? Array.from(document.querySelectorAll('[data-stack-card="' + wantClear + '"] .patch-iv-picker summary'))
        : [];
      const target = wantSet
        ? (mine.find(sameOption) || options.find(sameOption) || mine[0] || options[0] || null)
        : (wantClear
          ? (clearSummaries.filter(sameCopy)[0] || clearSummaries[0] || null)
          : null);
      if (target) target.focus({ preventScroll: true });

      // Otherwise setting a version is a silent DOM swap: there was no live region on the page.
      const live = document.querySelector('[data-stack-live]');
      if (live && (wantSet || wantClear)) {
        const id = String(wantSet || wantClear).toLowerCase();
        const product = byId.get(id);
        const saved = readInstalled()[id];
        live.textContent = product
          ? (saved
            ? product.name + ': your version is now ' + saved.v + (saved.b ? ' build ' + saved.b : '') + '.'
            : product.name + ': your saved version was cleared.')
          : '';
      }
    });

    renderStack();
    paintWatchControls();
    document.addEventListener('auxsays:watchlist-change', () => {
      // Only rescue focus this re-render actually destroyed. Treating "focus is on <body>" as
      // lost would let a background tab's storage event yank the caret away from someone who was
      // merely scrolling.
      const hadFocus = document.activeElement;
      const wasOnACard = !!(hadFocus && hadFocus.closest && hadFocus.closest('[data-stack-card]'));
      renderStack();
      paintWatchControls();
      if (wasOnACard && !document.body.contains(hadFocus)) {
        // The empty state replaces the grid when the last product goes, and `querySelector` finds
        // headings inside a `hidden` section quite happily -- focusing one is a silent no-op that
        // drops the reader at the top of the document.
        const heading = ['.patch-stack-empty h2', '.patch-stack-attention h2', '.patch-stack-all h2', 'h1']
          .map((sel) => document.querySelector(sel))
          .find((el) => el && el.offsetParent !== null);
        if (heading) {
          heading.setAttribute('tabindex', '-1');
          heading.focus({ preventScroll: true });
        }
      }
    });
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
