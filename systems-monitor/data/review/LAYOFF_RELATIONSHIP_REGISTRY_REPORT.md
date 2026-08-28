# Layoffs & Job Destruction Relationship Registry Report

Status: local review only; no relationship is accepted or publication-eligible.

## Counts

| Class | Count | Lifecycle |
| --- | ---: | --- |
| Outcome → Level-1 hierarchy tether | 1 | `HIERARCHY_ONLY` |
| Level-1 → Level-2 hierarchy tether | 10 | `HIERARCHY_ONLY` |
| Level-2 → Level-3 hierarchy tether | 100 | `HIERARCHY_ONLY` |
| Measurement candidate | 1 | `CANDIDATE` |
| Accounting-definition candidates | 3 | 2 `VALIDATED`, 1 `CANDIDATE` |
| Leading-signal candidate | 1 | `CANDIDATE` |
| Pressure-channel hypothesis | 1 | `CANDIDATE` |
| Accepted/traversable semantic relationships | **0** | — |

## Guarded semantics

- Initial Claims measure new insured-unemployment entry; they are not job-destruction accounting.
- Establishment contractions and closures are the two BLS BED components of Gross Job Losses. The two edges remain `NOT_ACCEPTED` pending Taylor relationship acceptance.
- Business bankruptcy filings are a stress signal, not layoffs, firm death, or establishment closure.
- Gross Job Losses are only the negative side of the BED accounting identity. Gross Job Gains from expansions and openings must remain visible before connecting the result to Net Employment Change.
- Every hierarchy tether is navigation only. It conveys no causal direction, weight, propagation, or acceptance.

## Registry authority

Machine registry: `systems-monitor/data/config/layoffs/relationships.json`

Relationship lifecycle and evidence fields follow the BINDING Dependency Relationship Contract. Nothing in this review package promotes a relationship or closes Gate B.
