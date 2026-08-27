# Structural Graph Generation Plan

Status: **DESIGN / NO NEW FACTUAL ACCEPTANCE**

| Relationship class | Authority | Runtime role |
|---|---|---|
| `AUTHORITATIVE_DIRECT_REQUIREMENT` | BEA `CxIDRAR` | Traversable only after governed acceptance |
| `INDUSTRY_PRODUCES_COMMODITY` | Future approved BEA Make/`IxCMSAR` rule | Missing industry→commodity handoff |
| `TOTAL_REQUIREMENT_BENCHMARK` | BEA `IxCTRAR` | Non-recursive benchmark only |
| `CURRENT_STATE_ATTACHMENT` | EIA/BLS OBS | Context only unless separately authorized |
| `CURRENT_EMPLOYMENT_EXPOSURE` | Accepted paths + OBS → AUXSAYS CALC | Current/as-of only, never forecast |
| `TEST_FIXTURE_RELATIONSHIP` | Repository fixture | Never accepted or published |

Direct requirements may define immediate topology. Total requirements already
contain indirect effects and must never be recursively added to accumulated
direct paths. Current code enforces this in Phase-4B configuration,
`structural.py`, the live runner, and tests.

The factual multi-stage graph remains blocked because commodity→industry direct
requirements do not supply an industry→commodity output handoff. Equal codes
cannot bridge namespaces. A later reviewed generator must resolve BEA Make and
production-share products from live metadata, preserve source-cell and measure
semantics, run its own acceptance lifecycle, and keep `IxCMSAR` production share
distinct from substitution evidence.

Common-origin IDs must survive branching. Overlapping paths are reconciled by
an approved cap/overlap rule or return an unresolved warning. Current EIA/BLS
observations remain context attachments; there is no approved OBS-to-pressure
transformation or factual employment-exposure CALC.

BLS BED is a useful future quarterly context bridge for gross job gains/losses
and establishment openings/expansions/closings/contractions. It does not replace
the BEA industry-output handoff and may not become a propagation seed without a
separately approved transformation.

Gate B remains open; accepted factual structural relationship count remains 0.
