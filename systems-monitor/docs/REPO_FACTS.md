# AUXSAYS Repository Facts for Systems Monitor

- Inspected: 2026-08-17
- Approved Phase-2 implementation base: `0cd8c2182cc93e339f857c82711f014b83b79292`
- Implementation branch: `codex/systems-monitor-ui-shell`
- Phase-2 correction HEAD accepted by Taylor for MVP: `7f1a64aa5dcdde652663e8673c8ef75dfb86473d`
- Repository remote: `https://github.com/auxchan/auxsays.github.io.git`

Revalidate facts whose cited files changed after the validated commit.

## FACT — observed directly

### Repository and framework

- Local repository path during this inspection: `D:\Auxsays\auxsays.github.io`. This is an operator workstation fact, not an application path; application/configuration code must use repo-relative paths.
- Public site source root is `auxsays/`.
- The site uses Jekyll `~> 4.4`, the Chirpy theme, and Jekyll SEO/Sitemap/Archives/Include Cache plugins (`auxsays/Gemfile`, `auxsays/_config.yml`).
- Site URL is `https://auxsays.com` with `baseurl: ""` (`auxsays/_config.yml`).
- Global custom presentation is primarily `auxsays/_layouts/aux-base.html`, `auxsays/assets/css/auxsays-custom.css`, and `auxsays/assets/js/auxsays.js`.
- The global layout renders Home, About Aux, Articles, Patch Feed, and the narrowly added Systems Monitor route. It loads Chirpy CSS, one site-wide custom CSS file, Google Analytics, Lottie from cdnjs, and the site-wide JavaScript file.
- Existing CSS contains duplicated selector blocks and global rules. A future React surface needs a scoped root/namespaced styles rather than assuming clean global isolation.

### Deployment and Actions

- Production deploys from pushes to `main` or manual dispatch through `.github/workflows/pages.yml`.
- The Pages job runs on Ubuntu, sets up Ruby 3.3, Node 24, and Python 3.12, generates source health, validates logo assets and patch records, runs `bundle exec jekyll build --trace`, and uploads `auxsays/_site`.
- The single Pages build job now installs and validates the package-local Systems Monitor application before Jekyll, verifies its static route/assets after Jekyll, and retains the existing artifact/deploy job relationship.
- Additional workflows are Patch Feed/evidence automation: `consensus-audit.yml`, `davinci-updates.yml`, `obs-evidence-collection.yml`, `obs-evidence-revalidation.yml`, `obs-updates.yml`, `patch-ingest.yml`, and `promote-davinci-verified-reports.yml`.
- Repository instructions prohibit changing the Pages pipeline without explicit instruction and warn that workflow-generated durable records may require a pull before a later push.

### Current tooling

- `auxsays/package.json` remains an ESM private tooling package, not a frontend application package.
- The isolated `systems-monitor/app/` npm package contains exact React 19.2.8, React DOM 19.2.8, React Is 19.2.8, and Recharts 3.10.1 production dependencies plus package-local TypeScript/Vite/Vitest/testing dependencies and lockfile. No root package/lockfile, Motion, Graphology, or Sigma dependency was created.
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

## RESOLVED PHASE-2 REPOSITORY CHOICES

- O-001A/O-001B implemented: isolated npm package and package-local committed lockfile at `systems-monitor/app/`.
- O-001C implemented: Systems-Monitor-owned content-hashed output is generated uncommitted through exact bounded staging/composition paths with safe cleanup and manifest/output equality checks.
- O-001D implemented: the existing single Pages build job builds/validates the UI before Jekyll and verifies the final static route before artifact upload.
- O-002 implementation proof passed for Recharts 3.10.1 with explicit native point controls and table equivalents; Taylor accepted Human UI/comprehension for MVP with further polish deferred.

## PHASE-2 IMPLEMENTATION EVIDENCE

- `systems-monitor/app/` implements the validated fixture, canonical query state, three lazy primary views, bounded lazy Trace, responsive/scoped styling, and automated tests.
- `auxsays/systems-monitor/index.html` is the only product route attachment; generated assets/include and `_site` stay ignored.
- Production output on 2026-08-17: eight content-hashed assets, 630,953 raw bytes, 183,867 gzip bytes, and 155,406 Brotli bytes.
- TypeScript and 29 automated tests passed; existing ingestion-source, Patch Feed, consensus, and logo validations passed.
- Windows Jekyll integration/static validation passed with an uncommitted `timezone: false` override because the existing local bundle lacks `tzinfo`; Ubuntu Pages uses the committed configuration. No deployment was performed.
- The Round-1 correction commit `7f1a64a` raised measured typography floors, reduced visible copy, refined hierarchy/surfaces, passed 29 tests and local build/Jekyll/browser validation, and was accepted by Taylor as **PASS FOR MVP — VISUAL POLISH DEFERRED**. Hosted GitHub Actions execution remains an operational pre-merge/deployment proof obligation.

## UNKNOWN — establish in the affected phase

- Final fonts and self-hosting/subsetting strategy.
- Permanent analytics/cloud provider, secrets service, durable store, scheduler, and public API/payload host; selection is intentionally deferred.
- Whether site-wide CSP can be made restrictive without first refactoring existing cdnjs/Google Analytics usage.

## Reinspection triggers

Reinspect only the affected facts when `AGENTS.md`, `.github/workflows/pages.yml`, `auxsays/_config.yml`, `auxsays/Gemfile`, `auxsays/package.json`, `auxsays/_layouts/aux-base.html`, global CSS/JS, or deployment branch policy changes.
