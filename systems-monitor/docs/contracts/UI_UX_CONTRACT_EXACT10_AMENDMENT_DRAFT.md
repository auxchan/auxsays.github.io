# Systems Monitor UI/UX Contract — Exact-10 Amendment Draft

```text
Proposal: UXA-001 Exact-10 / View-All / Multi-Placement Amendment
Proposal Version: 0.1.1
Status: SUPERSEDED HISTORICAL PROPOSAL / NOT BINDING
Date: 2026-08-25
Targets: UI_UX_CONTRACT.md 1.0.0 — UX-003 and UX-006
Implementation authority: NONE
Promotion authority: Taylor only
Disposition: UXA-001 approved and promoted into UI_UX_CONTRACT.md 1.0.1
```

## 1. Purpose and narrow scope

This historical proposal recorded the conflict between UI/UX 1.0.0 and the
approved exact-ten hierarchy requirement. Taylor approved UXA-001 on 2026-08-25
and promoted its authoritative semantics into BINDING UI/UX 1.0.1. The proposal
was limited to:

- exact child-placement cardinality;
- incomplete-taxonomy behavior;
- View All as non-hierarchy related records;
- canonical-factor multi-placement without duplicated analytical truth;
- hierarchy-versus-structural-relationship separation needed by those changes;
- bounded progressive disclosure and non-spatial access.

This artifact does not modify or supersede the BINDING contract and is retained
only as review history. UI/UX 1.0.1 is authoritative. The promotion did not
redesign color, typography, camera timing, renderer architecture, node art,
motion grammar, inspector behavior, mobile composition, primary modes, or
unrelated accessibility rules.

## 2. Existing conflict

Current `UI_UX_CONTRACT.md` 1.0.0 states:

- UX-003: progressive `10 -> 10 -> 10`, with **at most ten** defensible ranked
  children per level and View All when more defensible items exist.
- UX-006: View All exposes a bounded list while preserving the relationship
  between the displayed Top 10 and nearby candidates.

Taylor's product requirement is now exact cardinality:

- every approved Core/outcome hierarchy parent has exactly ten Sub-A hierarchy
  placements;
- every approved Sub-A hierarchy placement has exactly ten Sub-B hierarchy
  placements;
- record 11+ may not remain an additional hierarchy child under View All.

The requirements could not be silently reinterpreted. UI/UX 1.0.1 now supplies
the required BINDING amendment. Exact-ten implementation remains separately
authorized.

## 3. Proposed replacement for UX-003

> **PROPOSED UX-003 — Exact-ten progressive hierarchy.** Progressive
> `10 -> 10 -> 10` drill-down is the primary public information hierarchy.
> Every taxonomy-complete approved Core or outcome parent contains exactly ten
> approved Sub-A hierarchy placements. Every taxonomy-complete approved Sub-A
> placement contains exactly ten approved Sub-B hierarchy placements. Exact ten
> is a taxonomy-acceptance requirement, not permission to invent concepts. When
> fewer than ten defensible canonical factors and placements are approved, the
> branch remains explicitly `TAXONOMY_INCOMPLETE` and may not present itself as
> a complete exact-ten branch. Each transition preserves parent context. The UI
> never renders the theoretical complete registry simultaneously.

### Consequences

- Cardinality applies to hierarchy placements, not the number of source series,
  evidence records, or search results.
- Filler, synthetic neutral factors, and undefined reserved public slots are
  prohibited.
- A complete taxonomy can still have partial current-data coverage.
- A current-data outage does not delete the approved placement; it changes the
  separately governed data-coverage/availability state.

## 4. Proposed replacement for UX-006

> **PROPOSED UX-006 — Related-record View All.** View All remains in the selected
> hierarchy context but does not reveal hierarchy child placement 11, 12, or
> later. It opens a bounded, searchable, sortable, accessible collection of
> explicitly labeled non-hierarchy related records, which may include supporting
> indicators, alternate official series, evidence, source records, geography
> views, histories, methods, and other payload-backed records. Related records
> cannot affect exact-ten completeness, rank/order, parentage, or analytical
> roll-up merely by appearing in View All. The UI clearly distinguishes the ten
> hierarchy placements from related records and preserves a route back to the
> selected exact-ten context.

### Consequences

- View All is not a second hidden hierarchy.
- Search results may locate related records without making them children.
- Rank 10/11 near-cutoff semantics from the current generic Top-10 model do not
  apply to an exact-ten taxonomy unless a separately governed ranked related
  collection explicitly supplies those fields.
- Existing rights, provenance, canonical routing, and bounded-list rules remain.

## 5. Proposed canonical-factor / placement requirement

> **PROPOSED UXA-001A — Canonical-factor multi-placement.** A hierarchy
> placement references one canonical factor identity. One canonical factor may
> have multiple justified placements in different hierarchy contexts. Multiple
> placements do not create or alter an `OBS`, `CALC`, `FCST`, or `SCEN` claim;
> duplicate a source/evidence/derivation record; create independent analytical
> state; change reference calculation, provenance, rights, revision, or
> publication authority; or allow contradictory presentation of the same
> canonical state. Placement may affect navigation, surrounding context, a
> justified display-label override, and related-record suggestions only.

