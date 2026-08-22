# Systems Monitor Decisions

Accepted decisions are authoritative below approved/BINDING contracts and above scoped implementation tasks. Proposed decisions become authoritative only through Taylor approval or approval of their governing contract. Open decisions are not permission to guess.

## D-001 — Public route

- Date: 2026-08-17
- Decision: Systems Monitor public route is `/systems-monitor/`.
- Status: ACCEPTED
- Reason: Confirmed by Master V4.1 and the Foundation task.
- Affected contracts: Product, Repository Integration, Release Acceptance
- Supersedes: Earlier route/subdomain discussion

## D-002 — First-class product boundary

- Date: 2026-08-17
- Decision: Systems Monitor is a new first-class AUXSAYS.com product area alongside Patch Feed, not a Patch Feed replacement.
- Status: ACCEPTED
- Reason: Preserve the existing product while introducing an isolated analytical application.
- Affected contracts: Product, Repository Integration, Architecture
- Supersedes: None

## D-003 — Foundation public host

- Date: 2026-08-17
- Decision: GitHub Pages/Jekyll remains the public site host during Foundation.
- Status: ACCEPTED
- Reason: Existing deployment is operational and broad hosting migration is out of scope.
- Affected contracts: Repository Integration, Infrastructure
- Supersedes: None

## D-004 — Permanent analytics provider deferred

- Date: 2026-08-17
- Decision: Permanent analytics cloud-provider selection is deferred until vertical-slice workload measurements exist.
- Status: ACCEPTED
- Reason: Provider selection must follow measured compute, storage, traffic, cost, and rights constraints.
- Affected contracts: Architecture, Infrastructure
- Supersedes: None

## D-005 — Architectural separation

- Date: 2026-08-17
- Decision: Presentation, read-only public data, compute, and durable storage are separate architectural boundaries.
- Status: ACCEPTED
- Reason: Protect frontend stability and allow later infrastructure selection without schema leakage.
- Affected contracts: Architecture, Infrastructure, Public Data Interface
- Supersedes: None

## D-006 — Primary UX

- Date: 2026-08-17
- Decision: Primary UX is Summary / Verified Data / Outlook with progressive `10 -> 10 -> 10` navigation; a giant graph is not the default.
- Status: ACCEPTED
- Reason: Core product comprehension and Master invariants.
- Affected contracts: Product, Repository Integration, Public Data Interface, Release Acceptance
- Supersedes: None

## D-007 — Foundation documentation location

- Date: 2026-08-17
- Decision: Place the isolated Foundation package at repository-root `systems-monitor/docs/`; reserve `systems-monitor/` for future product-owned source, configuration, tests, and documentation while the Jekyll-served surface remains under `auxsays/`.
- Status: ACCEPTED — Taylor approval 2026-08-17
- Reason: Matches Master §60, avoids Patch Feed internals, and keeps product governance near future product code.
- Affected contracts: Repository Integration, Architecture
- Supersedes: None

## D-008 — GitHub Pages-safe state URLs

- Date: 2026-08-17
- Decision: Use the real static route `/systems-monitor/` as the durable pathname and serialize supported application state in validated query parameters. Do not require server-side SPA rewrites or unsupported deep pathnames.
- Status: ACCEPTED — Taylor approval 2026-08-17; baseline implemented by Repository Integration requirement RI-004
- Reason: Direct navigation and refresh must work on GitHub Pages. Query-state URLs preserve back/forward and shareability without site-wide 404 interception.
- Affected contracts: Repository Integration, Public Data Interface, Release Acceptance
- Supersedes: None

## D-009 — MVP system-evaluation heartbeat and source-aware freshness

- Date: 2026-08-17
- Decision: During normal MVP operation, the base system evaluates whether relevant source or state changes warrant publication at least once every four hours, supplemented by source-specific cadences, known-release-aware checks, and material-change triggers. The heartbeat does not require universal refetch, full-model recomputation, or publication when nothing material changed.
- Status: ACCEPTED — post-V4.1 Taylor review requirement pending future Master consolidation
- Reason: Keep the monitor operationally alive without misrepresenting slow official sources or creating unnecessary compute and polling cost.
- Affected contracts: Infrastructure, Public Data Interface, Release Acceptance
- Supersedes: None

## D-010 — Compute-once/read-many cost governance

- Date: 2026-08-17
- Decision: Prefer bounded scheduled, event-driven, or batch computation and publish reusable validated results for public reads. Introduce paid infrastructure or data APIs only when measured requirements or material incremental value justify recurring cost, with cost envelopes and monitoring where supported.
- Status: ACCEPTED — post-V4.1 Taylor review requirement pending future Master consolidation
- Reason: Minimize recurring infrastructure and API expense before measured product demand justifies expansion.
- Affected contracts: Infrastructure, Public Data Interface, Release Acceptance
- Supersedes: None

## Phase-2 engineering choices and open approval decisions

