# Infrastructure Contract

```text
Contract: Systems Monitor Infrastructure Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: ARCHITECTURE_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 90B5E9A47971A346C0F12FD687B6E9DCB88629AD22073ECF2EC8797F3DBFBFE3
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §0.3, §35.1–35.5, §38.2, §62, §64.1–64.12, §66–68. This BINDING contract is current provider-neutral Infrastructure authority; no provider or deployment is selected. MVP liveness and cost governance are accepted post-V4.1 Taylor requirements recorded in D-009 and D-010 pending future Master consolidation; they are not attributed to existing V4.1 text.

## Purpose

Define provider-neutral operational boundaries without constructing speculative multi-cloud infrastructure.

## Scope

Domain interfaces for `JobScheduler`, `ObjectStore`, `AnalyticalStore`, `SecretsProvider`, `PublicDataPublisher`, and `JobTelemetry`; current GitHub Pages hosting; MVP system-evaluation heartbeat and source-aware triggers; cost governance; vertical-slice measurement requirements; atomic publication and retry safety.

## Explicitly Out of Scope

- Selecting or implementing AWS, Azure, Google Cloud, Cloudflare, another permanent provider, or multiple interchangeable adapters.
- Deploying databases, scheduled analytics, APIs, secrets, collectors, or monitor UI.
- Implementing schedules, billing APIs, cloud resources, a multi-cloud cost framework, or fixed dollar budgets in Foundation.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT I-001:** GitHub Pages/Jekyll remains the public host during Foundation; it is not assumed to be the permanent compute/storage platform.
- **BINDING REQUIREMENT I-002:** Presentation, public interface, compute, and durable storage boundaries are separable.
- **BINDING REQUIREMENT I-003:** The six named domain capabilities use minimal interfaces at real boundaries; do not create unused vendor adapters.
- **BINDING REQUIREMENT I-004:** Provider selection is deferred until measured compute duration, CPU/memory, schedule, storage growth, query patterns, traffic, backtesting load, cost, and rights constraints exist.
- **BINDING REQUIREMENT I-005:** GitHub Actions may bootstrap tests/deployment/small jobs but must not become an irreversible analytics dependency.
- **BINDING REQUIREMENT I-006:** Public snapshots are immutable/versioned and atomically activated through a current manifest/pointer only after validation.
- **BINDING REQUIREMENT I-007:** Failed publication leaves the last valid snapshot active.
- **BINDING REQUIREMENT I-008:** Jobs are idempotent, bounded, retry-safe, and concurrency-safe before scheduled production use.
- **BINDING REQUIREMENT I-009:** Secrets never enter repository/public payloads and are provided with least privilege.
- **BINDING REQUIREMENT I-010:** Runtime/tool versions and lockfiles support Windows development and Linux CI.
- **BINDING REQUIREMENT I-011:** Telemetry must eventually cover run IDs, status, timing, failures, retries, source latency, snapshot IDs, and publication outcome without exposing secrets.

### MVP system liveness and refresh

- **BINDING REQUIREMENT I-012:** During normal MVP operation, the base system must evaluate whether relevant source or state changes warrant publication at least once in every four-hour window. Known releases and material-change triggers may require earlier evaluation.
- **BINDING REQUIREMENT I-013:** Every source follows its own justified observation/release/retrieval cadence. A monthly or quarterly official series remains current when no newer official release is available or expected; no source is polled more frequently merely to create the appearance of freshness.
- **BINDING REQUIREMENT I-014:** Scheduling combines source-specific cadence, checks shortly after known release times, and material-change triggers. Faster operational sources may be evaluated more frequently when justified.
- **BINDING REQUIREMENT I-015:** The four-hour heartbeat evaluates whether work is warranted; it does not require refetching every source, recomputing the entire model, publishing an unchanged snapshot, or running heavy forecasts/backtests. Recompute only affected state/models under their own triggers or schedules, then atomically publish only when validation and material-change rules warrant activation.

### Infrastructure and API cost governance

- **BINDING REQUIREMENT I-016:** Apply `COMPUTE ONCE, READ MANY`: public users normally read already-computed, validated snapshots/results and do not trigger expensive model execution.
- **BINDING REQUIREMENT I-017:** Prefer bounded scheduled, event-driven, or batch compute over always-running compute whenever technically adequate. Do not create always-on VMs, databases, queues, caches, or other paid infrastructure merely because they are conventional choices.
- **BINDING REQUIREMENT I-018:** Free, local, or GitHub capabilities may serve an approved phase when they meet safety, reliability, rights, and workload requirements; this does not make GitHub an irreversible analytics dependency.
- **BINDING REQUIREMENT I-019:** Introduce a paid infrastructure or API resource only when a measured requirement or material product benefit justifies it. Expected monthly recurring cost is a first-class selection criterion, and commercial data must demonstrate material incremental value over adequate authoritative/free coverage.
- **BINDING REQUIREMENT I-020:** Future paid resources must use configurable budget or cost ceilings and cost monitoring/alerts where the selected provider supports them. A workload exceeding its intended cost envelope triggers review rather than silently scaling without bound.

## Interfaces / Dependencies

| Interface | Minimum responsibility | Must not expose |
|---|---|---|
| `JobScheduler` | Start a versioned, bounded job with schedule/run identity | Vendor cron/event types into domain logic |
| `ObjectStore` | Put/get immutable artifacts by generated key/hash | Local absolute paths or public-by-default access |
| `AnalyticalStore` | Transactional/analytical reads and writes through controlled data services | Raw SQL to public clients |
| `SecretsProvider` | Resolve scoped secrets at runtime | Secret values in logs/config/repo |
| `PublicDataPublisher` | Validate/publish immutable snapshot and atomically activate manifest | Partial in-place mutation |
| `JobTelemetry` | Record run state, metrics, and correlation IDs | Restricted content/credentials |

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Local filesystem, DuckDB/Parquet, and small GitHub Actions jobs may serve a bounded vertical-slice path when later authorized.
- **IMPLEMENTATION CHOICE:** One provider implementation may be chosen later; clean boundaries do not require multi-provider parity.
- **IMPLEMENTATION CHOICE:** Public payloads may be served as static versioned files or by a read-only service.

## Prohibited Behavior

- Premature permanent provider choice; generalized multi-cloud framework; unjustified always-on paid services; convenience-first commercial data; unbounded cost scaling; mutable public dataset updates; unbounded retries; concurrent writers without control; secrets in code/logs/public artifacts; provider SDK types crossing domain contracts.

## Failure / Degraded States

- Job failure records diagnostics and does not activate output.
- Retry uses the same idempotency scope and cannot duplicate facts.
- Provider/telemetry outage cannot convert partial output into the current public snapshot.

## Acceptance Criteria

1. Interfaces are defined semantically without vendor implementation.
2. Atomic publication and retry/concurrency invariants align with Public Data and Security contracts.
3. Provider-decision measurements and deferral are explicit.
4. No provider code, cloud resource, workflow, or deployment is added in Phase 1.
5. MVP scheduling can demonstrate a maximum four-hour base evaluation interval plus source/release-aware earlier checks without requiring universal polling, full recomputation, or unchanged publication.
6. Infrastructure proposals document compute-once/read-many behavior, expected recurring cost, justification for paid resources, and an enforceable cost envelope where supported.

## Risks / Open Decisions

- Permanent provider and actual stores are deferred by D-004. O-001C covers build-output ownership; O-001D covers Pages workflow integration. O-001A and O-001B remain engineering implementation choices. See R-008, R-011, and R-013.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): First BINDING version approved by Taylor after Phase-1 external review, including accepted D-009/D-010 liveness and cost-governance requirements; no provider selected.
- 0.1.1 (2026-08-17): Added post-V4.1 D-009 MVP liveness/source-aware refresh invariants, D-010 compute-once/read-many cost governance, and split open-decision references. Remains DRAFT; no provider selected.
- 0.1.0 (2026-08-17): Initial Foundation draft. Not approved.
