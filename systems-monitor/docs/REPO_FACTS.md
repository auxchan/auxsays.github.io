# AUXSAYS Repository Facts for Systems Monitor

- Inspected: 2026-08-17
- Validated commit: `adae22a5d6e9f506b5b1fd6868a0690434bea233`
- Validation branch: `codex/systems-monitor-foundation`, based on local `main`
- Repository remote: `https://github.com/auxchan/auxsays.github.io.git`

Revalidate facts whose cited files changed after the validated commit.

## FACT — observed directly

### Repository and framework

- Local repository path during this inspection: `D:\Auxsays\auxsays.github.io`. This is an operator workstation fact, not an application path; application/configuration code must use repo-relative paths.
- Public site source root is `auxsays/`.
- The site uses Jekyll `~> 4.4`, the Chirpy theme, and Jekyll SEO/Sitemap/Archives/Include Cache plugins (`auxsays/Gemfile`, `auxsays/_config.yml`).
- Site URL is `https://auxsays.com` with `baseurl: ""` (`auxsays/_config.yml`).
- Global custom presentation is primarily `auxsays/_layouts/aux-base.html`, `auxsays/assets/css/auxsays-custom.css`, and `auxsays/assets/js/auxsays.js`.
- The global layout currently renders Home, About Aux, Articles, and Patch Feed navigation. It loads Chirpy CSS, one site-wide custom CSS file, Google Analytics, Lottie from cdnjs, and the site-wide JavaScript file.
- Existing CSS contains duplicated selector blocks and global rules. A future React surface needs a scoped root/namespaced styles rather than assuming clean global isolation.

### Deployment and Actions

- Production deploys from pushes to `main` or manual dispatch through `.github/workflows/pages.yml`.
- The Pages job runs on Ubuntu, sets up Ruby 3.3, Node 24, and Python 3.12, generates source health, validates logo assets and patch records, runs `bundle exec jekyll build --trace`, and uploads `auxsays/_site`.
- The current Pages workflow does not install/build a React application.
- Additional workflows are Patch Feed/evidence automation: `consensus-audit.yml`, `davinci-updates.yml`, `obs-evidence-collection.yml`, `obs-evidence-revalidation.yml`, `obs-updates.yml`, `patch-ingest.yml`, and `promote-davinci-verified-reports.yml`.
- Repository instructions prohibit changing the Pages pipeline without explicit instruction and warn that workflow-generated durable records may require a pull before a later push.

### Current tooling

- `auxsays/package.json` is an ESM private tooling package, not a frontend application package.
- Existing Node dev dependencies are Playwright and Simple Icons; there is no React, TypeScript, Vite, Motion, charting, Graphology, Sigma, or frontend test dependency installed on the validated commit.
- `auxsays/Gemfile` governs Jekyll/Ruby dependencies.
- `.gitignore` excludes Jekyll output, Node modules, local Ruby dependencies, Python caches, and specified generated/status artifacts.

### Source-control state at Foundation start

- Starting branch: `expansion-inventory-foundation`.
- Starting branch commit: `762e8efc78ecec6e4561235e72261d58d3ee4b44`.
- Starting worktree: clean (`git status --porcelain=v1` returned no entries).
- Local `main` at branch creation: `adae22a5d6e9f506b5b1fd6868a0690434bea233`.
- Foundation branch: `codex/systems-monitor-foundation`, created from that `main` commit.

## ACCEPTED DECISION — approved project choices

- The public Jekyll surface will live at `/systems-monitor/` under `auxsays/`, while Systems Monitor data/model/application internals remain isolated from Patch Feed.
- A future React/TypeScript sub-application is the likely integration mechanism. It must mount inside a dedicated product root and preserve the existing site/global shell without a broad rewrite.
- **D-007 (ACCEPTED):** Repository-root `systems-monitor/` is the Systems Monitor-owned area for documentation and future isolated product source, configuration, and tests; the Jekyll-served public surface remains under `auxsays/systems-monitor/`.
- **D-008 (ACCEPTED):** `/systems-monitor/` is the durable pathname and supported application state uses validated, canonical query parameters unless a future approved contract amendment changes the routing strategy.

## UNKNOWN — establish in the affected phase

- Exact Phase-2 package location, package manager, lockfile strategy, and build-output ownership.
- Exact approved Pages workflow change and whether UI build artifacts are generated only in CI or committed.
- Chart library selection after accessibility/interaction/bundle proof.
- Final fonts and self-hosting/subsetting strategy.
- Permanent analytics/cloud provider, secrets service, durable store, scheduler, and public API/payload host; selection is intentionally deferred.
- Whether site-wide CSP can be made restrictive without first refactoring existing cdnjs/Google Analytics usage.

## Reinspection triggers

Reinspect only the affected facts when `AGENTS.md`, `.github/workflows/pages.yml`, `auxsays/_config.yml`, `auxsays/Gemfile`, `auxsays/package.json`, `auxsays/_layouts/aux-base.html`, global CSS/JS, or deployment branch policy changes.
