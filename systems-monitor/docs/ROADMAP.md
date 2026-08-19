# Systems Monitor Roadmap and Deliverable Registry

Status reflects both artifacts and authority. Taylor approved all seven Foundation contracts as `BINDING` after final external review.

## Current phase

Phase 4A — Engine / Labor-State Proof implementation only. Phase 3 Data
Integrity is CLOSED with Human Data QA Round 2 PASS and Gate A PASS. Gate B
remains OPEN. Phase-4B, new-source ingestion, factual public activation,
forecasting, deployment, and the deferred UI overhaul remain unauthorized.

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
| P3-013 | Correct factual publication boundary | Public Data Interface / Architecture contracts | Taylor Gate-A review | Complete — Gate A PASS | `data/review/GATE_A_EVIDENCE.md` | Internal model, pre-activation candidate, and active PDI are distinct; `childRefs[]` transport enforced |
| P3-014 | Human Data QA evidence surface | Taylor Gate-A human review | Phase-3 closure | PASS | `data/review/HUMAN_DATA_QA.md` | Taylor approved exact series/evidence, factual Outlook isolation, and DOL replay proof |

## Phase-4 design deliverables

| ID | Name | Required authority | Blocks what | Status | Artifact / path | Review result |
|---|---|---|---|---|---|---|
| P4-001 | State Model contract | Taylor promotion | State implementation | BINDING 1.0.0 | `contracts/STATE_MODEL_CONTRACT.md` | Taylor-approved 2026-08-19 |
| P4-002 | Dependency Relationship contract | Taylor promotion | Relationship graph implementation | BINDING 1.0.0 | `contracts/DEPENDENCY_RELATIONSHIP_CONTRACT.md` | Taylor-approved 2026-08-19 |
| P4-003 | Allocation/Propagation contract | Taylor promotion | Propagation/allocation implementation | BINDING 1.0.0 | `contracts/ALLOCATION_PROPAGATION_CONTRACT.md` | Taylor-approved 2026-08-19 |
| P4-004 | Derivation Transparency contract | Taylor promotion | CALC/public derivation implementation | BINDING 1.0.0 | `contracts/DERIVATION_TRANSPARENCY_CONTRACT.md` | Taylor-approved 2026-08-19 |
| P4-005 | Phase-4 Testing contract | Taylor promotion | Gate-B implementation/evidence | BINDING 1.0.0 | `contracts/PHASE4_TESTING_CONTRACT.md` | Taylor-approved 2026-08-19; Gate B OPEN |
| P4-006 | Integrated implementation design | Five promoted contracts plus scoped authorization | Phase-4 engineering | Approved 0.1.1 design | `PHASE4_STATE_DEPENDENCY_ALLOCATION_DESIGN.md` | Phase-4A authorized; Phase-4B locked |
| P4-007 | Phase-4A current/as-of labor engine proof | State Model; O-006 accepted profile; scoped authorization | Engine proof, not Gate B | Implemented / Human QA pending | `data/src/systems_monitor_data/`; `state/review/` | 170 Python + 76 UI tests pass; LIMITED_ENGINE_PROOF; cannot pass Gate B |
| P4-008 | Phase-4B authoritative structural relationship proof | Five contract promotions; bounded source/slice approval | Gate B | Required design only | Design §§6, 13–15 | Original-authority BEA structural subset required; no ingestion |
| P4-009 | Bounded propagation/common-cause behavior | Allocation/Propagation promotion; Phase-4B evidence | Gate B | Designed only | Design §§7–8, 13 | Real accepted lag/buffer/substitution/common-cause proof required |
| P4-010 | Allocation/employment boundary | Allocation/Propagation; O-006 | Allocation proof | Mechanics implemented only | `data/src/systems_monitor_data/allocation.py` | Synthetic conservation proof; no real employment model or forecast |
| P4-011 | Derivation/master-view read model | Derivation; O-006 | Explainable public candidate | Phase-4A candidate implemented | `state/review/phase4a-read-model-candidate.json` | Public-safe limited proof; UI overhaul deferred |
| P4-012 | Gate-B evidence matrix | Testing; authorized Phase-4A and 4B implementation | Gate B | Phase-4A technical PASS / Human QA pending / Gate B OPEN | `state/review/PHASE4A_EVIDENCE.md` | Phase-4B authoritative backbone + remaining criteria + Human QA/Taylor approval required |
| P4-013 | Direct/total requirements role and double-count proof | Dependency/Testing promotion; Phase-4B source approval | Gate B | Required design only | Design §6.3; contracts DR-027–029 | Total requirements cannot recursively duplicate direct topology |
| P4-014 | Structural coverage/read-model honesty | State/Derivation/Testing promotion | Gate B/public-read candidate | Required design only | Design §11 | Sparse graph cannot imply economy-wide coverage |