### O-001A — React application/package location

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: RESOLVED / IMPLEMENTED — 2026-08-17
- Selected choice: One isolated React/TypeScript package at repository-relative `systems-monitor/app/`.
- Rationale: D-007 assigns `systems-monitor/` to product-owned source/config/tests, while `auxsays/package.json` is an existing site-tools package. Isolation avoids mixing dependency and ownership boundaries.
- Implemented paths: `systems-monitor/app/package.json`, `systems-monitor/app/package-lock.json`, `systems-monitor/app/src/`, `systems-monitor/app/tests/`, and package-local config/scripts.
- Compatibility implications: Commands and config must be repo-relative, work on Windows and Ubuntu/Node 24, emit `/systems-monitor/`-safe URLs, and avoid Patch Feed imports. No path was created by this decision.

### O-001B — Package-manager and lockfile strategy

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: RESOLVED / IMPLEMENTED — 2026-08-17
- Selected choice: npm with one committed `systems-monitor/app/package-lock.json`; future CI uses package-local `npm ci`.
- Rationale: Node/npm already exists in the Pages environment, so this adds no package-manager bootstrap or repository-root workspace and gives deterministic isolated installs.
- Implemented paths: `systems-monitor/app/package.json`, its lockfile, and package-local scripts/config.
- Compatibility implications: Pin supported Node/npm behavior, align with current Node 24 CI, and do not create a repository-root lockfile or merge app dependencies into `auxsays/package.json`. Exact dependency versions require a fresh audit before authorized installation.

### O-001C — Build-output ownership/location

