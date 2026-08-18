# Systems Monitor Ontology and Crosswalk Contract

```text
Contract: Systems Monitor Ontology and Crosswalk Contract
Version: 1.0.0
Status: BINDING
Parent Master Spec: V4.1
Depends On: DATA_CONTRACT.md, SOURCE_CONTRACT.md
Supersedes: None
Approved By: Taylor
Approved At: 2026-08-17
Content Hash: 3322E9890E3DBFDC2597A092034A6E3DC9D0C4D5603AD89517684FE1F46D874B
Last Updated: 2026-08-17
```

## Authority / Status

Governing Master sections: §31.1–31.6, §32, §37, §61, §64.1–64.12, §65, §67 Phase 3, and §68. This BINDING contract is Taylor-approved authority for only the canonical mappings required by the bounded Phase-3 first slice; broad classification corpora and Phase 4 remain unauthorized.

## Purpose

Stabilize versioned concepts and explicit source-to-canonical mappings so incompatible indicators, units, geographies, industries, occupations, and entities cannot be combined through undocumented one-to-one assumptions.

## Scope

- Namespaced/versioned canonical and source-native concepts.
- Many-to-many, effective-dated, provenance-bearing crosswalks and conversion rules.
- Phase-3 source-series-to-indicator, U.S.-national geography, unit, frequency, and seasonal-adjustment foundations.

The namespace architecture reserves explicit versioned identities for the following families without authorizing full corpus construction:

| Family | Required identity/version boundary | Phase-3 posture |
|---|---|---|
| NAICS | code, title, level, edition, effective dates | Reserved; mappings deferred beyond approved slice |
| SOC | code, title, level, edition, effective dates | Reserved; corpus deferred |
| O*NET-SOC | O*NET-SOC code/version and referenced SOC edition | Reserved; corpus deferred |
| CIP | code/title/version and education-classification edition | Reserved; corpus deferred |
| BEA classifications | dataset/table/line/industry or commodity vocabulary version | Only exact slice metadata if needed |
| Geography | authority namespace, geography ID/type, boundary vintage, semantic basis | U.S.-national identity only in first slice |
| Internal commodity/resource | AUXSAYS namespace/version, definition, evidence and supersession | Reserved for later approved phase |
| Trade/commodity codes | HS/HTS/NAICS or other authority namespace/version/effective dates | Reserved for later approved phase |
| Company/facility | source-native and canonical entity/facility IDs, resolution version/evidence | Reserved for later approved phase |

## Explicitly Out of Scope

- Building broad NAICS/SOC/O*NET-SOC/CIP/BEA/trade/commodity/company/facility crosswalk corpora, company/facility resolution, supply-chain/dependency edges, model features, causal inference, forecasts, or automatic acceptance of machine/LLM-proposed mappings.
- Creation or downloading of taxonomy datasets.

## Binding Requirements / Invariants

- **BINDING REQUIREMENT ONT-001:** Every concept has a stable namespaced ID, label, definition, concept type, vocabulary/version, effective interval, status, provenance, and supersession link when applicable.
- **BINDING REQUIREMENT ONT-002:** Indicator concepts explicitly define measure, population/universe, unit, seasonal-adjustment state, frequency, geography level, aggregation behavior, and valid-time meaning.
- **BINDING REQUIREMENT ONT-003:** Source-native IDs are preserved. Canonicalization adds an explicit mapping and never replaces the original identity/provenance.
- **BINDING REQUIREMENT ONT-004:** Crosswalks are versioned and effective-dated. Historical reproduction separately selects the mapping version effective in valid time, proven publicly available by the cutoff for `PUBLICLY_AVAILABLE_AS_OF`, or actually retrieved/validated/accepted by AUXSAYS by the cutoff for `OPERATIONALLY_KNOWN_AS_OF`. These replay modes cannot silently substitute for one another.
- **BINDING REQUIREMENT ONT-005:** Mappings may be one-to-one, one-to-many, many-to-one, or unresolved. The system never assumes one-to-one solely from similar labels.
- **BINDING REQUIREMENT ONT-006:** Weighted mappings record weight, weight basis, denominator/universe, expected-sum rule, geography/time scope, rounding/tolerance, and evidence provenance.
- **BINDING REQUIREMENT ONT-007:** Unit conversions are dimensionally compatible, deterministic, versioned, and distinguish scale conversion from substantive aggregation or seasonal adjustment.
- **BINDING REQUIREMENT ONT-008:** Geography meaning is explicit: boundary vintage, national/state/county/metro/other level, inclusion rules, and whether a value is place-of-work, residence, production, shipment, or another basis when relevant.
- **BINDING REQUIREMENT ONT-009:** Ambiguous, low-evidence, conflicting, out-of-effective-range, or incomplete mappings remain candidates and cannot silently aggregate or enter public factual claims.
- **BINDING REQUIREMENT ONT-010:** LLM/document proposals have candidate status only, zero instruction authority, and require deterministic validation plus corroborated evidence and the applicable approval.
- **BINDING REQUIREMENT ONT-011:** Crosswalk changes are append-only versions. Previously published/reproduced snapshots retain their exact mapping/version references.
- **BINDING REQUIREMENT ONT-012:** The initial Phase-3 slice is limited to explicit mappings for its approved source series, units, seasonal states, frequencies, and U.S.-national geography; later taxonomies require scoped amendments.
- **BINDING REQUIREMENT ONT-013:** Rights and attribution for source vocabularies/crosswalk datasets are machine-enforced before storage, transformation, or public display.
- **BINDING REQUIREMENT ONT-014:** Mapping provenance preserves valid/effective time, proven official publication/public-availability time, AUXSAYS retrieval time, and AUXSAYS system-known/accepted time separately. A current vocabulary download cannot prove that the same mapping was historically public at an earlier cutoff.

