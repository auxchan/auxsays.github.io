import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import { marked } from 'marked';

const ROOT = process.cwd();
const DIST = path.join(ROOT, 'dist');
const CONTENT_DIR = path.join(ROOT, 'content', 'articles');
const STATIC_PATHS = ['index.html','portfolio','articles','admin','assets','downloads','CNAME'];
const rmrf = p => fs.rmSync(p,{recursive:true,force:true});
const ensureDir = p => fs.mkdirSync(p,{recursive:true});
const copyRecursive = (src,dest) => {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    ensureDir(dest);
    for (const entry of fs.readdirSync(src)) copyRecursive(path.join(src,entry), path.join(dest,entry));
  } else {
    ensureDir(path.dirname(dest));
    fs.copyFileSync(src,dest);
  }
};
const escapeHtml = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const slugify = s => String(s||'').toLowerCase().trim().replace(/[^a-z0-9\s-]/g,'').replace(/\s+/g,'-').replace(/-+/g,'-');
rmrf(DIST); ensureDir(DIST);
for (const item of STATIC_PATHS) { const src = path.join(ROOT,item); if (fs.existsSync(src)) copyRecursive(src,path.join(DIST,item)); }
const articleFiles = fs.existsSync(CONTENT_DIR) ? fs.readdirSync(CONTENT_DIR).filter(f=>f.endsWith('.md')) : [];
const manifest = [];
const articleTemplate = fs.readFileSync(path.join(ROOT,'articles','_article-shell.html'),'utf8');
for (const file of articleFiles) {
  const fullPath = path.join(CONTENT_DIR,file);
  const raw = fs.readFileSync(fullPath,'utf8');
  const parsed = matter(raw);
  const data = parsed.data || {};
  const slug = data.slug || slugify(path.basename(file,'.md'));
  const title = data.title || slug;
  const html = marked.parse(parsed.content || '');
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
  manifest.push({slug,title,category,tags,excerpt,cover,date,featured,app,path:`/articles/${slug}/`,source:`/content/articles/${file}`,video_embed,download_label,download_url});
  const outHtml = articleTemplate
    .replaceAll('__ARTICLE_TITLE__', escapeHtml(title))
    .replaceAll('__ARTICLE_EXCERPT__', escapeHtml(excerpt))
    .replaceAll('__ARTICLE_DATE__', escapeHtml(date))
    .replaceAll('__ARTICLE_CATEGORY__', escapeHtml(category))
    .replaceAll('__ARTICLE_TAGS__', tags.map(t => `<span class="tag-chip">${escapeHtml(t)}</span>`).join(''))
    .replaceAll('__ARTICLE_COVER__', escapeHtml(cover))
    .replaceAll('__ARTICLE_BODY__', html)
    .replaceAll('__ARTICLE_APP__', escapeHtml(app))
    .replaceAll('__VIDEO_EMBED__', video_embed ? `<div class="article-video">${video_embed}</div>` : '')
    .replaceAll('__DOWNLOAD_BLOCK__', download_url ? `<a class="btn btn-primary" href="${escapeHtml(download_url)}" download>${escapeHtml(download_label || 'Download attached file')}</a>` : '');
  const outDir = path.join(DIST,'articles',slug); ensureDir(outDir); fs.writeFileSync(path.join(outDir,'index.html'), outHtml);
}
manifest.sort((a,b) => new Date(b.date || 0) - new Date(a.date || 0));
ensureDir(path.join(DIST,'assets','data')); fs.writeFileSync(path.join(DIST,'assets','data','article-manifest.json'), JSON.stringify(manifest,null,2));
