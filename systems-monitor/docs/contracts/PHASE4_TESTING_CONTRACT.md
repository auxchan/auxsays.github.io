# Systems Monitor Phase-4 Testing Contract

```text
Contract: Systems Monitor Phase-4 Testing Contract
Version: 0.1.1
Status: DRAFT
Parent Master Spec: V4.1
Depends On: TESTING_CONTRACT.md, RELEASE_ACCEPTANCE_CONTRACT.md, STATE_MODEL_CONTRACT.md, DEPENDENCY_RELATIONSHIP_CONTRACT.md, ALLOCATION_PROPAGATION_CONTRACT.md, DERIVATION_TRANSPARENCY_CONTRACT.md
Supersedes: None
Approved By: —
Approved At: —
Content Hash: PENDING — DRAFT
Last Updated: 2026-08-19
```

## Authority / Status

Governing Master sections: §9–14, §20–20.1, §31.3–31.5, §51, §64.1,
§67 Phase 4, and §68, subordinate to the BINDING Testing and Release Acceptance
Contracts. This DRAFT defines future Gate-B evidence; it authorizes no tests
against live sources, dependency installation, implementation, gate closure, or
self-approval.

## Purpose

Define objective evidence required before State, Dependency, Allocation, and
Derivation work can pass Gate B. Passing implementation-specific unit tests is
necessary but insufficient; evidence must prove the contracts' semantics.

## Test Principles

- Tests are deterministic, local/offline by default, and use retained fixtures.
- Every expected value states its authority, units, time semantics, and reason.
- Positive, negative, boundary, degraded, replay, and mutation cases are required.
- A contract owner cannot silently redefine expected behavior to make a test pass.
- Human QA and Taylor gate approval remain separate from automated results.
- No new dependency, paid service, network call, source ingestion, or public
  activation is authorized by this contract.
- Phase-4A labor fixtures may prove software mechanics but cannot pass Gate B.
  Synthetic structural fixtures may test edge cases; Gate B requires a bounded
  original-authority Phase-4B structural proof.

## Required Evidence Matrix

### P4T-STATE — State model

1. Mixed daily/weekly/monthly/quarterly inputs use explicit reference and age
   rules without pretending they share a timestamp.
2. `as_known` excludes future publication/acceptance and `latest_revised` selects
   the correct eligible vintage.
3. Exact age/staleness/source-health/rights evidence survives state output.
4. Missing, stale, delayed, contradictory, insufficient, and rights-blocked
   inputs produce explicit `UNKNOWN`/degraded results, never zero or fabricated
   neutrality.
5. State vocabulary, baseline/window/config versions, geography, units, and
   derivation are validated; unsupported numeric precision is rejected.

### P4T-REL — Relationship model

6. Relationship identity, direction, type/mechanism, polarity, evidence class,
   quality/coverage/calibration/regime, geography, lag, lifecycle, and versions
   round-trip without loss.
7. Candidate/experimental/deprecated/rejected relationships cannot traverse as
   accepted production authority.
8. Effective/knowledge interval replay chooses the correct relationship/evidence
   version and rejects future knowledge.
9. Correlation or model score alone cannot become a causal/numeric edge.
10. Cycles, invalid units, missing evidence, unsupported precision, invalid
    geography, and hostile metadata fail/degrade explicitly.
11. Criticality remains distinct from dollar magnitude and tests TTR greater
    than TTS, concentration, substitution, capacity, buffers, and hidden/common-
    cause dependencies.

### P4T-STRUCT — Authoritative structural I/O

12. Gate-B evidence identifies and retains the original authoritative structural
    source, exact dataset/table/matrix/version, official publication/vintage,
    rights/terms fingerprint and operation permissions, schema, units, source
    and target classifications, crosswalk/version, source health, parser/
    transformation, and bounded scope. BEA Real GDP/NIPA is distinct and cannot
    stand in for structural Supply/Use or I/O evidence.
13. Governance-approved deterministic relationship generation proves source
    artifact → validated table/version → validated taxonomy/crosswalk → approved
    conversion/filter/acceptance rule → versioned `ACCEPTED` structural records.
    Manual per-edge approval is not required; invalid/ambiguous/inferred/LLM
    records remain candidates and cannot satisfy Gate B.
14. Direct-requirement generation and direct-path propagation are tested from
    real authoritative evidence. Total requirements have a separately declared
    benchmark/decomposition/non-recursive role and are never traversed as normal
    direct edges while their indirect effects are also present in topology.