## Interfaces / Dependencies

- Source Contract supplies source-native metadata and vocabulary versions.
- Data Contract references exact concept/crosswalk versions in observations, calculations, and snapshots.
- Testing Contract validates semantics, weights, effective-time behavior, ambiguity, and reproducibility.
- Future Phase-4+ contracts may consume approved concepts but cannot redefine them silently.

## Allowed Implementation Freedom

- **IMPLEMENTATION CHOICE:** Store vocabularies/crosswalks relationally, as versioned files, or both after approval.
- **IMPLEMENTATION CHOICE:** Use exact decimal/rational weights and suitable tolerances per mapping family.
- **IMPLEMENTATION CHOICE:** Introduce hierarchy/graph traversal only when a bounded approved use case needs it.

## Prohibited Behavior

- Label-only joins; unversioned mappings; overwriting historical crosswalks; conflating public availability with AUXSAYS acceptance; backdating a current mapping; silent unit/seasonal/geography conversion; mapping weights without a basis; automatic candidate promotion; using current classifications in historical replay without effective and knowledge-time rules.

## Failure / Degraded States

- Missing/incompatible/ambiguous mapping quarantines the affected normalized record or leaves it source-native; it does not invent a canonical identity.
- Weight/range/effective-date/rights validation failure prevents aggregation and public-candidate inclusion.
- Later vocabulary drift creates a new candidate version and explicit source-health evidence.

## Acceptance Criteria

1. The vertical-slice fixtures map every enabled source series to one exact canonical indicator/version while preserving source identity.
2. Tests cover one-to-one, many-to-one, one-to-many, unresolved, expired, superseded, and conflicting mappings.
3. Weighted mappings enforce declared range/sum/tolerance and fail on missing basis.
4. Historical replay independently proves the correct effective, publicly-available-as-of, and operationally-known-as-of mapping versions.
5. Incompatible unit, seasonal adjustment, universe, or geography combinations are rejected.
6. Candidate/LLM-proposed mappings cannot enter accepted/public state without evidence and approval.
7. Every public fact traces to the exact concept and crosswalk versions used.

## Risks / Open Decisions

- The first slice intentionally defers NAICS, SOC, entity, and facility complexity. See R-022 and future Phase-4 scope.
- **OPEN DECISION:** Any historical classification bridging needed beyond source-series mappings must return for scoped Taylor review.

## Conditional Data Profile

- Concept and mapping provenance includes source, distinct public-availability/retrieval/system-accepted times, content hash, methodology/license references, and reviewer state.
- Unknown rights or semantics fail closed for aggregation/publication.

## Version / Approval / Change History

- 1.0.0 (2026-08-17): Taylor-approved first BINDING version after external-review correction separating mapping public availability from AUXSAYS operational acceptance.
- 0.1.0 (2026-08-17): Initial Phase-3 review draft. Not approved; no implementation authority.

## Amendment protocol

Use the project amendment protocol and identify affected historical snapshots, migrations, and replay tests. Taylor alone may promote this contract.
