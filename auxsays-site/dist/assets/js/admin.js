const repoOwner = 'auxchan';
const repoName = 'auxsays.github.io';
const branch = 'main';

document.addEventListener('DOMContentLoaded', async () => {
  const els = {
    token: document.getElementById('gh-token'),
    remember: document.getElementById('remember-token'),
    connect: document.getElementById('connect-token'),
    status: document.getElementById('admin-status'),
    list: document.getElementById('admin-article-list'),
    title: document.getElementById('article-title'),
    slug: document.getElementById('article-slug'),
    app: document.getElementById('article-app'),
    category: document.getElementById('article-category'),
    date: document.getElementById('article-date'),
    tags: document.getElementById('article-tags'),
    excerpt: document.getElementById('article-excerpt'),
    cover: document.getElementById('article-cover'),
    featured: document.getElementById('article-featured'),
    video: document.getElementById('article-video'),
    body: document.getElementById('article-body'),
    downloadLabel: document.getElementById('article-download-label'),
    downloadUrl: document.getElementById('article-download-url'),
    save: document.getElementById('save-article'),
    saveStatus: document.getElementById('save-status'),
    newArticle: document.getElementById('new-article')
  };

  const state = { token: '', articles: [] };

  const remembered = localStorage.getItem('auxsays_token');
  if (remembered) {
    els.token.value = remembered;
    els.remember.checked = true;
  }

  els.connect.addEventListener('click', async () => {
    state.token = els.token.value.trim();
    if (!state.token) {
      setStatus('Paste your GitHub token first.', true);
      return;
    }

    if (els.remember.checked) localStorage.setItem('auxsays_token', state.token);
    else localStorage.removeItem('auxsays_token');

    try {
      await githubRequest('/user', { token: state.token });
      setStatus('Connected. Loading article list...');
      await loadArticles();
    } catch (error) {
      setStatus(`Connection failed: ${error.message}`, true);
    }
  });

  els.newArticle.addEventListener('click', () => {
    clearForm();
    setSaveStatus('Ready for a new article.');
  });

  els.title.addEventListener('input', () => {
    if (!els.slug.dataset.touched) {
      els.slug.value = slugify(els.title.value);
    }
  });

  els.slug.addEventListener('input', () => {
    els.slug.dataset.touched = 'true';
  });

  els.save.addEventListener('click', async () => {
    if (!state.token) {
      setSaveStatus('Connect your GitHub token first.', true);
      return;
    }

    const article = readForm();
    if (!article.title || !article.slug || !article.category) {
      setSaveStatus('Title, slug, and category are required.', true);
      return;
    }

    const path = `content/articles/${article.slug}.md`;
    const content = serializeMarkdown(article);

    try {
      let sha = '';
      try {
        const existing = await githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, { token: state.token });
        sha = existing.sha || '';
      } catch {}

      const body = {
        message: `${sha ? 'Update' : 'Create'} article: ${article.slug}`,
        content: btoa(unescape(encodeURIComponent(content))),
        branch
      };
      if (sha) body.sha = sha;

      await githubRequest(`/repos/${repoOwner}/${repoName}/contents/${path}`, {
        token: state.token,
        method: 'PUT',
        body: JSON.stringify(body)
      });

      setSaveStatus('Saved to GitHub. The Actions workflow will rebuild the site.');
      await loadArticles();
    } catch (error) {
      setSaveStatus(`Save failed: ${error.message}`, true);
    }
  });

  async function loadArticles() {
    const res = await fetch(`/assets/data/article-manifest.json?v=${Date.now()}`);
    state.articles = res.ok ? await res.json() : [];
    renderList();
    setStatus(`Connected. ${state.articles.length} article(s) detected.`);
  }

  function renderList() {
    els.list.innerHTML = state.articles.map(article => `
      <button class="admin-item" type="button" data-source="${article.source}">
        <strong>${escapeHtml(article.title)}</strong>
        <div class="small muted">${escapeHtml(article.category)} • ${escapeHtml(article.date || '')}</div>
      </button>
    `).join('') || '<div class="admin-note small">No articles yet.</div>';

    els.list.querySelectorAll('[data-source]').forEach(btn => {
      btn.addEventListener('click', async () => {
        els.list.querySelectorAll('.admin-item').forEach(x => x.classList.remove('active'));
        btn.classList.add('active');
        await loadArticleIntoForm(btn.dataset.source);
      });
    });
  }

  async function loadArticleIntoForm(source) {
    const res = await fetch(`${source}?v=${Date.now()}`);
    const raw = await res.text();
    const parsed = parseMarkdownFile(raw);
    fillForm(parsed);
    setSaveStatus(`Loaded ${source}`);
  }

  function readForm() {
    return {
      title: els.title.value.trim(),
      slug: els.slug.value.trim() || slugify(els.title.value),
      app: els.app.value.trim(),
      category: els.category.value.trim(),
      date: els.date.value.trim(),
      tags: els.tags.value.split(',').map(x => x.trim()).filter(Boolean),
      excerpt: els.excerpt.value.trim(),
      cover: els.cover.value.trim() || '/assets/img/aux-portrait-bw.jpg',
      featured: els.featured.checked,
      video_embed: els.video.value.trim(),
      download_label: els.downloadLabel.value.trim(),
      download_url: els.downloadUrl.value.trim(),
      body: els.body.value
    };
  }

  function fillForm(article) {
    els.title.value = article.title || '';
    els.slug.value = article.slug || '';
    els.slug.dataset.touched = 'true';
    els.app.value = article.app || '';
    els.category.value = article.category || '';
    els.date.value = article.date || '';
    els.tags.value = (article.tags || []).join(', ');
    els.excerpt.value = article.excerpt || '';
    els.cover.value = article.cover || '/assets/img/aux-portrait-bw.jpg';
    els.featured.checked = Boolean(article.featured);
    els.video.value = article.video_embed || '';
    els.downloadLabel.value = article.download_label || '';
    els.downloadUrl.value = article.download_url || '';
    els.body.value = article.body || '';
  }

  function clearForm() {
    fillForm({
      title: '', slug: '', app: '', category: '', date: '', tags: [], excerpt: '',
      cover: '/assets/img/aux-portrait-bw.jpg', featured: false, video_embed: '',
      download_label: '', download_url: '', body: ''
    });
    els.slug.dataset.touched = '';
  }

  function serializeMarkdown(article) {
    return `---
` +
`title: "${escapeQuotes(article.title)}"
` +
`slug: "${escapeQuotes(article.slug)}"
` +
`app: "${escapeQuotes(article.app)}"
` +
`category: "${escapeQuotes(article.category)}"
` +
`date: "${escapeQuotes(article.date)}"
` +
`tags: [${article.tags.map(t => `"${escapeQuotes(t)}"`).join(', ')}]
` +
`excerpt: "${escapeQuotes(article.excerpt)}"
` +
`cover: "${escapeQuotes(article.cover)}"
` +
`featured: ${article.featured ? 'true' : 'false'}
` +
`video_embed: "${escapeQuotes(article.video_embed)}"
` +
`download_label: "${escapeQuotes(article.download_label)}"
` +
`download_url: "${escapeQuotes(article.download_url)}"
` +
`---

${article.body}
`;
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

  function slugify(input = '') {
    return String(input).toLowerCase().trim().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-');
  }

  function escapeQuotes(value = '') {
    return String(value).replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('\n', '\\n');
  }

  function setStatus(msg, error = false) {
    els.status.textContent = msg;
    els.status.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)';
  }

  function setSaveStatus(msg, error = false) {
    els.saveStatus.textContent = msg;
    els.saveStatus.style.borderColor = error ? 'rgba(207,31,46,.45)' : 'rgba(255,255,255,.12)';
  }

  async function githubRequest(path, { token, method = 'GET', body } = {}) {
    const res = await fetch(`https://api.github.com${path}`, {
      method,
      headers: {
        Accept: 'application/vnd.github+json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {})
      },
      body
    });

    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const data = await res.json();
        if (data.message) msg = data.message;
      } catch {}
      throw new Error(msg);
    }

    return res.json();
  }

  function escapeHtml(value = '') {
    return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  }
});
