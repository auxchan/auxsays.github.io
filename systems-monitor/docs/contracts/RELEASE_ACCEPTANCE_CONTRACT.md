# Release and Capability-Gate Contract

```text
Contract: Systems Monitor Release and Capability-Gate Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: PRODUCT_CONTRACT.md, REPOSITORY_INTEGRATION_CONTRACT.md, ARCHITECTURE_CONTRACT.md, INFRASTRUCTURE_CONTRACT.md, PUBLIC_DATA_INTERFACE_CONTRACT.md, SECURITY_INGESTION_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 5461536537AF5E8376B55023EED2ECA93792B11876E639B0681C35175C039C6D
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §61–64.1, §64.2–64.12, §66–70. This BINDING contract is current capability-gate and release authority. Phase-1 approval authorizes Phase-2 contract/design drafting only; it does not authorize UI implementation, public release, or deployment.

## Purpose

Define phase promotion and public-claim readiness so documentation, visual completeness, or passing narrow tests cannot bypass contracts and capability gates.

## Scope

- Phase-1 acceptance.
- Contract approval dependency.
- Future Gates A–E and safe release/degraded behavior.
- Evidence required to begin Phase 2 and to prevent premature public claims.

## Explicitly Out of Scope

- Executing Phase-2+ tests, accepting later gates, deploying, or launching.
- Replacing future detailed Testing/UI/Data/Model contracts.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT RA-001:** Engineering agents may report evidence but may not self-promote contracts or declare a phase approved; Taylor approval is required.
- **BINDING REQUIREMENT RA-002:** Phase promotion requires applicable contracts approved plus objective acceptance evidence; a polished frontend is not gate evidence for data/model readiness.
- **BINDING REQUIREMENT RA-003:** Test failures are reported and corrected within contract; tests/criteria are not weakened merely to pass.
- **BINDING REQUIREMENT RA-004:** Fixture/illustrative data cannot be released as factual claims. Phase-2 fixture surfaces must remain unmistakably non-production.
- **BINDING REQUIREMENT RA-005:** No public predictive ranking is production-ready before Gate C and applicable human-capital/public-product gates pass.
- **BINDING REQUIREMENT RA-006:** A release candidate cannot modify or expose Patch Feed generated/state/transient files unintentionally.
- **BINDING REQUIREMENT RA-007:** Direct route/refresh/back/forward/invalid-query/404 behavior is release-blocking for supported Systems Monitor states.
- **BINDING REQUIREMENT RA-008:** Security, rights, schema, snapshot integrity, accessibility, and provenance failures fail closed and preserve the last valid public state.

## Capability gates

- **Gate A — Data Integrity:** authoritative ingestion, source health, vintages, bitemporal queries, taxonomy crosswalks, reproducible snapshots.
- **Gate B — Structural Modeling:** authoritative I/O backbone, validated relationships, lag/buffer/substitution behavior, common-cause reconciliation.
- **Gate C — Forecast Skill:** baseline competition, out-of-sample backtests, prediction intervals, calibration, forecast contracts, revision attribution.
- **Gate D — Human Capital:** industry-to-occupation synthesis, replacement demand, qualified supply, hiring-volume forecasts, rank stability.
- **Gate E — Public Product:** three-view comprehension, source transparency, premium but accessible interaction, mobile, performance, security/operations.

Each gate remains `NOT EVALUATED` until its phase supplies evidence. Partial success must not be reported as pass.

## Phase-1 acceptance criteria

1. Unmodified V4.1 exists at `systems-monitor/docs/MASTER_SPEC.md` and matches source SHA-256 `08895B471909DC600FC6AA5F373E2D6E16F457580A9BA141363ED210676397EA`.
2. Compact guardrails and precise Master index exist.
3. Repository facts are separated into FACT/DECISION/UNKNOWN and anchored to commit `adae22a`.
4. Contract index parses as YAML and records version/status/sections/dependencies/blocks.
5. Seven required Foundation contracts were created and externally reviewed as `DRAFT`; no engineering agent self-approved or promoted them. After Phase-1 review passes, Taylor may promote them, and that authorized promotion does not invalidate the historical Phase-1 acceptance evidence.
6. Product, repository/routing, architecture/infrastructure, public payload, security, and release boundaries are coherent.
7. Decisions D-001 through D-010 are recorded as ACCEPTED; O-001A through O-001D and O-002 remain visible and unresolved under their recorded authority classifications.
8. Phase-2 candidate licenses are reviewed without installing dependencies.
9. No Phase-2+ application/ingestion/model/cloud implementation exists.
10. Existing AUXSAYS/Patch Feed source, generated/state files, workflow behavior, deployment, and `main` remain unchanged.
11. Foundation documentation link/path/YAML/hash/content consistency checks pass.
12. No push, merge, publication, or deployment occurs.

## Phase-1 acceptance result

**PASS — 2026-08-17.** Recorded after the Taylor-authorized corrections, first-binding promotion metadata, and required Foundation validation checks passed. This advances authority only to Phase-2 contract/design drafting; UI implementation and deployment remain unauthorized until their applicable contracts and decisions are approved.

## Interfaces / Dependencies

All Foundation contracts feed Phase-1 review. Later Testing/UI/Data/Model contracts add gate-specific evidence without weakening this contract.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Validation tooling may be lightweight in Phase 1 if it objectively checks structure, references, statuses, YAML, master hash, and repo scope.
- **IMPLEMENTATION CHOICE:** Later gates may add stricter metrics/thresholds through approved contracts.

## Prohibited Behavior

- Self-approval; “pass with exceptions” that hides failed blockers; deployment from DRAFT contracts; public fixtures as facts; skipping gates; selective forecast scorecard; unrelated cleanup/refactor in a release branch.

## Failure / Degraded States

- A failed Phase-1 criterion is reported `FAIL`; an external prerequisite preventing evaluation is `BLOCKED`; unevaluated later gates remain `NOT EVALUATED`.
- Only affected scope pauses; unaffected Foundation corrections may continue.

## Risks / Open Decisions

- R-001 intentionally blocks Phase 2 until review. O-001A and O-001B must be resolved as engineering implementation choices before their affected work; O-001C and O-001D require Taylor approval before build-output or Pages-workflow integration.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after the Phase-1 external review and authorized correction pass.
- 0.1.2 (2026-08-17): Corrected Phase-1 acceptance lifecycle language and recorded Taylor approval of D-007/D-008. Remains DRAFT pending final validation and promotion.
- 0.1.1 (2026-08-17): Replaced the former combined open-decision reference with O-001A through O-001D and their existing authority classifications. Remains DRAFT.
- 0.1.0 (2026-08-17): Initial Foundation draft. Not approved.