15. A configuration combining recursive direct paths with overlapping total-
    requirement contribution rejects or reconciles explicitly. Where comparison
    is mathematically appropriate, accumulated direct paths are checked against a
    total-requirements benchmark and discrepancies outside versioned tolerance
    fail with evidence.
16. Supply/Use and market-share artifacts are used only under exact declared
    computational roles supported by authoritative documentation. Crosswalk
    version/effective/knowledge handling, misclassification, unsupported matrix
    interchange, and unknown-as-zero all have negative tests.

### P4T-PROP — Propagation mechanics

17. One-edge and multi-edge fixtures prove deterministic ordering, sign, unit,
    lag, geography, contributions, and focused trace.
18. Separate fixtures exercise offset, amplification, buffer absorption, partial
    absorption, substitution, blocking, delay, saturation/floors/ceilings, and
    unknown supporting evidence.
19. Materiality, max depth, max rounds, node/path/contribution budgets, and all
    stop/truncation reasons terminate exactly as configured.
20. Same-period cycles reject under the Phase-4A profile; any later approved
    solver proves convergence and deterministic non-convergence fallback.
21. Mutation/property tests prove no recursion escape, dynamic budget growth,
    order-dependent drift, NaN/infinite value, or incompatible-unit arithmetic.

### P4T-COMMON — Common cause and double counting

22. Two paths from one origin retain origin/common-cause identity and are not
    naively summed.
23. Independent origins remain independent; unresolved overlap returns a range/
    qualitative warning rather than a falsely exact net result.
24. Caps/overlap rules preserve positive, negative, absorbed, and unresolved
    components and are version/replay stable.
25. Gate B includes accepted real structural paths sharing an origin where naive
    aggregation overattributes; the approved reconciliation must change or bound
    the result. Synthetic fixtures alone are insufficient.

### P4T-BEHAVIOR — Buffer, substitution, lag, and capacity

26. Gate B includes an accepted real structural path whose result changes under
    evidence-backed inventory/buffer behavior, covering full/partial/exhausted
    behavior as applicable; stale or missing buffer evidence degrades honestly.
27. Gate B includes an evidence-backed eligible substitute with bounded capacity
    or an evidence-backed no-valid-substitute result, including qualification,
    geography, lead-time, compatibility, regulatory, logistics, and capacity
    checks as applicable.
28. At least one accepted relationship changes current-state treatment because
    a real supported immediate/delayed/operational/publication/physical lag is
    applied. Unknown lag is not zero and lag handling is not labeled forecasting.
29. Capacity/headroom, utilization, binding threshold, saturation, and maximum
    throughput are tested where applicable; absent authoritative current evidence
    yields `UNKNOWN`, never infinite response or fabricated precision.

### P4T-ALLOC — Allocation

30. Supply/demand/capacity/eligibility/cost/priority/geography inputs are explicit
    and versioned; missing evidence produces partial/qualitative output.
31. Conservation fixtures reconcile allocated, absorbed, unmet, and residual
    within tolerance; inapplicable conservation is explicitly justified.
32. Capacity, substitution, priority ties, insufficient supply, excess supply,
    invalid units, and deterministic tie-breaking have boundary tests.
33. Output is current/as-of CALC and tests reject portfolio advice, optimization,
    future employment claims, forecasts, scenarios, rankings, and prescriptions.

### P4T-DERIVE — Derivation and reproduction

34. OBS fixtures show exact official series/table/cell, units, periods,
    publication/retrieval/acceptance, vintage, publisher role, health, methodology,
    rights, and distinct machine/human evidence links.
35. CALC fixtures reproduce from exact immutable inputs, snapshot, cutoff/replay,
    algorithm/config versions, transforms, assumptions, intermediates, and units.
36. Structural CALC fixtures additionally retain accepted relationship IDs/
    versions, structural source/table/matrix/version, classification and
    crosswalk versions, generation/acceptance rule, direct/total role,
    propagation profile, buffer/substitution/lag rules, common-cause
    reconciliation, and material intermediate contributions.
37. Claim-class laundering, missing/version-mismatched references, graph cycles,
    depth/node overflow, recursive duplication, and fabricated evidence fail.
38. Layered public summaries preserve meaning/status/uncertainty while bounded
    deep derivation remains independently checkable.

### P4T-PUBLIC — Public read model and PDI

39. The Phase-4 candidate is validated against the BINDING PDI envelope and
    publication classes; no contract-local alternate public interface is allowed.
