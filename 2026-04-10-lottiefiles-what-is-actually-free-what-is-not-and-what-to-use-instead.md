<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Vault — {{ site.title }}</title>
    <link rel="stylesheet" href="{{ '/assets/css/auxsays-custom.css' | relative_url }}">
    <script defer src="{{ '/assets/js/vault.js' | relative_url }}"></script>
  </head>
  <body class="vault-page">
    <main class="vault-shell">
      <section class="vault-header">
        <div>
          <div class="eyebrow">Hidden editor</div>
          <h1>Vault</h1>
          <p>Not public-facing. Use a fine-grained GitHub token with contents write access for <code>auxchan/auxsays.github.io</code>.</p>
        </div>
      </section>

      <section class="vault-login panel">
        <h2>Connect</h2>
        <div class="vault-grid">
          <label>Repo owner<input id="repo-owner" value="auxchan"></label>
          <label>Repo name<input id="repo-name" value="auxsays.github.io"></label>
          <label>Site folder<input id="site-folder" value="auxsays"></label>
          <label>GitHub token<input id="github-token" type="password" placeholder="Fine-grained token"></label>
        </div>
        <button id="vault-connect" class="btn btn-primary">Connect</button>
        <p id="vault-status" class="vault-status">Enter your token locally. Nothing is prefilled or stored server-side.</p>
      </section>

      <section class="panel vault-editors">
        <div class="vault-columns">
          <div>
            <h2>Home JSON</h2>
            <textarea id="home-json" spellcheck="false"></textarea>
            <button data-save="home" class="btn btn-secondary">Save Home</button>
          </div>
          <div>
            <h2>About JSON</h2>
            <textarea id="about-json" spellcheck="false"></textarea>
            <button data-save="about" class="btn btn-secondary">Save About</button>
          </div>
        </div>
      </section>

      <section class="panel vault-posts">
        <div class="vault-columns posts-layout">
          <div>
            <h2>Posts</h2>
            <select id="post-list" size="8"></select>
            <button id="new-post" class="btn btn-secondary">New Post Scaffold</button>
          </div>
          <div>
            <h2>Post content</h2>
            <textarea id="post-body" spellcheck="false"></textarea>
            <button id="save-post" class="btn btn-primary">Save Post</button>
          </div>
        </div>
      </section>

      <section class="panel vault-upload">
        <h2>Upload image</h2>
        <div class="vault-grid">
          <label>Destination filename<input id="upload-name" placeholder="aux-about-portrait.jpg"></label>
          <label>Choose file<input id="upload-file" type="file" accept="image/*"></label>
        </div>
        <button id="upload-image" class="btn btn-secondary">Upload to assets/img</button>
      </section>
    </main>
  </body>
</html>