Parentage belongs to the placement record. A canonical factor has no mandatory
permanent navigation parent. Separately typed ontology relations may exist, but
they may not overload navigation parentage.

## 6. Proposed hierarchy/relationship separation requirement

> **PROPOSED UXA-001B — Hierarchy is not dependency.** A hierarchy tether means
> only parent/child navigation. It must remain visually and semantically distinct
> from an accepted structural relationship and from active propagation. A
> placement never proves causation, dependency, direction, weight, lag, or
> exposure. Structural connectors continue to require the lifecycle, evidence,
> provenance, Gate-B, and Human-QA authority defined by the applicable BINDING
> contracts.

R&D/test-fixture connectors remain visibly fixture-only and cannot satisfy this
requirement for factual output.

## 7. Proposed accessibility and progressive-disclosure requirement

> **PROPOSED UXA-001C — Equivalent bounded access.** The spatial exact-ten
> hierarchy has an equivalent keyboard-, touch-, and assistive-technology-
> operable list/search path. That path distinguishes exact-ten hierarchy
> placements, related records, and evidence; preserves parent context and
> canonical claim identity; and does not require hover, animation, or spatial
> position to understand membership. Progressive disclosure exposes one bounded
> hierarchy level or focused trace at a time; no ordinary view attempts to
> render the full theoretical `10 × 10` registry simultaneously.

This supplements rather than weakens current UX-004, UX-007, UX-024–UX-027,
UX-037–UX-041, and Motion/Interaction reduced-motion requirements.

## 8. Claim honesty

Hierarchy placement cannot create or alter analytical claims. Material claim
records retain exactly one governed class:

- `OBS`;
- `CALC`;
- `FCST`;
- `SCEN`.

The canonical claim, source evidence, state profile, reference, and derivation
remain authoritative. A placement may not make a CALC appear source-owned or
make fixture content factual.

## 9. Taxonomy completeness versus data coverage

The amended UI must keep two independent dimensions:

```text
taxonomy completeness
= approved canonical concepts and placements / exact required placements

current data coverage
= eligible current claims / approved factor claims at the snapshot cutoff
```

`10/10 taxonomy; 6/10 current data` is a complete taxonomy with partial data.
`6/10 concepts approved` is an incomplete taxonomy. Missing, stale,
rights-blocked, unavailable, and zero remain distinct.

## 10. Public Data Interface impact

No PDI amendment is proposed here.

The current PDI already supports versioned material claims, source/provenance
references, navigation nodes with child references, and namespaced additive
extensions that do not override core semantics. A future compatible extension
may define equivalents of:

- canonical factor registry;
- hierarchy placement registry;
- related-record collections;
- taxonomy completeness and data-coverage summaries;
- display/reference profile references.

`publicationClass` remains snapshot-owned under PDI-008. Item/placement-level
publication authority is prohibited. Concrete schema names and compatibility
tests require separate authorization. If later schema work cannot preserve
PDI-010 compatibility, that work must return with a specific amendment request.

## 11. Acceptance criteria for a future promoted amendment

1. A taxonomy-complete parent resolves to exactly ten child placements.
2. Fewer than ten approved concepts returns `TAXONOMY_INCOMPLETE`; no filler is
   created.
3. View All exposes no hierarchy child 11+ and labels all records by role.
4. Multiple placements of one factor resolve to one claim/state/provenance at a
   named snapshot/cutoff.
5. Placement changes do not change analytical truth or create duplicate claims.
6. Hierarchy tethers cannot be confused with factual structural connectors.
7. List/search access preserves exact-ten hierarchy, related-record, and
   evidence distinctions.
8. Progressive disclosure never renders the full theoretical registry.
9. Existing mode, provenance, information-class, fixture, accessibility, and
   reduced-motion requirements continue to pass.

## 12. Decision record

```text
Decision ID: UXA-001
Status: APPROVED / PROMOTED — TAYLOR, 2026-08-25
Result: Narrow exact-ten amendment semantics promoted into BINDING UI/UX 1.0.1.
```

Rationale: exact-ten and child-11/View-All semantics could not coexist with the
former BINDING wording without explicit amendment. Canonical-factor
multi-placement prevents the hierarchy correction from duplicating analytical
truth.

Rejected alternatives:

- silently reinterpret “at most ten” as exactly ten;
- retain child 11+ behind View All;
- duplicate canonical factors/claims for each parent;
- broaden this amendment into a general UI redesign.

Implementation consequence: none until a separately authorized Workstream-1
implementation sprint.

Contract consequence: `UI_UX_CONTRACT.md` 1.0.1 is BINDING and supersedes the
affected 1.0.0 semantics. This historical proposal has no independent authority.

## 13. Recommendation

**SUPERSEDED BY BINDING UI/UX CONTRACT 1.0.1.**

Do not implement exact-ten UI behavior, canonical registries, renderer changes,
or Workstream 1 from this historical artifact. Separate implementation
authorization remains required.