## Phase progression

| Phase | Contract prerequisite | Implementation outcome | Gate |
|---|---|---|---|
| 1 Foundation | Current Master/task | Binding governance and boundaries | PASS — Taylor-approved after external review |
| 2 UI Shell | Foundation and UI/Motion contracts BINDING; O-001C/O-001D approved | Isolated three-view shell using contract-valid, unmistakable fixtures | PASS for MVP — technical PASS and Taylor Human UI QA PASS; polish deferred |
| 3 Data Integrity | Data/Source/Ontology/Testing contracts BINDING | Six-indicator BLS/DOL implementation with provenance, dual replay, health, revision proof, and validated factual candidate; no public activation | PASS — Gate A and Human Data QA Round 2 |
| 4 Closed Vertical Slice | Five Phase-4 contracts promoted by Taylor plus separately scoped Phase-4A and Phase-4B implementation authority | Phase-4A labor engine mechanics plus Phase-4B original-authority structural I/O, real behavioral propagation, allocation/current employment exposure, derivation, and coverage proof | Gate B — OPEN / Phase 4A alone insufficient |
| 5 Forecasting/Accountability | Forecast/Scenario/Calibration contracts approved | Baselines, forecasts, uncertainty, replay, attribution | Gate C |
| 6 Human Capital/Events | Subsystem contracts approved | Three occupation proof cases and bounded event/experimental work | Gate D |
| 7 Launch Hardening | Release contract and all applicable contracts approved | Evidence inspectors, scorecard, rights/security/accessibility/performance/operations | Gate E |

## Next authorized work

Implement only the deterministic Phase-4A Engine / Labor-State Proof using the
six accepted Phase-3 labor observations and O-006's configurable depth-3,
eight-round profile. Produce technical and `HUMAN_PHASE4A_QA = PENDING` evidence.

Do not ingest any new source, retrieve/ingest BEA, implement Phase-4B, claim Gate
B, activate factual data publicly, redesign the UI, forecast, install
dependencies, choose cloud/paid services, push, merge, or deploy. O-007 remains
an engineering choice constrained to standard-library/local structures. Any
future Phase-4B work requires a bounded structural source-discovery/intake
authorization; Phase 4A cannot close Gate B.

## Phase-3 first-slice implementation checkpoint — 2026-08-18

Implemented locally for technical review: four source registries; eight indicator entries with six enabled; operation-specific rights; bounded secure retrieval; immutable raw capture; normalized temporal versions; SQLite latest/public/known queries; factual DOL revision replay; cadence-aware health and four-hour evaluation semantics; atomic local candidate/withdrawal; deletion tombstones; idempotency/concurrency/telemetry tests; a separate factual candidate; and a local-only factual UI mode.

Taylor approved `HUMAN_DATA_QA ROUND 2 = PASS` and `GATE A = PASS`; Phase 3 is
CLOSED. Factual public activation was not performed and remains unauthorized.

The requested master-system overview and visible interconnectivity are deferred
design inputs, not Phase-3 presentation work. Phase 4 contract/design drafting
must first define governed State, Dependency, and Allocation relationships;
later UI work may then cover relationship navigation, propagation/cascade
inspection, stronger hierarchy, and a comprehensive systems-level overview
using real relationship evidence rather than decorative links.

Future explanation behavior must also make every material claim's derivation
class obvious: source-owned `OBS`, deterministic AUXSAYS `CALC`, future `FCST`,
or conditional `SCEN`. Derived claims must eventually expose bounded inputs,
algorithm/configuration versions, snapshot/cutoff, assumptions, typed evidence,
uncertainty, and trace references. The Phase-4 package designs the enabling data
boundary; it does not authorize the visual overhaul.
