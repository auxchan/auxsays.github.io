# Human Level-4 Initial UI Claims QA

Status: **PENDING**

Review URL: `http://127.0.0.1:4173/systems-monitor/#layoffs-level4-qa`

Authority boundary: this surface is prepared for Taylor's review. It does not self-approve Level-4 content, calculations, sources, relationships, materiality, or forecasting.

## What to review

The surface presents exactly ten Initial UI Claims placements:

1. Layoffs & Discharges — accepted existing JOLTS history reuse.
2. Temporary Layoffs — accepted existing CPS history reuse.
3. Permanent Job Losers — accepted existing CPS history reuse.
4. Payroll Contraction Breadth — governed calculation pending Taylor's methodology decision.
5. Gross Job Losses — accepted existing BED history reuse.
6. Jobs Lost at Establishment Deaths — accepted existing BED history reuse through the canonical migration.
7. Business Bankruptcy Filings, 12-Month Total — exact U.S. Courts F-2 selector, pending rights and immutable history acceptance.
8. Real Output Growth — exact BEA NIPA T10101 line 1 selector, blocked on `AUXSAYS_BEA_USER_ID` and history acceptance.
9. Real Personal Consumption Expenditures Growth — exact BEA NIPA T10101 line 2 selector, blocked on `AUXSAYS_BEA_USER_ID` and history acceptance.
10. FEMA Disaster Declaration — bounded OpenFEMA event semantics, pending source and immutable event-history acceptance.

Verify identity, placement, canonical reuse, evidence class, source/provenance, accepted factual state or exact blocker, calculation methodology state, event semantics, and the absence of fixture or causal language.

## Guardrails visible on the surface

- Unexplained renderer fixtures: **0**.
- Accepted structural relationships: **0**.
- Gate B: **OPEN**.
- Forecasting: **LOCKED / unavailable**.
- FEMA is presented as an event, not a scalar observation, direction, or outcome claim.

Record `HUMAN_LEVEL4_INITIAL_UI_CLAIMS_QA = PASS` only through a later explicit Taylor approval checkpoint.
