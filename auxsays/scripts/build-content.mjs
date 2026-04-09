import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();
const DIST = path.join(ROOT, 'dist');
const CONTENT_DIR = path.join(ROOT, 'content', 'articles');
const SITE_CONFIG = path.join(ROOT, 'content', 'site-config.json');
const STATIC_PATHS = ['index.html', 'portfolio', 'articles', 'vault', 'assets', 'downloads', 'CNAME'];

const rmrf = p => fs.rmSync(p, { recursive: true, force: true });
const ensureDir = p => fs.mkdirSync(p, { recursive: true });

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    ensureDir(dest);
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    ensureDir(path.dirname(dest));
    fs.copyFileSync(src, dest);
  }
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function slugify(input = '') {
  return String(input)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function parseFrontMatter(raw) {
  if (!raw.startsWith('---\n')) return { data: {}, content: raw };
  const end = raw.indexOf('\n---\n', 4);
  if (end === -1) return { data: {}, content: raw };
  const front = raw.slice(4, end);
  const content = raw.slice(end + 5);
  const data = {};
  for (const line of front.split('\n')) {
    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (value.startsWith('[') && value.endsWith(']')) {
      value = value.slice(1, -1).split(',').map(x => x.trim().replace(/^"|"$/g, '')).filter(Boolean);
    } else if (value === 'true' || value === 'false') {
      value = value === 'true';
    } else {
      value = value.replace(/^"|"$/g, '').replace(/\\n/g, '\n');
    }
    data[key] = value;
  }
  return { data, content };
}

function inlineMarkdown(text = '') {
  let out = escapeHtml(text);
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  return out;
}

function markdownToHtml(md = '') {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  let html = '';
  let inUl = false;
  let inOl = false;
  let inBlockquote = false;
  let paragraph = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const text = paragraph.join(' ').trim();
    if (text) html += `<p>${inlineMarkdown(text)}</p>`;
    paragraph = [];
  };

  const closeLists = () => {
    if (inUl) { html += '</ul>'; inUl = false; }
    if (inOl) { html += '</ol>'; inOl = false; }
  };

  const closeBlockquote = () => {
    if (inBlockquote) { flushParagraph(); html += '</blockquote>'; inBlockquote = false; }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      closeLists();
      closeBlockquote();
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      closeLists();
      closeBlockquote();
      const level = heading[1].length;
      html += `<h${level}>${inlineMarkdown(heading[2])}</h${level}>`;
      continue;
    }

    if (line.startsWith('> ')) {
      flushParagraph();
      closeLists();
      if (!inBlockquote) { html += '<blockquote>'; inBlockquote = true; }
      paragraph.push(line.slice(2));
      continue;
    }

    const ol = line.match(/^\d+\.\s+(.*)$/);
    if (ol) {
      flushParagraph();
      closeBlockquote();
      if (!inOl) { closeLists(); html += '<ol>'; inOl = true; }
      html += `<li>${inlineMarkdown(ol[1])}</li>`;
      continue;
    }

    const ul = line.match(/^[-*]\s+(.*)$/);
    if (ul) {
      flushParagraph();
      closeBlockquote();
      if (!inUl) { closeLists(); html += '<ul>'; inUl = true; }
      html += `<li>${inlineMarkdown(ul[1])}</li>`;
      continue;
    }

    paragraph.push(line);
  }

  flushParagraph();
  closeLists();
  closeBlockquote();
  return html;
}

rmrf(DIST);
ensureDir(DIST);
for (const item of STATIC_PATHS) {
  const src = path.join(ROOT, item);
  if (fs.existsSync(src)) copyRecursive(src, path.join(DIST, item));
}

ensureDir(path.join(DIST, 'assets', 'data'));
if (fs.existsSync(SITE_CONFIG)) {
  fs.copyFileSync(SITE_CONFIG, path.join(DIST, 'assets', 'data', 'site-config.json'));
}

const articleFiles = fs.existsSync(CONTENT_DIR)
  ? fs.readdirSync(CONTENT_DIR).filter(f => f.endsWith('.md'))
  : [];

const manifest = [];
const articleTemplate = fs.readFileSync(path.join(ROOT, 'articles', '_article-shell.html'), 'utf8');

for (const file of articleFiles) {
  const fullPath = path.join(CONTENT_DIR, file);
  const raw = fs.readFileSync(fullPath, 'utf8');
  const parsed = parseFrontMatter(raw);
  const data = parsed.data || {};
  const slug = data.slug || slugify(path.basename(file, '.md'));
  const title = data.title || slug;
  const html = markdownToHtml(parsed.content || '');
  const tags = Array.isArray(data.tags) ? data.tags : [];
  const category = data.category || 'Uncategorized';
  const excerpt = data.excerpt || '';
  const cover = data.cover || '/assets/img/aux-portrait-bw.jpg';
  const date = data.date || '';
  const app = data.app || '';
  const featured = Boolean(data.featured);
  const video_embed = data.video_embed || '';
  const download_label = data.download_label || '';
  const download_url = data.download_url || '';

  manifest.push({
    slug,
    title,
    category,
    tags,
    excerpt,
    cover,
    date,
    featured,
    app,
    path: `/articles/${slug}/`,
    source: `/content/articles/${file}`,
    video_embed,
    download_label,
    download_url
  });

  const outHtml = articleTemplate
    .replaceAll('__ARTICLE_TITLE__', escapeHtml(title))
    .replaceAll('__ARTICLE_EXCERPT__', escapeHtml(excerpt))
    .replaceAll('__ARTICLE_DATE__', escapeHtml(date))
    .replaceAll('__ARTICLE_CATEGORY__', escapeHtml(category))
    .replaceAll('__ARTICLE_TAGS__', tags.map(t => `<span>${escapeHtml(t)}</span>`).join(' • '))
    .replaceAll('__ARTICLE_COVER__', escapeHtml(cover))
    .replaceAll('__ARTICLE_BODY__', html)
    .replaceAll('__ARTICLE_APP__', escapeHtml(app))
    .replaceAll('__VIDEO_EMBED__', video_embed ? `<div class="article-video">${video_embed}</div>` : '')
    .replaceAll('__DOWNLOAD_BLOCK__', download_url ? `<a class="btn btn-primary" href="${escapeHtml(download_url)}" download>${escapeHtml(download_label || 'Download attached file')}</a>` : '');

  const outDir = path.join(DIST, 'articles', slug);
  ensureDir(outDir);
  fs.writeFileSync(path.join(outDir, 'index.html'), outHtml);
}

manifest.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
fs.writeFileSync(path.join(DIST, 'assets', 'data', 'article-manifest.json'), JSON.stringify(manifest, null, 2));
