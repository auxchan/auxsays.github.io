# Systems Monitor Roadmap and Deliverable Registry

Status reflects both artifacts and authority. Taylor approved all seven Foundation contracts as `BINDING` after final external review.

## Current phase

Phase 2 — UI Shell Implementation. The authorized technical shell, synthetic fixture, tests, and minimal Jekyll/Pages integration are implemented on `codex/systems-monitor-ui-shell`. Automated/local technical validation passes; Taylor human UI/comprehension review remains PENDING. Deployment and Phase-3 ingestion/data/model work remain unauthorized.

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
| P2-006 | Tokens/responsive/accessibility | UI/UX and Motion contracts | Presentation implementation | Technical proof complete | `systems-monitor/app/src/styles.css` | Isolation/tests/browser proof pass; human QA pending |
| P2-007 | Package location | D-007 | App package creation | Implemented | `systems-monitor/app/` | Isolated package exists |
| P2-008 | Package manager/lockfile | Repository conventions | Dependency installation | Implemented | `systems-monitor/app/package-lock.json` | Exact npm lock committed locally |
| P2-009 | Build-output ownership | Taylor O-001C | Build/Jekyll composition | Implemented | `systems-monitor/app/scripts/` | Safe clean, hashed manifest/output equality, ignored composition pass |
| P2-010 | Pages integration | Taylor O-001D | Workflow modification | Implemented locally | `.github/workflows/pages.yml` | Single-job order retained; hosted run awaits future push |
| P2-011 | Chart library | UI accessibility/performance proof | Chart implementation | Implemented | `DEPENDENCY_VERIFICATION.md` | Recharts 3.10.1 gate passes with HTML/table equivalence |
| P2-012 | Performance and test plan | Phase-2 contracts | Acceptance implementation | Implemented | `systems-monitor/app/tests/` | 28 tests and production measurement pass; human QA pending |

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

Complete Taylor's Phase-2 human visual/comprehension review using `systems-monitor/app/HUMAN_QA_CHECKLIST.md`, then make only resulting Phase-2 corrections if authorized. **Do not begin Phase-3 ingestion/data/model work, factual forecasts, push, merge, or deployment.**