40. The allowlist rejects secrets, local paths, raw protected payloads, internal
    graph dumps, candidate relationships, disallowed sources, and fixture/synthetic
    leakage.
41. Outlook remains unavailable/not supported while factual mode is active; no
    Phase-4 work can reintroduce forecast/scenario/ranking/trace fixture claims.
42. Atomic publication, rollback, content hash, prior-known-good behavior, and
    partial/degraded health remain testable when publication is later authorized.
    The candidate also proves bounded master-view inputs, typed OBS/CALC labels,
    and exact source/provenance references without raw-table access.
43. Read-model tests require `structuralCoverageState`, covered/unsupported
    domains, accepted/candidate counts, relationship evidence mix, stale/degraded
    structural inputs, and derivation completeness. Phase-4A and sparse Phase-4B
    graphs cannot imply economy-wide coverage.

### P4T-SEC — Security, integrity, and hostile inputs

44. Fuzz/mutation fixtures cover malformed values/units/times/IDs, oversized
    graphs, injection text, executable formula attempts, path/query traversal,
    and unsafe URLs.
45. Allowlisted algorithms/configurations reject source-supplied instructions;
    least privilege and rights/publication boundaries are enforced.
46. Logs/evidence do not leak secrets or protected payloads and remain sufficient
    for audit, replay, and failure diagnosis.

### P4T-COST — Cost, operability, and regression

47. The candidate demonstrates the $0 recurring-cost target using local/static/
    repository-compatible infrastructure and no required paid/API/LLM service.
48. Cold/offline replay succeeds from retained fixtures; loss of any optional AI
    or network service does not break core state/relationship/derivation behavior.
49. Existing Phase-3 factual/PDI/source/replay/security tests remain green and the
    authoritative Master Spec hash and BINDING contracts remain unchanged.
50. Clean Windows/Linux evidence compares canonical results and records measured
    runtime, memory, storage, graph size, rounds, paths/contributions, truncation,
    and no-op/public-read reuse under the versioned configuration.
51. Performance evidence uses bounded representative/adversarial fixtures and
    proves declared budgets without choosing infrastructure by benchmark theater.

## Gate-B Required Package

Before Gate B can be considered, a future authorized implementation must provide:

1. A test-plan-to-requirement matrix covering every item above.
2. Deterministic fixtures and exact automated commands/results.
3. State/relationship/propagation/allocation/derivation candidate artifacts.
4. Replay and common-cause evidence with readable worked examples.
5. Public-candidate validation and synthetic/secret/candidate leakage evidence.
6. Security, cost, performance, failure, recovery, and prior-phase regression
   reports.
7. A concise Human State/Dependency QA guide that does not require database or
   code inspection.
8. Independent review findings, unresolved risks, and Taylor's explicit PASS.
9. Original-authority Phase-4B structural artifacts/evidence, deterministic
   accepted relationship-generation proof, and direct/total role/double-count
   evidence; Phase-4A output cannot substitute.

No implementation may label Gate B PASS by generating its own report. Automated
PASS, independent evidence review, human QA, and Taylor approval are distinct.

## Acceptance Criteria for This Contract

- Every Phase-4 normative requirement has at least one positive and one relevant
  negative/degraded test route.
- Evidence proves semantics/replay/bounds, not only code coverage.
- The package is reproducible offline without new dependencies or live sources.
- Gate B stays OPEN until Phase-4B original-authority structural evidence, every
  required behavioral proof, Human QA, and Taylor approval pass.

## Risks / Open Decisions

- **OPEN DECISION:** Taylor must approve the Gate-B test matrix and human QA scope
  after the five Phase-4 contracts are reviewed.
- Representative graph size/performance budgets remain a later evidence-driven
  implementation choice.
- See R-027 through R-034.

## Version / Approval / Change History

- 0.1.1 (2026-08-19): External-review correction splitting Phase-4A mechanics
  from required Phase-4B authoritative structural evidence; adds deterministic
  structural promotion, direct/total semantics, real behavioral proof, coverage,
  cross-platform, runtime/memory/storage, and corrected Gate-B requirements.
  Remains DRAFT; Gate B OPEN.
- 0.1.0 (2026-08-18): Initial Phase-4 review draft. Gate B remains OPEN.

## Amendment protocol

Use the project amendment protocol. Record requirement/test mappings, fixture and
schema versions, replay/public/security impacts, evidence migrations, and Taylor's
decision. Never weaken an acceptance criterion merely to match an implementation.
