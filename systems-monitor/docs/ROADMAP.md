# Systems Monitor Roadmap and Deliverable Registry

Status reflects both artifacts and authority. Taylor approved all seven Foundation contracts as `BINDING` after final external review.

## Current phase

Phase 3 — Data Integrity implementation, limited to the Taylor-approved six-indicator first slice using BLS CES/CPS/JOLTS and DOL Weekly Claims. All four Phase-3 contracts are BINDING. FRED/ALFRED and CPI/GDP ingestion are not authorized; factual public activation still requires Gate-A/activation approval. Phase-2 deferred polish remains tracked in R-018.

## Phase-1 deliverables

| ID | Name | Required contract | Blocks what | Status | Artifact / path | Acceptance result |
|---|---|---|---|---|---|---|
| F-001 | Repo architecture summary | Repository Integration | Phase 2 repository changes | Complete draft | `REPO_FACTS.md` | Verified at `adae22a` |
| F-002 | Product boundary | Product | All product work | BINDING | `contracts/PRODUCT_CONTRACT.md` | Taylor-approved 2026-08-17 |
| F-003 | Existing-repo integration | Repository Integration | Phase 2 build/routing | BINDING | `contracts/REPOSITORY_INTEGRATION_CONTRACT.md` | D-007/D-008 and contract Taylor-approved 2026-08-17 |
| F-004 | Public route confirmation | Product | Phase 2 routing | Accepted decision | `DECISIONS.md` D-001 | Recorded |
| F-005 | Architecture boundary | Architecture | Phase 2+ module boundaries | BINDING | `contracts/ARCHITECTURE_CONTRACT.md` | Taylor-approved 2026-08-17 |
| F-006 | Provider-neutral, cost-governed infrastructure | Infrastructure | Phase 3+ runtime selection | BINDING | `contracts/INFRASTRUCTURE_CONTRACT.md` | Taylor-approved with D-009/D-010 on 2026-08-17 |
| F-007 | Presentation/public/compute/storage split | Architecture/Infrastructure | Producer/consumer implementation | BINDING | Architecture and Infrastructure contracts | Taylor-approved 2026-08-17 |
| F-008 | Initial public data and freshness interface | Public Data Interface | Phase-2 fixtures | BINDING | `contracts/PUBLIC_DATA_INTERFACE_CONTRACT.md` | Taylor-approved 2026-08-17; implementation awaits Phase-2 contract approval |
| F-009 | Initial security/ingestion boundary | Security Ingestion | Production ingestion | BINDING | `contracts/SECURITY_INGESTION_CONTRACT.md` | Taylor-approved 2026-08-17 |
| F-010 | Contract governance/template | Master §64.2–64.12 | Contract-driven work | Complete draft | `CONTRACT_TEMPLATE.md`, indexes/ledgers | Structure/status consistency passed |
| F-011 | Compact guardrails | Master §64.9 | Routine agent tasks | Complete draft | `PROJECT_GUARDRAILS.md` | Required invariant check passed |
| F-012 | Master routing index | Master §64.9 | Targeted context retrieval | Complete draft | `MASTER_INDEX.md` | Section-routing check passed |
| F-013 | Machine-readable contract index | Master §64.9 | Contract routing | Complete draft | `CONTRACT_INDEX.yaml` | YAML parse/path/dependency checks passed |
| F-014 | Decision ledger | Master §64.10 | Phase decisions | Complete draft | `DECISIONS.md` | Required decisions recorded |
| F-015 | Risk ledger | Master §64.10 | Gate/release review | Complete draft | `RISKS.md` | Priorities recorded |
| F-016 | Phased roadmap | Master §66–67 | Phase control | Complete draft | `ROADMAP.md` | Phase boundaries recorded |
| F-017 | Change ledger | Master §64.8, §64.10 | Auditability | Complete draft | `CHANGELOG.md` | Initial entry recorded |
| F-018 | Initial capability/release contract | Release Acceptance | Phase promotion/release | BINDING | `contracts/RELEASE_ACCEPTANCE_CONTRACT.md` | Taylor-approved 2026-08-17 |
| F-019 | Phase-2 dependency/license review | Repository Integration | Phase-2 dependency approval | Complete candidate review | `PHASE2_DEPENDENCY_LICENSE_REVIEW.md` | Re-audit exact installs required |
| F-020 | Known unknowns | Foundation contracts | Phase-specific decisions | Complete draft | `RISKS.md`, `DECISIONS.md` | O-001A–O-001D and O-002 visible |

