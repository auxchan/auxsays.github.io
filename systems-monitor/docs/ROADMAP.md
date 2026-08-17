# Systems Monitor Roadmap and Deliverable Registry

Status reflects both artifacts and authority. Taylor approved all seven Foundation contracts as `BINDING` after final external review.

## Current phase

Phase 2 — UI Shell Implementation. Taylor approved the BINDING UI/UX and Motion/Interaction contracts and O-001C/O-001D architecture on 2026-08-17. A subsequent scoped task may implement the contract-valid synthetic UI shell and approved minimal Jekyll/Pages integration after exact-version dependency verification. This approval task itself stops before implementation; deployment and Phase-3 ingestion/data/model work remain unauthorized.

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
| P2-003 | Component/module architecture | UI/UX contract | Application structure | Design complete | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §1 | Proportional V1 boundary proposed |
| P2-004 | Canonical query-state routing | D-008; UI/UX contract | Router/state implementation | Design complete | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §2 | Direct/refresh/history rules defined |
| P2-005 | Public fixture design | Public Data Interface; UI/UX contract | Fixture implementation | Design complete | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §3 | No schema amendment identified |
| P2-006 | Tokens/responsive/accessibility | UI/UX and Motion contracts | Presentation implementation | Design complete | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §§4–5 | Isolation and proof plan defined |
| P2-007 | Package location | D-007 | App package creation | RESOLVED design choice | `DECISIONS.md` O-001A | `systems-monitor/app/`; not created |
| P2-008 | Package manager/lockfile | Repository conventions | Dependency installation | RESOLVED design choice | `DECISIONS.md` O-001B | npm/package-local lockfile; not created |
| P2-009 | Build-output ownership | Taylor O-001C | Build/Jekyll composition | ACCEPTED / RESOLVED | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §8 | Taylor-approved architecture; not implemented |
| P2-010 | Pages integration | Taylor O-001D | Workflow modification | ACCEPTED / RESOLVED | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §9 | Taylor-approved architecture; not implemented |
| P2-011 | Chart library | UI accessibility/performance proof | Chart implementation | RESOLVED design choice | `DECISIONS.md` O-002; design §10 | Recharts; exact-version proof required before install |
| P2-012 | Performance and test plan | Phase-2 contracts | Acceptance implementation | Design complete | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §§11–12 | No tests/code created |

## Phase progression

| Phase | Contract prerequisite | Implementation outcome | Gate |
|---|---|---|---|
| 1 Foundation | Current Master/task | Binding governance and boundaries | PASS — Taylor-approved after external review |
| 2 UI Shell | Foundation and UI/Motion contracts BINDING; O-001C/O-001D approved | Current authorization is a subsequent scoped isolated three-view shell using contract-valid, unmistakable fixtures | UI architecture/accessibility/routing/comprehension checks |
| 3 Data Integrity | Data/Source/Ontology contracts approved | Authoritative ingestion, bitemporal storage, source health, publishable snapshots | Gate A |
| 4 Closed Vertical Slice | State/Dependency/Hidden Dependency/Allocation contracts approved | Observation-to-industry-effect proof | Gate B |
| 5 Forecasting/Accountability | Forecast/Scenario/Calibration contracts approved | Baselines, forecasts, uncertainty, replay, attribution | Gate C |
| 6 Human Capital/Events | Subsystem contracts approved | Three occupation proof cases and bounded event/experimental work | Gate D |
| 7 Launch Hardening | Release contract and all applicable contracts approved | Evidence inspectors, scorecard, rights/security/accessibility/performance/operations | Gate E |

## Next authorized work

Begin a subsequent scoped Phase-2 UI-shell implementation task under the BINDING contracts and accepted decisions. Before installation, verify exact dependency versions; then implement only the isolated synthetic shell, D-008 routing, scoped styling/accessibility/responsive behavior, Recharts/Trace boundaries, approved minimal Jekyll/Pages integration, and Phase-2 tests. **Do not begin Phase-3 ingestion/data/model work, factual forecasts, deployment, or any implementation within this approval/commit task.**
