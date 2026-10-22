# Product and governance

The Systems Monitor is a continuously updated, evidence-first model of U.S. systems—not a chart dashboard, news feed, or AI-prediction veneer. Its claim classes remain separate: OBS, CALC, FCST, and SCEN.

Authority order:

1. `../MASTER_SPEC.md` V4.1, SHA-256 `08895B471909DC600FC6AA5F373E2D6E16F457580A9BA141363ED210676397EA`.
2. Taylor-approved decisions in `../DECISIONS.md` and BINDING contracts.
3. `../CONTRACT_INDEX.yaml`, the governing contract registry.
4. Approved profiles and implementation designs that do not conflict with higher authority.

The registry contains 18 contract entries and all 18 are BINDING. UI/UX and Repository Integration are 1.0.1; the other active contracts are 1.0.0. D-009 and D-010 are separate indexed decisions, not contracts. Registry `content_hash` values are governance hashes, not raw whole-file SHA-256 values. `MASTER_INDEX.md` is a routing map, not a substitute specification.

Current gates: Phase 3 CLOSED / Gate A PASS / Human Data QA PASS. Phase 4A is a completed `LIMITED_ENGINE_PROOF`. Gate B remains `OPEN_REQUIRES_PHASE_4B_AUTHORITATIVE_STRUCTURAL_PROOF`. Phase 5, public activation, merge, and deployment remain unauthorized.

Non-negotiable invariants: no fixture leakage; visibly sparse coverage; exact-ten hierarchy without filler; hierarchy tethers cannot create evidence or causality; accepted versioned edges alone can propagate; direct and total requirements cannot be double-counted; valid-time and knowledge-time remain distinct; source health cannot be presented as economic state; missing evidence is not neutral.
