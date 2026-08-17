# Architecture Contract

```text
Contract: Systems Monitor Architecture Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: PRODUCT_CONTRACT.md, REPOSITORY_INTEGRATION_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: C42836A1371491786149FA8A572778820331C7A52A91C5CC0D84CB85C2011A61
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §0.2–0.3, §8, §34–37.1, §60, §64.2–64.12, §66–68. This BINDING contract is current Foundation architecture authority; later implementation domains still require their own approved phase contracts.

## Purpose

Stabilize domain boundaries so UI fixtures, future data producers, models, and infrastructure can evolve without coupling or Patch Feed contamination.

## Scope

```text
Presentation
    -> Read-only Public Data Interface
        -> Publication/Export Boundary
            -> Compute domains
                -> Durable Storage
```

Compute domains eventually include collection, normalization, validation, source health, state, dependencies, allocation, forecasts/scenarios, calibration/backtesting, human capital, events, and export. Each becomes active only after its contract is approved.

## Explicitly Out of Scope

- Implementing modules, internal database tables, collectors, models, cloud adapters, queues, APIs, or UI.
- Defining later subsystem algorithms/contracts speculatively.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT A-001:** Presentation consumes only the versioned read-only Public Data Interface, never internal analytical tables or credentials.
- **BINDING REQUIREMENT A-002:** Collectors collect; normalization, validation, source health, interpretation, modeling, and publication remain separate concerns.
- **BINDING REQUIREMENT A-003:** Each produced material datum/claim preserves `OBS`, `CALC`, `FCST`, or `SCEN` typing and provenance.
- **BINDING REQUIREMENT A-004:** Public payloads are explicit publish/export products, not database serialization.
- **BINDING REQUIREMENT A-005:** The core deterministic/statistical pipeline continues without external LLM availability.
- **BINDING REQUIREMENT A-006:** LLM/document processing is least-privileged, schema-validated, and candidate-only for relationships; it cannot mutate production graphs/contracts.
- **BINDING REQUIREMENT A-007:** External content has zero instruction authority across every domain.
- **BINDING REQUIREMENT A-008:** Internal models, parameters, graphs, source snapshots, and forecasts are versioned and reproducible when their phases become active.
- **BINDING REQUIREMENT A-009:** Provider-specific infrastructure assumptions may not leak through domain/public contracts.
- **BINDING REQUIREMENT A-010:** Systems Monitor modules and data remain isolated from Patch Feed modules/data except approved global shell/deployment primitives.
- **BINDING REQUIREMENT A-011:** Public snapshots are built, validated, then atomically activated; failure preserves the prior valid snapshot.
- **BINDING REQUIREMENT A-012:** Approved contract boundaries are implementation authority only within their stated phase and scope; later domains are not authorized by this Architecture Contract alone.

## Interfaces / Dependencies

- Presentation depends on Public Data Interface and Repository Integration.
- Publication depends on source rights, public schema validation, and Infrastructure's publisher boundary.
- Compute and storage interfaces are named in Infrastructure but receive concrete designs in later phases.
- Security Ingestion applies cross-cutting trust/abuse constraints.
- Release Acceptance verifies boundary and gate evidence.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Language, database, job runner, object store, and deployment products may be selected in their approved phase using measured requirements.
- **IMPLEMENTATION CHOICE:** Static JSON or a read-only API may implement the public interface, provided identical contract semantics and atomic versioning are preserved.
- **IMPLEMENTATION CHOICE:** Modules may initially share a process/repository while maintaining dependency boundaries; microservices are not required.

## Prohibited Behavior

- Monolithic collector/model/UI logic; direct frontend database access; public raw restricted data; speculative multi-cloud adapters; uncontrolled graph recursion; hidden LLM numerical truth; Phase-2+ implementation without its required approved contracts.

## Failure / Degraded States

- Each boundary fails closed: invalid source data is quarantined, invalid model/public output is not promoted, and public consumers retain the last valid snapshot.
- Optional AI/discovery failure cannot block core state/forecast operation.

## Acceptance Criteria

1. Every Foundation contract maps to a clear boundary without circular authority.
2. Public types are independent of internal storage and provider specifics.
3. Patch Feed isolation, AI independence, external-content trust, atomic publication, and phase control are explicit.
4. Architecture can support a static Phase-2 fixture producer and later real producer without public type replacement.

## Risks / Open Decisions

- Concrete processes/stores are intentionally deferred. See R-005–R-008 and R-011.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review; stale DRAFT-only wording updated without changing substantive architecture requirements.
- 0.1.0 (2026-08-17): Initial Foundation draft. Not approved.
