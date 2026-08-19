# Master Specification Index — V4.1

This is a routing map, not a substitute specification. Retrieve the listed sections from `MASTER_SPEC.md`; do not infer requirements from this index alone.

## Approved Foundation decision routing

| Decision | Accepted baseline | Governing records |
|---|---|---|
| D-007 | Repository-root `systems-monitor/` owns Systems Monitor documentation and future isolated product source/configuration/tests; the Jekyll-served surface remains under `auxsays/systems-monitor/` | `DECISIONS.md`; Repository Integration and Architecture contracts |
| D-008 | `/systems-monitor/` is the durable pathname with validated/canonical query-parameter application state unless a future approved amendment changes it | `DECISIONS.md`; Repository Integration RI-004 |

## Post-V4.1 Taylor review requirements — pending Master consolidation

These requirements were established during final Foundation review after V4.1. They are authoritative as recorded decisions but are not represented as existing V4.1 text; do not cite `MASTER_SPEC.md` as their source.

| Decision | Post-V4.1 requirement | Current authoritative records |
|---|---|---|
| D-009 | Four-hour maximum MVP base system-evaluation heartbeat plus source-specific cadence, known-release-aware checks, material-change triggers, affected-state recomputation, and cadence-relative freshness | `DECISIONS.md`; BINDING Infrastructure and Public Data Interface contracts |
| D-010 | Compute-once/read-many and measured, bounded recurring infrastructure/API cost governance | `DECISIONS.md`; BINDING Infrastructure contract |

## Phase-2 design artifact routing