- Classification: TAYLOR APPROVAL DECISION
- Status: ACCEPTED / RESOLVED — TAYLOR APPROVAL, 2026-08-17; design approval only
- Rationale: Whether build output is committed or CI-generated, and where it is published, materially affects repository ownership and the Jekyll publication boundary.
- Approved choice: React/TypeScript source remains `systems-monitor/app/`. Systems Monitor owns clean, uncommitted, content-hashed output staged at `systems-monitor/.build/ui/`; a bounded manifest-aware step may temporarily populate only `auxsays/systems-monitor/assets/` and `auxsays/_includes/generated/systems-monitor-assets.html`; Jekyll owns final composition into `auxsays/_site/systems-monitor/`.
- Guardrails: future ignore rules cover generated paths; cleanup deletes only explicitly Systems-Monitor-owned generated paths; manifest validation rejects missing, unreferenced, wrong-base, or stale artifacts before upload; build failure leaves the last valid site live. No path or output was created by this approval.
- Alternatives considered: committed built output; fixed unhashed assets; post-Jekyll SPA overlay; separate artifact job. See `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §8.

### O-001D — GitHub Pages workflow integration

- Classification: TAYLOR APPROVAL DECISION
- Status: ACCEPTED / RESOLVED — TAYLOR APPROVAL, 2026-08-17; architecture approval only
- Rationale: Workflow integration changes deployment behavior and repository automation; Phase 1 authorizes neither a workflow change nor a production-site change.
- Approved choice: retain the existing single Pages build job and one Jekyll-produced artifact. Future scoped implementation may run package-local `npm ci` and Systems Monitor build/composition before Jekyll, then Systems-Monitor-specific static-site validation before the existing artifact upload. Failure blocks upload/deploy and leaves the prior valid release live; existing Patch Feed generation/validation remains intact.
- Rollback and future paths: remove only narrowly approved Systems Monitor install/build/verify and Jekyll attachment changes. Affected paths are `.github/workflows/pages.yml`, `.gitignore`, `systems-monitor/app/` package/config/scripts, and the minimal `auxsays/systems-monitor/` attachment plus generated include/assets paths. No workflow or Jekyll file was changed by this approval. See design §9.

### O-002 — Phase-2 chart candidate

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: RESOLVED / IMPLEMENTED — 2026-08-17: Recharts 3.10.1 passed exact-version verification
- Selected choice: Recharts, because its React/TypeScript composition, responsive/reference primitives, default Recharts 3 accessibility layer, and documented keyboard data-point navigation best match the focused V1 shell.
- Alternative: Apache ECharts remains viable for later large/complex visualization, but its documented ARIA capability is opt-in and does not establish equivalent keyboard data-point navigation for this requirement set.
- Evidence: Exact-version license/transitive/security, React compatibility, accessibility, touch, customization, annotation, bundle, and performance proofs passed in the Phase-2 implementation records. Reopen and return the tradeoff to Taylor if a material regression later fails those requirements.

## Phase-3 approval decisions

### O-003 — Initial Data Integrity scope

- Classification: TAYLOR APPROVAL DECISION
- Status: ACCEPTED / RESOLVED — TAYLOR APPROVAL, 2026-08-17
- Approved choice: Bound the initial registry to eight indicators: total nonfarm payrolls, U-3 unemployment, labor-force participation, initial claims, job openings, hires, CPI-U all items, and real GDP. The first implementation slice enables only the first six labor indicators from BLS CES/CPS/JOLTS and DOL Weekly Claims.
- Reason: The slice is small enough to prove registry, health, revisions, bitemporal and mixed-frequency semantics, rights, idempotency, and factual-candidate publication without entering Phase 4 or forecasting.
- Affected draft contracts: Data, Source, Ontology/Crosswalk, Testing
- Follow-on boundary: CPI-U and real GDP remain approved registry items but are not first-slice ingestion requirements. Expansion beyond eight indicators requires subsequent approved scope.
- Implementation effect: The six-indicator first slice may begin only after all four governing contracts are BINDING; factual public activation still requires Gate-A/activation approval.

### O-004 — Tier-B ALFRED historical-vintage evidence

- Classification: TAYLOR APPROVAL DECISION
- Status: RESOLVED — REJECTED / NOT AUTHORIZED — TAYLOR, 2026-08-17
- Rejected choice: FRED/ALFRED may not be used as an ingestion, archival/vintage, stored cross-check, numerical fallback, historical replay, model-feature/training, database, compilation, archive, or cache source under current terms.
- Reason: Independent recheck of the official FRED Services/API terms on 2026-08-17 found prohibitions on software/system or machine-learning use and storing/caching/archiving/database incorporation that are materially incompatible with the planned AUXSAYS pipeline.
- Affected contracts: Data, Source, Testing
- Replacement proof: Gate A uses an original Tier-A DOL Weekly Claims advance release and the subsequent original release containing the revised value, with independently proven publication times and immutable provenance.
- Reconsideration: Only explicit written permission or materially changed terms, a fresh rights review, and a new Taylor decision may reopen project use. No substitute aggregator is authorized by this rejection.

## Phase-4 approval decisions

### O-005 — Promote the Phase-4 contract package

- Classification: TAYLOR APPROVAL DECISION
- Status: ACCEPTED / RESOLVED — TAYLOR, 2026-08-19
- Approved choice: Promote the externally reviewed State Model, Dependency
  Relationship, Allocation/Propagation, Derivation Transparency, and Phase-4
  Testing contracts from DRAFT 0.1.1 to BINDING 1.0.0 and authorize only the
  Phase-4A Engine / Labor-State Proof implementation.
- Boundary: Gate B remains OPEN. Phase-4B structural ingestion, new-source
  ingestion, forecasting, public activation, deployment, and the deferred major
  UI/UX overhaul remain unauthorized.

### O-006 — Approve the first Phase-4 proof slice and run profile

- Classification: TAYLOR APPROVAL DECISION
- Status: ACCEPTED / RESOLVED — TAYLOR, 2026-08-19 — INITIAL PROOF PROFILE ONLY
- Approved choice: The six factual labor indicators are Phase-4A engine-proof
  inputs. Initial maximum propagation depth is 3 and initial maximum propagation
  rounds is 8.
- Configuration boundary: Both limits are configurable, versioned,
  reproducible, finite, and measurable test/calibration settings—not permanent
  economic constants. Longer paths are not declared economically irrelevant.
- Gate boundary: Phase 4A cannot pass Gate B alone. Gate B requires Phase-4B
  original-authority structural I/O evidence and all corrected acceptance
  requirements. O-006 does not promote a contract or authorize implementation,
  ingestion, relationships, calculations, publication, UI work, or deployment.

### O-007 — Select Phase-4 storage and graph structures

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: OPEN — DEFERRED UNTIL CONTRACT PROMOTION AND IMPLEMENTATION AUTHORITY
- Choice later: Select exact standard data structures, SQLite/file schemas,
  canonical serialization, indexes, and measured performance budgets. Propose a
  library only if approved requirements and evidence show existing tooling is
  insufficient, followed by license/security/cost review.
- Boundary: No dependency or permanent graph/cloud infrastructure is selected by
  the approved Phase-4A scope.

### O-008 — Approve the Phase-4B structural source and bounded vertical slice

- Classification: TAYLOR APPROVAL DECISION
- Status: OPEN / RECOMMENDED — 2026-08-21
- Recommended choice: Use BEA annual 2024, 71-summary-category,
  after-redefinitions Direct Requirements (`CxIDRAR` interactive product token)
  as the future direct-topology source for a bounded energy
  supply/refining/utilities/transport proof. Use Industry-by-Commodity Total
  Requirements (`IxCTRAR`) only as a non-recursive benchmark/validation control.
- Companion evidence: EIA weekly petroleum stocks/refinery utilization and
  natural-gas storage, plus BLS CES `CES1021100001` for current NAICS 211
  employment exposure.
- Approval dependencies: provision a BEA API key outside the repository; resolve
  current API integer table IDs from live metadata; close or explicitly deny
  UNKNOWN retention/derived-publication/redistribution rights; validate the
  current BEA-to-BLS NAICS crosswalk; choose the final 484/486 downstream node.
- Boundary: Approval of this decision would select the source/slice design. It
  would not by itself authorize production retrieval, parsing, accepted
  relationship generation, propagation, public activation, Gate-B closure,
  Phase 5, UI work, push, merge, or deployment.
