# AUXSAYS Repository Facts for Systems Monitor

- Inspected: 2026-08-17
- Approved Phase-2 implementation base: `0cd8c2182cc93e339f857c82711f014b83b79292`
- Implementation branch: `codex/systems-monitor-ui-shell`
- Phase-2 correction HEAD accepted by Taylor for MVP: `7f1a64aa5dcdde652663e8673c8ef75dfb86473d`
- Phase-2 closure commit before Phase-3 approval: `f0002b2e6d6f15f602c5fd1f7c1d66c158643275`
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

## PHASE-3 APPROVED DATA-INTEGRITY BOUNDARY

- Data, Source, Ontology/Crosswalk, and Testing contracts are Taylor-approved BINDING 1.0.0.
- O-003 accepts eight bounded registry indicators and a six-indicator first slice using only BLS CES/CPS/JOLTS and DOL Weekly Claims. CPI-U and real GDP are follow-on registry items.
- O-004 rejects FRED/ALFRED pipeline use under current terms; it is not an ingestion, archive, cross-check, fallback, replay, database/cache, model-feature, or training source.
- Preferred Gate-A factual revision proof is an original DOL Weekly Claims advance release followed by the original subsequent release containing the revised value, with proven publication times and retained permitted provenance.
- Phase-3 implementation authority ends before factual public activation and Phase 4. No API call, data download, dependency install, database/Parquet creation, public activation, push, merge, or deploy occurred in the approval task.

## UNKNOWN — establish in the affected phase

- Final fonts and self-hosting/subsetting strategy.
- Permanent analytics/cloud provider, secrets service, durable store, scheduler, and public API/payload host; selection is intentionally deferred.
- Whether site-wide CSP can be made restrictive without first refactoring existing cdnjs/Google Analytics usage.

## Reinspection triggers

Reinspect only the affected facts when `AGENTS.md`, `.github/workflows/pages.yml`, `auxsays/_config.yml`, `auxsays/Gemfile`, `auxsays/package.json`, `auxsays/_layouts/aux-base.html`, global CSS/JS, or deployment branch policy changes.

## PHASE-3 FIRST-SLICE IMPLEMENTATION EVIDENCE — 2026-08-18

- `systems-monitor/data/` is an isolated Python 3.11+ package with no third-party runtime dependency. It uses standard-library bounded HTTPS retrieval, content-addressed local raw capture, SQLite, deterministic validation/tests, and atomic local candidate pointers. Recurring infrastructure/data cost is $0.
- The source registry enables only BLS CES, BLS CPS, BLS JOLTS, and DOL Weekly Claims. It records reviewed 2026-08-18 official endpoints, current operational limits, cadence/revisions, methodology/terms/rights evidence, parser versions, and a 2027-02-18 terms recheck. The indicator registry has exactly eight entries; the approved six labor observations are enabled and CPI-U/real GDP remain disabled follow-on entries.
- Factual DOL evidence uses original 2024-03-07 and 2024-03-14 weekly-release PDFs for week ending 2024-03-02: advance 217,000, revised 210,000. Their hashes, publication/retrieval/acceptance times, revision link, and dual replay results are retained in a bounded committed test fixture; original bytes remain in the ignored local runtime boundary.
- `data/review/internal-factual-review-model.json` preserves the normalized six-observation review representation. The explicit exporter produces `data/review/factual-snapshot-candidate.json` as an immutable pre-activation build artifact targeting PDI 1.0.0; it has complete rights-cleared payload/provenance and no `publishedAt` or active-snapshot claim. Candidate validation and final active-PDI validation are separate.
- Local activation tests revalidate the candidate, materialize a distinct immutable PDI 1.0.0 snapshot with the actual local activation time, validate it, and atomically update only a temporary local pointer. `data/review/local-active-pdi-test-snapshot.json` is review evidence, not an AUXSAYS.com activation. Public hierarchy uses `childRefs[]`; the frontend derives nested children only after validation.
- Gate-A evidence records two superseded false claims: the original internal-shaped payload was mislabeled PDI-valid, and its replacement used generation time as `publishedAt` despite no activation. Both regression boundaries are now explicit; old candidate SHA `0D463A590921B5652F7D095DE52468937D4B74CB62DC7933C040D89CDF926B9B` is superseded.
- Current DOL evidence distinguishes a current PDF-verified observation for week ending 2026-08-08 from a stale automated XML retrieval path ending 2026-07-18; no automated PDF parser is claimed.
- Taylor approved `HUMAN_DATA_QA ROUND 2 = PASS` and `GATE A = PASS` on
  2026-08-18. Phase 3 Data Integrity is CLOSED. The evidence proves the bounded
  six-observation data-integrity slice; it does not activate factual data or
  claim forecasting, dependency/allocation modeling, or employment prediction.