| Design concern | Phase-2 artifact | Master / binding context |
|---|---|---|
| Application/view/navigation contract | `contracts/UI_UX_CONTRACT.md` | §2–3, §38–59, §63, §69; Product and Repository Integration contracts |
| Motion and interaction grammar | `contracts/MOTION_INTERACTION_CONTRACT.md` | §46–52, §56–58, §69; Product and Release Acceptance contracts |
| Component and data/view-model boundaries | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §1 | §37.1, §59–60; Architecture and Public Data Interface contracts |
| Canonical query-state routing | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §2 | §38.1, §52; D-008 and Repository Integration RI-004 |
| Contract-valid synthetic fixture | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §3 | §3, §37.1, §55; Public Data Interface contract |
| Tokens, responsive, accessibility | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §§4–5 | §40–42, §46–50, §56–57, §69 |
| O-001A/B/C/D and O-002 | `DECISIONS.md`; `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §§6–10 | §38.1–38.2, §58–60, §67 Phase 2 |
| Performance and tests | `PHASE2_UI_IMPLEMENTATION_DESIGN.md` §§11–12 | §58, §61, §63; Release Acceptance contract |

## Phase-3 Data Integrity BINDING routing

| Design concern | Phase-3 authoritative artifact | Master / binding context |
|---|---|---|
| Canonical observations, revisions, bitemporal reads, and publication | `contracts/DATA_CONTRACT.md` | §31–32, §35–37.1; Architecture, Infrastructure, Public Data Interface, Security Ingestion |
| Source priority, registry, health, cadence, and collection boundary | `contracts/SOURCE_CONTRACT.md` | §27–31, §34.1–36; D-009/D-010 |
| Versioned semantics and source-to-canonical mappings | `contracts/ONTOLOGY_CROSSWALK_CONTRACT.md` | §31.1–31.6, §32, §37 |
| Gate-A test evidence | `contracts/TESTING_CONTRACT.md` | §61–64.1; Release Acceptance and Security Ingestion |
| Source inventory and bounded indicator registry | `PHASE3_DATA_INTEGRITY_DESIGN.md` §§1–2 | §27–30, §65, §67 Phase 3 |
| Storage, rights, atomicity, and idempotency | `PHASE3_DATA_INTEGRITY_DESIGN.md` §§3–7 | §31–32, §35.3–35.5, §68 |
| Exact first vertical slice and test matrix | `PHASE3_DATA_INTEGRITY_DESIGN.md` §§8–10 | §61, §64.1, §65, §67 Phase 3 |
| Resolved Phase-3 scope/rights decisions | `DECISIONS.md` O-003/O-004 | §27, §31, §64.4–64.8 |
| Publicly-available vs operationally-known replay | Data DAT-003; Ontology ONT-004/014; Testing TST-005; design §4 | §31–31.2, §61, §68 |
| Current-rights withdrawal and governed deletion | Data DAT-013/019/020; Testing TST-008/012; design §§6–7 | §31.6, §35.4–35.5, §61 |
| First-slice source boundary and FRED/ALFRED prohibition | Source SRC-001/018/019; `DECISIONS.md` O-003/O-004; design §§1, 8 | §27–31 plus Taylor project decisions |

## Product and public experience

| Concept | Authoritative V4.1 sections |
|---|---|
| Product definition and non-dashboard purpose | §0 |
| V4/V4.1 architectural and governance upgrades | §0.1, §72 |
| AUXSAYS/Patch Feed/Systems Monitor boundary and public route | §0.2 |
| Infrastructure decision boundary and cloud deferral | §0.3 |
| User questions / product outcomes | §1, §70–71 |
| Summary / Verified Data / Outlook | §2–2.3 |
| OBS / CALC / FCST / SCEN | §3 |
| Ten employment driver systems | §4–4.10 |
| Employment outcomes | §5 |
| Progressive Top 10 navigation | §38 |
| Shared application shell | §39 |
| Search and exploration | §53 |
| UX writing | §64 |
| Non-negotiable UX/UI rules | §69 |

## Data, sources, time, and semantics

| Concept | Authoritative V4.1 sections |
|---|---|
| Authoritative source tiers | §27 |
| Source Registry | §28 |
| Source health and freshness | §29–30 |
| Vintages and revisions | §31 |
| Bitemporal valid/knowledge time | §31.1 |
| Mixed-frequency as-of state | §31.2 |
| Taxonomy / ontology / crosswalks | §31.3 |
| Company/facility entity resolution | §31.4 |
| Geographic semantics | §31.5 |
| Machine-enforced data rights | §31.6 |
| Universal observation schema | §32 |
| Configuration over hardcoding | §37 |
| Public Data Interface / view-model | §37.1 |

## Analytical and model systems

| Concept | Authoritative V4.1 sections |
|---|---|
| Physical-economy inputs | §6 |
| Supply-use / input-output backbone | §6.1 |
| External shocks | §7 |
| Analytical engine sequence | §8 |
| Informative / State Engine | §9 |
| Dependency edge semantics | §10 |
| Pressure propagation | §11 |
| Probabilistic propagation and typed uncertainty | §11.1 |
| Lagged feedback | §11.2 |
| Common-cause / double counting | §11.3 |
| Hidden dependencies | §11.4–11.10 |
| Hidden-dependency criticality | §11.5 |
| Time to Survive / Time to Recover | §11.6 |
| Multi-tier suppliers/facilities | §11.7 |
| Reverse dependency / failure-mode discovery | §11.8 |
| Candidate dependency promotion | §11.9, §20 |
| Converging / contradictory evidence | §12 |
| Market allocation / demand-share movement | §13–13.1 |
| Supply response and adaptation | §14 |
| Forecasting and ensembles | §15–16 |
| Forecast object contracts | §16.1 |
| Naive baseline competition | §16.2 |
| Forecast revision attribution | §16.3 |
| Scenarios and probability-aware events | §17–18 |
| Calibration / model registry / regime change | §19–19.2 |
| Established methodology adoption | §20.1 |
| Historical backtesting | §21 |
| Human capital | §22–26.3 |
| Event intelligence | §33 |
| Public-official positioning signal (experimental/non-blocking) | §33.1 |

## Security and operational integrity

| Concept | Authoritative V4.1 sections |
|---|---|
| Core AI independence | §34 |
| External content zero instruction authority | §34.1 |
| Least-privilege LLM/document extraction | §34.2 |
| Hashing, caching, AI budgets | §34.3 |
| Bounded discovery | §34.4 |
| SSRF/network safety | §34.5 |
| Hostile documents/archives | §34.6 |
| Path traversal | §34.7 |
| XSS/rendering safety | §34.8 |
| SQL/config-expression injection | §34.9 |
| Spreadsheet formula injection | §34.10 |
| GitHub/repository security | §34.11 |
| Public-data security boundary | §35.3 |
| Atomic public snapshot publishing | §35.4 |
| Idempotency, retries, concurrency | §35.5 |
| Monitor observability | §62 |

## Architecture, repository, UI, and delivery

| Concept | Authoritative V4.1 sections |
|---|---|
| Backend pipeline | §35 |
| Presentation/compute/storage separation | §35.1 |
| Provider-neutral infrastructure | §35.2 |
| Collector separation rule | §36 |
| GitHub Pages/Jekyll routing | §38.1 |
| Windows/Linux compatibility | §38.2 |
| Visual direction / color / typography | §40–42 |
| View layouts | §43–45 |
| Charts / hover / focus / motion / transitions | §46–50 |
| Focused Trace Mode and breadcrumbs | §51–52 |
| Ranking stability / comprehension testing | §52.1–52.2 |
| Source health / evidence UX | §54–55.2 |
| Responsive / accessibility / performance | §56–58 |
| Suggested React architecture | §59 |
| Suggested repository shape | §60 |
| Tests | §61 |
| Error/degraded states | §63 |

## Governance, phases, and gates

| Concept | Authoritative V4.1 sections |
|---|---|
| Capability gates A–E | §64.1 |
| Contract-governed framework | §64.2 |
| Authority chain and conflicts | §64.3 |
| Contract statuses / Taylor approval | §64.4 |
| Lean contract structure / profiles | §64.5 |
| Contract inventory | §64.6 |
| Just-in-time contract creation | §64.7 |
| Contract amendment | §64.8 |
| Agent working-context protocol | §64.9 |
| Decisions, risks, roadmap, changelog | §64.10 |
| Contract references in artifacts | §64.11 |
| Governance success | §64.12 |
| Initial vertical slice | §65 |
| Required phases 0–7 | §66 |
| Engineering Deliverable Registry | §67 |
| Non-negotiable methodology rules | §68 |

## Phase routing

| Phase | Read first | Do not start before |
|---|---|---|
| 1 Foundation | §0.2–0.3, §34.1–35.5, §37.1, §38.1–38.2, §64.1–64.12, §66–68 | Current task authorization |
| 2 UI Shell | §2, §38–59, §67 Phase 2, §69 | PASS for implementation authority — Foundation and UI/Motion contracts BINDING; O-001C/O-001D Taylor-approved; use a scoped implementation task |
| 3 Data Integrity | §27–32, §34–37.1, §61, §67 Phase 3; four BINDING Phase-3 contracts | CLOSED — Gate A and Human Data QA Round 2 PASS; factual public activation remains separate and unauthorized |
| 4 State/Dependency/Allocation | §6–14, §20–20.1, §67 Phase 4 | Drafting only: five Phase-4 contracts and design require Taylor review/promotion before implementation |
| 5 Forecasting | §15–21, §55.1–55.2, §67 Phase 5 | Forecast/Scenario/Calibration contracts approved and prior gates passed |
| 6 Human Capital/Events | §22–26.3, §33–33.1, §67 Phase 6 | Subsystem contracts approved |
| 7 Launch Hardening | §52.1–64.1, §67 Phase 7, §70 | Applicable gates and release contract passed |

## Phase-4 DRAFT routing

| Review question | DRAFT authority / design |
|---|---|
| Current/as-of State, mixed-frequency evidence, reference and replay | `contracts/STATE_MODEL_CONTRACT.md` |
| Relationship identity, evidence, lifecycle, criticality, hidden/common cause | `contracts/DEPENDENCY_RELATIONSHIP_CONTRACT.md` |
| Bounded propagation, cycles, materiality, substitution, allocation | `contracts/ALLOCATION_PROPAGATION_CONTRACT.md` |
| OBS/CALC derivation, reproduction, bounded explanation/public boundary | `contracts/DERIVATION_TRANSPARENCY_CONTRACT.md` |
| Gate-B semantic evidence and human review | `contracts/PHASE4_TESTING_CONTRACT.md` |
| Integrated architecture, proof slice, source expansion, risks | `PHASE4_STATE_DEPENDENCY_ALLOCATION_DESIGN.md` |

Current authorization is **Phase 4 — State / Dependency / Allocation contract
and design drafting only**. Phase 3 is CLOSED with Gate A and Human Data QA
Round 2 PASS, but factual public activation was not performed. Taylor must review
and promote the five DRAFT contracts before implementation. New ingestion,
dependencies, calculated Phase-4 output, major UI work, forecasting, push, merge,
and deployment remain unauthorized.
