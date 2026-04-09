const repoOwner = 'auxchan';
const repoName = 'auxsays.github.io';
const branch = 'main';
const repoBase = 'auxsays';

document.addEventListener('DOMContentLoaded', async () => {
  const els = {
    token: document.getElementById('gh-token'),
    remember: document.getElementById('remember-token'),
    connect: document.getElementById('connect-token'),
    status: document.getElementById('studio-status'),
    articleList: document.getElementById('studio-article-list'),
    siteSave: document.getElementById('save-site-config'),
    siteStatus: document.getElementById('site-save-status'),
    articleSave: document.getElementById('save-article'),
    articleStatus: document.getElementById('article-save-status'),
    newArticle: document.getElementById('new-article'),
    assetFile: document.getElementById('asset-file'),
    assetName: document.getElementById('asset-name'),
    assetUpload: document.getElementById('upload-asset'),
    assetStatus: document.getElementById('asset-save-status')
  };

  const state = { token: '', articles: [], siteConfig: {} };

  const remembered = localStorage.getItem('auxsays_token');
  if (remembered) {
    els.token.value = remembered;
    els.remember.checked = true;
  }

  document.querySelectorAll('[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => switchMode(btn.dataset.mode));
  });

  els.connect.addEventListener('click', async () => {
    state.token = els.token.value.trim();
    if (!state.token) return setStatus('Paste your GitHub token first.', true);

    if (els.remember.checked) localStorage.setItem('auxsays_token', state.token);
    else localStorage.removeItem('auxsays_token');

    try {
      await githubRequest(`/repos/${repoOwner}/${repoName}`, { token: state.token });
      setStatus('Connected. Loading vault data...');
      await loadSiteConfig();
      await loadArticles();
    } catch (error) {
      setStatus(`Connection failed: ${error.message}`, true);
    }
  });

  els.siteSave.addEventListener('click', async () => {
    if (!state.token) return setSiteStatus('Connect first.', true);
    const cfg = readSiteConfig(state.siteConfig);
    try {
      await saveJson(`${repoBase}/content/site-config.json`, cfg, 'Update site config', state.token);
      state.siteConfig = cfg;
      setSiteStatus('Site settings saved to GitHub. Actions will redeploy the site.');
    } catch (error) {
      setSiteStatus(`Save failed: ${error.message}`, true);
    }
  });

  els.newArticle.addEventListener('click', () => {
    clearArticle();
    setArticleStatus('Ready for a new article.');
  });

  document.getElementById('article-title').addEventListener('input', () => {
    const slug = document.getElementById('article-slug');
    if (!slug.dataset.touched) slug.value = slugify(document.getElementById('article-title').value);
  });

  document.getElementById('article-slug').addEventListener('input', () => {
    document.getElementById('article-slug').dataset.touched = 'true';
  });

  els.articleSave.addEventListener('click', async () => {
    if (!state.token) return setArticleStatus('Connect first.', true);
    const article = readArticle();
    if (!article.title || !article.slug || !article.category) {
      return setArticleStatus('Title, slug, and category are required.', true);
    }
    const path = `${repoBase}/content/articles/${article.slug}.md`;
    try {
      await saveText(path, serializeMarkdown(article), `${article.slug}: save article`, state.token);
      setArticleStatus('Article saved. Actions will rebuild the site.');
      await loadArticles();
    } catch (error) {
      setArticleStatus(`Save failed: ${error.message}`, true);
    }
  });

  els.assetUpload.addEventListener('click', async () => {
    if (!state.token) return setAssetStatus('Connect first.', true);
    const file = els.assetFile.files[0];
    if (!file) return setAssetStatus('Choose a file first.', true);
    const safeName = (els.assetName.value.trim() || file.name).replace(/[^a-zA-Z0-9._-]/g, '-');
    const path = `${repoBase}/assets/uploads/${safeName}`;
    try {
      const data = await fileToBase64(file);
      await saveBase64(path, data, `Upload asset: ${safeName}`, state.token);
      setAssetStatus(`Uploaded. Use this path: /assets/uploads/${safeName}`);
    } catch (error) {
      setAssetStatus(`Upload failed: ${error.message}`, true);
    }
  });

  async function loadSiteConfig() {
    const res = await fetch(`/assets/data/site-config.json?v=${Date.now()}`);
    state.siteConfig = res.ok ? await res.json() : {};
    fillSiteConfig(state.siteConfig);
  }

  async function loadArticles() {
    const res = await fetch(`/assets/data/article-manifest.json?v=${Date.now()}`);
    state.articles = res.ok ? await res.json() : [];
    renderArticleList();
    setStatus(`Connected. ${state.articles.length} article(s) detected.`);
  }

  function renderArticleList() {
    els.articleList.innerHTML = state.articles.map(article => `
      <button class="admin-item" type="button" data-source="${article.source}">
        <strong>${escapeHtml(article.title)}</strong>
        <div class="small muted">${escapeHtml(article.category)} • ${escapeHtml(article.date || '')}</div>
      </button>
    `).join('') || '<div class="admin-note small">No articles yet.</div>';

    els.articleList.querySelectorAll('[data-source]').forEach(btn => {
      btn.addEventListener('click', async () => {
        els.articleList.querySelectorAll('.admin-item').forEach(x => x.classList.remove('active'));
        btn.classList.add('active');
        await loadArticleIntoForm(btn.dataset.source);
        switchMode('articles');
      });
    });
  }

  async function loadArticleIntoForm(source) {
    const res = await fetch(`${source}?v=${Date.now()}`);
    const raw = await res.text();
    const parsed = parseMarkdownFile(raw);
    fillArticle(parsed);
    setArticleStatus(`Loaded ${source}`);
  }

  function fillSiteConfig(cfg) {
    const h = cfg.home || {};
    const a = cfg.about || {};
    const b = h.brief || [];
    setVal('cfg-brand-tagline', cfg.brand?.tagline || '');
    setVal('cfg-home-kicker', h.kicker || '');
    setVal('cfg-home-headline', h.headline || '');
    setVal('cfg-home-lead', h.lead || '');
    setVal('cfg-home-coverage', h.coverage_intro || '');
    setVal('cfg-brief1-eyebrow', b[0]?.eyebrow || '');
    setVal('cfg-brief1-title', b[0]?.title || '');
    setVal('cfg-brief1-body', b[0]?.body || '');
    setVal('cfg-brief2-eyebrow', b[1]?.eyebrow || '');
    setVal('cfg-brief2-title', b[1]?.title || '');
    setVal('cfg-brief2-body', b[1]?.body || '');
    setVal('cfg-brief3-eyebrow', b[2]?.eyebrow || '');
    setVal('cfg-brief3-title', b[2]?.title || '');
    setVal('cfg-brief3-body', b[2]?.body || '');
    setVal('cfg-about-title', a.title || '');
    setVal('cfg-about-portrait', a.portrait || '');
    setVal('cfg-about-intro1', a.intro1 || '');
    setVal('cfg-about-intro2', a.intro2 || '');
  }

  function readSiteConfig(previous = {}) {
    const home = previous.home || {};
    const about = previous.about || {};
    return {
      brand: {
        name: 'AUXSAYS',
        tagline: val('cfg-brand-tagline')
      },
      home: {
        ...home,
        kicker: val('cfg-home-kicker'),
        headline: val('cfg-home-headline'),
        lead: val('cfg-home-lead'),
        coverage_intro: val('cfg-home-coverage'),
        brief: [
          { eyebrow: val('cfg-brief1-eyebrow'), title: val('cfg-brief1-title'), body: val('cfg-brief1-body') },
          { eyebrow: val('cfg-brief2-eyebrow'), title: val('cfg-brief2-title'), body: val('cfg-brief2-body') },
          { eyebrow: val('cfg-brief3-eyebrow'), title: val('cfg-brief3-title'), body: val('cfg-brief3-body') }
        ]
      },
      about: {
        ...about,
        title: val('cfg-about-title'),
        portrait: val('cfg-about-portrait'),
        intro1: val('cfg-about-intro1'),
        intro2: val('cfg-about-intro2')
      }
    };
  }

  function readArticle() {
    return {
      title: val('article-title'),
      slug: val('article-slug') || slugify(val('article-title')),
      app: val('article-app'),
      category: val('article-category'),
      date: val('article-date'),
      tags: val('article-tags').split(',').map(x => x.trim()).filter(Boolean),
      excerpt: val('article-excerpt'),
      cover: val('article-cover') || '/assets/img/aux-portrait-color.jpg',
      featured: document.getElementById('article-featured').checked,
      video_embed: val('article-video'),
      download_label: val('article-download-label'),
      download_url: val('article-download-url'),
      body: document.getElementById('article-body').value
    };
  }

  function fillArticle(article) {
    setVal('article-title', article.title || '');
    setVal('article-slug', article.slug || '');
    document.getElementById('article-slug').dataset.touched = 'true';
    setVal('article-app', article.app || '');
    setVal('article-category', article.category || '');
    setVal('article-date', article.date || '');
    setVal('article-tags', (article.tags || []).join(', '));
    setVal('article-excerpt', article.excerpt || '');
    setVal('article-cover', article.cover || '/assets/img/aux-portrait-color.jpg');
    document.getElementById('article-featured').checked = !!article.featured;
    setVal('article-video', article.video_embed || '');
    setVal('article-download-label', article.download_label || '');
    setVal('article-download-url', article.download_url || '');
    document.getElementById('article-body').value = article.body || '';
  }

  function clearArticle() {
    fillArticle({
      title: '', slug: '', app: '', category: '', date: '', tags: [], excerpt: '',
      cover: '/assets/img/aux-portrait-color.jpg', featured: false, video_embed: '',
      download_label: '', download_url: '', body: ''
    });
    document.getElementById('article-slug').dataset.touched = '';
  }

  function serializeMarkdown(article) {
    return [
      '---',
      `title: "${escapeQuotes(article.title)}"`,
      `slug: "${escapeQuotes(article.slug)}"`,
      `app: "${escapeQuotes(article.app)}"`,
      `category: "${escapeQuotes(article.category)}"`,
      `date: "${escapeQuotes(article.date)}"`,
      `tags: [${article.tags.map(t => `"${escapeQuotes(t)}"`).join(', ')}]`,
      `excerpt: "${escapeQuotes(article.excerpt)}"`,
      `cover: "${escapeQuotes(article.cover)}"`,
      `featured: ${article.featured ? 'true' : 'false'}`,
      `video_embed: "${escapeQuotes(article.video_embed)}"`,
      `download_label: "${escapeQuotes(article.download_label)}"`,
      `download_url: "${escapeQuotes(article.download_url)}"`,
      '---',
      '',
      article.body,
      ''
    ].join('\n');
  }

  function parseMarkdownFile(raw) {
    const parts = raw.split('---\n');
    if (parts.length < 3 || !raw.startsWith('---\n')) return { body: raw };
    const frontmatter = parts[1];
    const body = parts.slice(2).join('---\n');
    const out = { body };

    frontmatter.split('\n').forEach(line => {
      const idx = line.indexOf(':');
      if (idx === -1) return;
      const key = line.slice(0, idx).trim();
      let value = line.slice(idx + 1).trim();
      if (value.startsWith('[') && value.endsWith(']')) {
        value = value.slice(1, -1).split(',').map(x => x.trim().replace(/^"|"$/g, '')).filter(Boolean);
      } else if (value === 'true' || value === 'false') {
        value = value === 'true';
      } else {
        value = value.replace(/^"|"$/g, '').replace(/\\n/g, '\n');
      }
      out[key] = value;
    });
    return out;
  }

  function switchMode(mode) {
    document.querySelectorAll('[data-mode]').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
    document.querySelectorAll('.studio-pane').forEach(pane => pane.classList.add('hidden'));
    const pane = document.getElementById(`pane-${mode}`);
    if (pane) pane.classList.remove('hidden');
  }

  function val(id) { return document.getElementById(id).value.trim(); }
  function setVal(id, value) { const el = document.getElementById(id); if (el) el.value = value || ''; }
  function setStatus(msg, error = false) { els.status.textContent = msg; els.status.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)'; }
  function setSiteStatus(msg, error = false) { els.siteStatus.textContent = msg; els.siteStatus.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)'; }
  function setArticleStatus(msg, error = false) { els.articleStatus.textContent = msg; els.articleStatus.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)'; }
  function setAssetStatus(msg, error = false) { els.assetStatus.textContent = msg; els.assetStatus.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)'; }
});

async function saveJson(path, obj, message, token) {
  return saveText(path, `${JSON.stringify(obj, null, 2)}\n`, message, token);
}

async function saveText(path, text, message, token) {
  let sha = '';
  try {
    const existing = await githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, { token });
    sha = existing.sha || '';
  } catch {}
  const body = { message, content: btoa(unescape(encodeURIComponent(text))), branch };
  if (sha) body.sha = sha;
  return githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, { token, method: 'PUT', body: JSON.stringify(body) });
}

async function saveBase64(path, base64, message, token) {
  let sha = '';
  try {
    const existing = await githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, { token });
    sha = existing.sha || '';
  } catch {}
  const body = { message, content: base64, branch };
  if (sha) body.sha = sha;
  return githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, { token, method: 'PUT', body: JSON.stringify(body) });
}

async function githubRequest(path, { token, method = 'GET', body } = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    method,
    headers: {
      'Accept': 'application/vnd.github+json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    },
    body
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.message || `GitHub request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function slugify(input = '') {
  return String(input).toLowerCase().trim().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-');
}

function escapeQuotes(value = '') {
  return String(value).replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('\n', '\\n');
}

function escapeHtml(value = '') {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}