- Phase 4A Engine / Labor-State Proof implementation is authorized under five
  BINDING 1.0.0 contracts. Phase-4B, new ingestion, cloud/paid service, factual
  activation, push, merge, and deployment remain unauthorized.
- Deferred product debt includes the master/interconnectivity experience and
  clear derivation transparency for `OBS`/`CALC`/`FCST`/`SCEN`; these are design
  inputs, not authorization to redesign the UI.

## PHASE-4 CONTRACT/DESIGN DRAFT — 2026-08-18

- Branch `codex/systems-monitor-state-dependency-design` was created directly
  from Phase-3 closure commit `bab19662046e70c1c1b963e40aa48bae55d233ea`.
- Five Phase-4 contracts exist only as DRAFT 0.1.0 review artifacts: State Model,
  Dependency Relationship, Allocation/Propagation, Derivation Transparency, and
  Phase-4 Testing. `PHASE4_STATE_DEPENDENCY_ALLOCATION_DESIGN.md` integrates
  their current/as-of boundary, proof slice, source-expansion map, Gate-B plan,
  risks, and $0/no-new-dependency posture.
- No Phase-4 runtime source, relationship dataset, state/propagation/allocation
  output, new ingestion, dependency, UI/application, workflow/deployment, or
  Patch Feed file was created or changed. Existing BINDING contracts and the
  authoritative Master Spec remain unchanged.

## PHASE-4 STRUCTURAL GATE-B CORRECTION — 2026-08-19

- External review found the six-labor-observation design adequate for engine
  mechanics but insufficient for BINDING Gate B's authoritative I/O backbone.
  The five contracts and integrated design are corrected to DRAFT 0.1.1.
- Phase 4A is the limited labor engine proof. O-006 accepts six labor inputs,
  maximum depth 3, and maximum eight rounds only as configurable/versioned test
  and calibration settings. Phase 4A cannot pass Gate B.
- Phase 4B requires a bounded original-authority structural I/O proof before Gate
  B, including deterministic accepted relationships, direct/total semantics,
  current observations, real behavioral evidence, current employment exposure,
  complete derivation, performance/cost evidence, and honest coverage. The
  construction-oriented domain is a selection candidate subject to future exact
  authoritative source/table/rights/schema/crosswalk validation.
- No BEA file was discovered/retrieved/ingested, and Real GDP/NIPA remains
  separate. No parser, crosswalk data, relationship dataset, engine/CALC/UI code,
  dependency, graph/cloud infrastructure, factual activation, Phase-5 work,
  workflow/deployment, Patch Feed file, push, merge, or deployment changed.

## PHASE-4 CONTRACT APPROVAL — 2026-08-19

- Taylor accepted/resolved O-005 and promoted all five corrected Phase-4
  contracts from DRAFT 0.1.1 to BINDING 1.0.0.
- The approval authorizes only Phase-4A Engine / Labor-State Proof implementation
  with the O-006 six-input, depth-3, eight-round configurable proof profile.
- Gate B remains OPEN. Phase-4B structural ingestion, BEA retrieval/ingestion,
  new sources, Phase 5, public activation, deployment, and the deferred major
  UI/UX overhaul remain unauthorized.
