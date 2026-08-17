# Systems Monitor Roadmap and Deliverable Registry

Status reflects both artifacts and authority. Taylor approved all seven Foundation contracts as `BINDING` after final external review.

## Current phase

Phase 2 — Contract / Design Drafting only. Creation and review of Phase-2 contracts/design decisions are authorized; React/UI implementation, dependencies, Jekyll/workflow changes, and deployment remain unauthorized until the required Phase-2 contracts are approved.

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

## Phase progression

| Phase | Contract prerequisite | Implementation outcome | Gate |
|---|---|---|---|
| 1 Foundation | Current Master/task | Binding governance and boundaries | PASS — Taylor-approved after external review |
| 2 UI Shell | Foundation contracts BINDING; UI/Motion contracts must be approved before implementation | Current authorization is contract/design drafting; later isolated three-view shell uses contract-valid, clearly labeled fixtures | UI architecture/accessibility/routing checks |
| 3 Data Integrity | Data/Source/Ontology contracts approved | Authoritative ingestion, bitemporal storage, source health, publishable snapshots | Gate A |
| 4 Closed Vertical Slice | State/Dependency/Hidden Dependency/Allocation contracts approved | Observation-to-industry-effect proof | Gate B |
| 5 Forecasting/Accountability | Forecast/Scenario/Calibration contracts approved | Baselines, forecasts, uncertainty, replay, attribution | Gate C |
| 6 Human Capital/Events | Subsystem contracts approved | Three occupation proof cases and bounded event/experimental work | Gate D |
| 7 Launch Hardening | Release contract and all applicable contracts approved | Evidence inspectors, scorecard, rights/security/accessibility/performance/operations | Gate E |

## Next authorized work

Draft and review the Phase-2 `UI_UX_CONTRACT.md`, `MOTION_INTERACTION_CONTRACT.md`, and other Master-required design/decision artifacts. O-001A through O-001D and O-002 remain open under their recorded authority classifications. **Do not implement the UI, install dependencies, or modify Jekyll/Pages integration until the required Phase-2 contracts and decisions are approved.**
