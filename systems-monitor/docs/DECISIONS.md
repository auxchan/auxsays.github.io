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

## Open decisions

### O-001A — React application/package location

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: OPEN — engineering must resolve this within the approved repository boundary before Phase-2 implementation
- Rationale: The exact package location is an ordinary implementation choice when it stays within the approved product and repository boundaries and does not alter public behavior or deployment authority.

### O-001B — Package-manager and lockfile strategy

- Classification: ENGINEERING IMPLEMENTATION CHOICE
- Status: OPEN — engineering must resolve this before adding Phase-2 dependencies
- Rationale: Selecting a package manager and committed lockfile is an implementation choice governed by repository conventions, reproducibility, and CI compatibility.

### O-001C — Build-output ownership/location

- Classification: TAYLOR APPROVAL DECISION
- Status: OPEN — Taylor approval is required before build-output integration
- Rationale: Whether build output is committed or CI-generated, and where it is published, materially affects repository ownership and the Jekyll publication boundary.

### O-001D — GitHub Pages workflow integration

- Classification: TAYLOR APPROVAL DECISION
- Status: OPEN — Taylor approval is required before modifying the Pages workflow
- Rationale: Workflow integration changes deployment behavior and repository automation; Phase 1 authorizes neither a workflow change nor a production-site change.

### O-002 — Phase-2 chart candidate

- Status: OPEN — required before chart implementation, not before Phase-2 contract drafting
- Decision needed: Select a chart library only after an accessibility, interaction, bundle-size, maintenance, and license proof.