## Phase-2 design deliverables

| ID | Name | Required authority | Blocks what | Status | Artifact / path | Review result |
|---|---|---|---|---|---|---|
| P2-001 | UI/UX contract | Taylor contract promotion | UI shell implementation | BINDING 1.0.0 | `contracts/UI_UX_CONTRACT.md` | Taylor-approved 2026-08-17 after external review corrections |
| P2-002 | Motion/Interaction contract | Taylor contract promotion | UI interaction implementation | BINDING 1.0.0 | `contracts/MOTION_INTERACTION_CONTRACT.md` | Taylor-approved 2026-08-17 after external review correction |
| P2-003 | Component/module architecture | UI/UX contract | Application structure | Implemented | `systems-monitor/app/src/` | Proportional shared shell + lazy views/Trace |
| P2-004 | Canonical query-state routing | D-008; UI/UX contract | Router/state implementation | Implemented | `systems-monitor/app/src/state/` | Canonical/direct/history/invalid-path tests pass |
| P2-005 | Public fixture design | Public Data Interface; UI/UX contract | Fixture implementation | Implemented | `systems-monitor/app/src/fixtures/` | Runtime schema and fixture-boundary tests pass |
| P2-006 | Tokens/responsive/accessibility | UI/UX and Motion contracts | Presentation implementation | Complete for MVP | `systems-monitor/app/src/styles.css` | Technical proof and Taylor MVP Human UI QA pass; polish deferred |
| P2-007 | Package location | D-007 | App package creation | Implemented | `systems-monitor/app/` | Isolated package exists |
| P2-008 | Package manager/lockfile | Repository conventions | Dependency installation | Implemented | `systems-monitor/app/package-lock.json` | Exact npm lock committed locally |
| P2-009 | Build-output ownership | Taylor O-001C | Build/Jekyll composition | Implemented | `systems-monitor/app/scripts/` | Safe clean, hashed manifest/output equality, ignored composition pass |
| P2-010 | Pages integration | Taylor O-001D | Workflow modification | Implemented locally | `.github/workflows/pages.yml` | Single-job order retained; hosted run awaits future push |
| P2-011 | Chart library | UI accessibility/performance proof | Chart implementation | Implemented | `DEPENDENCY_VERIFICATION.md` | Recharts 3.10.1 gate passes with HTML/table equivalence |
| P2-012 | Performance and test plan | Phase-2 contracts | Acceptance implementation | Complete for MVP | `systems-monitor/app/tests/` | 29 tests, production measurement, and Taylor MVP Human UI QA pass |

## Phase-3 design deliverables

