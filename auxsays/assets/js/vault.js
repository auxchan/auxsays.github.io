const ownerEl = () => document.getElementById('repo-owner');
const repoEl = () => document.getElementById('repo-name');
const tokenEl = () => document.getElementById('github-token');
const folderEl = () => document.getElementById('site-folder');
const statusEl = () => document.getElementById('vault-status');
const homeEl = () => document.getElementById('home-json');
const aboutEl = () => document.getElementById('about-json');
const postListEl = () => document.getElementById('post-list');
const postBodyEl = () => document.getElementById('post-body');

let currentPostPath = null;

function ghHeaders() {
  return {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${tokenEl().value.trim()}`,
    'X-GitHub-Api-Version': '2022-11-28'
  };
}

function contentPath(relativePath) {
  return `${folderEl().value.trim()}/${relativePath}`;
}

async function getContent(path) {
  const url = `https://api.github.com/repos/${ownerEl().value.trim()}/${repoEl().value.trim()}/contents/${path}`;
  const res = await fetch(url, { headers: ghHeaders() });
  if (!res.ok) throw new Error(`Failed to load ${path}`);
  return res.json();
}

async function putContent(path, content, message) {
  const existing = await getContent(path).catch(() => null);
  const payload = {
    message,
    content: btoa(unescape(encodeURIComponent(content)))
  };
  if (existing?.sha) payload.sha = existing.sha;
  const url = `https://api.github.com/repos/${ownerEl().value.trim()}/${repoEl().value.trim()}/contents/${path}`;
  const res = await fetch(url, {
    method: 'PUT',
    headers: { ...ghHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Failed to save ${path}`);
  return res.json();
}

function decodeGithubContent(content) {
  return decodeURIComponent(escape(atob(content.replace(/\n/g, ''))));
}

async function loadBasics() {
  const [home, about, posts] = await Promise.all([
    getContent(contentPath('_data/home.json')),
    getContent(contentPath('_data/about.json')),
    getContent(contentPath('_posts'))
  ]);

  homeEl().value = decodeGithubContent(home.content);
  aboutEl().value = decodeGithubContent(about.content);

  postListEl().innerHTML = '';
  posts.filter((item) => item.type === 'file' && item.name.endsWith('.md')).forEach((item) => {
    const option = document.createElement('option');
    option.value = item.path;
    option.textContent = item.name;
    postListEl().appendChild(option);
  });
  statusEl().textContent = 'Connected. Loaded home, about, and posts.';
}

async function loadPost(path) {
  const file = await getContent(path);
  currentPostPath = path;
  postBodyEl().value = decodeGithubContent(file.content);
  statusEl().textContent = `Loaded ${path}`;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('vault-connect')?.addEventListener('click', async () => {
    try {
      statusEl().textContent = 'Connecting…';
      await loadBasics();
    } catch (err) {
      statusEl().textContent = err.message;
    }
  });

  document.querySelector('[data-save="home"]')?.addEventListener('click', async () => {
    try {
      JSON.parse(homeEl().value);
      await putContent(contentPath('_data/home.json'), homeEl().value, 'Update home data from vault');
      statusEl().textContent = 'Saved home.json';
    } catch (err) {
      statusEl().textContent = `Home save failed: ${err.message}`;
    }
  });

  document.querySelector('[data-save="about"]')?.addEventListener('click', async () => {
    try {
      JSON.parse(aboutEl().value);
      await putContent(contentPath('_data/about.json'), aboutEl().value, 'Update about data from vault');
      statusEl().textContent = 'Saved about.json';
    } catch (err) {
      statusEl().textContent = `About save failed: ${err.message}`;
    }
  });

  postListEl()?.addEventListener('change', (e) => {
    const value = e.target.value;
    if (value) loadPost(value).catch((err) => { statusEl().textContent = err.message; });
  });

  document.getElementById('new-post')?.addEventListener('click', () => {
    const today = new Date().toISOString().slice(0,10);
    currentPostPath = contentPath(`_posts/${today}-new-post.md`);
    postBodyEl().value = `---
layout: post
title: New Post
date: ${today} 09:00:00 -0700
description: Replace this draft description.
categories: [Free AI Tools]
tags: [draft]
---

Start writing here.`;
    statusEl().textContent = `Scaffolded ${currentPostPath}`;
  });

  document.getElementById('save-post')?.addEventListener('click', async () => {
    try {
      if (!currentPostPath) throw new Error('Load a post or create a scaffold first.');
      await putContent(currentPostPath, postBodyEl().value, 'Update post from vault');
      statusEl().textContent = `Saved ${currentPostPath}`;
      await loadBasics();
    } catch (err) {
      statusEl().textContent = err.message;
    }
  });

  document.getElementById('upload-image')?.addEventListener('click', async () => {
    try {
      const file = document.getElementById('upload-file').files[0];
      const name = document.getElementById('upload-name').value.trim();
      if (!file || !name) throw new Error('Choose an image and destination filename first.');
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const base64 = reader.result.split(',')[1];
          const path = contentPath(`assets/img/${name}`);
          const existing = await getContent(path).catch(() => null);
          const payload = { message: `Upload ${name} from vault`, content: base64 };
          if (existing?.sha) payload.sha = existing.sha;
          const url = `https://api.github.com/repos/${ownerEl().value.trim()}/${repoEl().value.trim()}/contents/${path}`;
          const res = await fetch(url, { method: 'PUT', headers: { ...ghHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          if (!res.ok) throw new Error('Upload failed');
          statusEl().textContent = `Uploaded ${name}`;
        } catch (err) {
          statusEl().textContent = err.message;
        }
      };
      reader.readAsDataURL(file);
    } catch (err) {
      statusEl().textContent = err.message;
    }
  });
});