| ID | Name | Required authority | Blocks what | Status | Artifact / path | Review result |
|---|---|---|---|---|---|---|
| P3-001 | Data contract | Taylor contract promotion | Data/storage implementation | BINDING 1.0.0 | `contracts/DATA_CONTRACT.md` | Taylor-approved 2026-08-17 after external-review corrections |
| P3-002 | Source contract | Taylor contract promotion | Collector/source-health implementation | BINDING 1.0.0 | `contracts/SOURCE_CONTRACT.md` | Taylor-approved 2026-08-17; FRED/ALFRED prohibited |
| P3-003 | Ontology/Crosswalk contract | Taylor contract promotion | Canonical mapping implementation | BINDING 1.0.0 | `contracts/ONTOLOGY_CROSSWALK_CONTRACT.md` | Taylor-approved 2026-08-17 |
| P3-004 | Testing contract | Taylor contract promotion | Phase-3 test implementation / Gate A evidence | BINDING 1.0.0 | `contracts/TESTING_CONTRACT.md` | Taylor-approved 2026-08-17; DOL revision proof required |
| P3-005 | Source inventory | Source contract; O-003/O-004 | Source enablement | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §§1, 10 | First slice BLS/DOL only; CPI/BEA follow-on; FRED/ALFRED unauthorized |
| P3-006 | Indicator registry | Data/Source contracts; O-003 | Normalization scope | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §2 | Eight accepted; six enabled in first slice |
| P3-007 | Storage/bitemporal design | Data contract | Storage implementation | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §§3–4 | Dual replay semantics; logical/provider-neutral only |
| P3-008 | Crosswalk architecture | Ontology/Crosswalk contract | Canonical mappings | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §5 | Initial scope limited to slice semantics |
| P3-009 | Rights enforcement plan | Data/Source/Security contracts | Factual publication | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §6 | Independent rights, revocation/withdrawal, deletion/tombstone |
| P3-010 | Atomic/idempotent publication design | Data/Infrastructure contracts | Factual activation | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §7 | Candidate failure vs current-rights withdrawal; atomic pointer |
| P3-011 | Exact vertical slice | All four Phase-3 contracts; O-003/O-004 | Gate A | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §8 | Six labor indicators; Tier-A DOL revision proof |
| P3-012 | Test plan | Testing contract | Gate A evidence | Approved design | `PHASE3_DATA_INTEGRITY_DESIGN.md` §9 | Deterministic matrix; no dependencies installed |
| P3-013 | Correct factual PDI export boundary | Public Data Interface / Architecture contracts | Taylor Gate-A review | Implemented; review pending | `data/review/GATE_A_EVIDENCE.md` | Prior internal-shaped false PASS corrected; PDI candidate and regression evidence complete |

## Phase progression

| Phase | Contract prerequisite | Implementation outcome | Gate |
|---|---|---|---|
| 1 Foundation | Current Master/task | Binding governance and boundaries | PASS — Taylor-approved after external review |
| 2 UI Shell | Foundation and UI/Motion contracts BINDING; O-001C/O-001D approved | Isolated three-view shell using contract-valid, unmistakable fixtures | PASS for MVP — technical PASS and Taylor Human UI QA PASS; polish deferred |
| 3 Data Integrity | Data/Source/Ontology/Testing contracts BINDING | Six-indicator BLS/DOL implementation may provide registry, retrieval, bitemporal storage, health, DOL revision proof, and factual candidate; no public activation before later approval | Gate A |
| 4 Closed Vertical Slice | State/Dependency/Hidden Dependency/Allocation contracts approved | Observation-to-industry-effect proof | Gate B |
| 5 Forecasting/Accountability | Forecast/Scenario/Calibration contracts approved | Baselines, forecasts, uncertainty, replay, attribution | Gate C |
| 6 Human Capital/Events | Subsystem contracts approved | Three occupation proof cases and bounded event/experimental work | Gate D |
| 7 Launch Hardening | Release contract and all applicable contracts approved | Evidence inspectors, scorecard, rights/security/accessibility/performance/operations | Gate E |

## Next authorized work

Implement only the approved Phase-3 six-indicator BLS CES/CPS/JOLTS and DOL Weekly Claims slice under the four BINDING contracts. Current endpoint/rights/limits discovery, bounded retrieval, local raw/Parquet/DuckDB-or-equivalent evaluation, normalization, dual replay, source health, DOL revision proof, idempotency, factual candidate, and deterministic tests are authorized. **Do not use FRED/ALFRED, ingest CPI/GDP, activate factual data publicly, begin forecasts/Phase 4, choose cloud, buy an API, push, merge, or deploy without later authorization.**

## Phase-3 first-slice implementation checkpoint — 2026-08-18

Implemented locally for technical review: four source registries; eight indicator entries with six enabled; operation-specific rights; bounded secure retrieval; immutable raw capture; normalized temporal versions; SQLite latest/public/known queries; factual DOL revision replay; cadence-aware health and four-hour evaluation semantics; atomic local candidate/withdrawal; deletion tombstones; idempotency/concurrency/telemetry tests; a separate factual candidate; and a local-only factual UI mode.

Remaining Gate-A/Phase-3 closure work: technical evidence review, Taylor factual-data QA (`PENDING`), Gate-A readiness review, and any correction pass. Factual public activation and Phase 4 remain unauthorized.
