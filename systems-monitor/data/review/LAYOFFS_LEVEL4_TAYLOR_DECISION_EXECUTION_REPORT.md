# Layoffs Level-4 Taylor Decision Execution Report

Authority: `TAYLOR_LAYOFFS_LEVEL4_ACCEPTANCE_2026_09_11`

Execution time: 2026-09-11

Status: locally implemented and validated; Human QA required; no push, merge, or deployment performed.

1. **Accepted observations:** 188 immutable observations are active: 76 BLS JOLTS, 38 BLS CPS, 40 BLS CES, and 34 DOL UI records. The DOL total includes the preserved 209,000 seed and 33 promoted current/revised records.

2. **Accepted canonical factors:** Eight canonical factors now have bounded descriptive histories: Layoffs and Discharges, Job Openings Rate, Hires Rate, Permanent Job Losers, Temporary Layoffs, Average Weekly Hours, Temporary Help Employment, and Initial Claims.

3. **Comparable history:** All eight accepted factors have compatible prior observations. Nine exact accepted series are represented because Layoffs and Discharges is backed by two governed JOLTS series.

4. **Factual direction/delta:** Direction and arithmetic delta are available for all eight factors. These outputs remain descriptive and do not assert economic materiality, influence, causality, or destination impact.

5. **DOL revision chain:** One explicit chain is active for `DOL-UI-SA-INITIAL`, period 2026-08-08: accepted seed 209,000 (revision 0) is superseded by 212,000 (revision 1). The original accepted value remains immutable.

6. **DOL release/freshness result:** Release identity is source-stable as `DOL-UI-r539cyNational-2026-09-10`. The audited retrieval is `STALE`: newest observation 2026-08-15, retrieval 2026-09-10T00:58:12.13299Z, age 624.97 hours, governed threshold 336 hours. The routine rule is active but future promotion fails closed until a current retrieval passes the freshness gate.

7. **BED disposition:** Exact central `bls-bed` rights are resolved for collection, parsing, validation, internal storage, and public display. Model-feature and model-training use remain `UNKNOWN`. No BED observation is accepted because Taylor acceptance authority has not been granted; all 13 BED candidates remain deferred.

8. **Vintage qualification:** Zero observations are forecast vintages. Current/revised backfill is never relabeled as forecast vintage, and no forecasting output was activated.

9. **Materiality:** `UNKNOWN` for every accepted factor. No threshold, confidence tier, or material-change claim was invented.

10. **Structural relationships:** Zero accepted structural relationships were added. Hierarchy placement remains orientation only and does not become evidence of causality, influence, or propagation.

11. **Gate B:** `OPEN; descriptive history activated, structural acceptance unchanged`. This is data and evidence progress only, not a forecasting or connector-signal milestone.

12. **Idempotency:** A second activation pass accepted zero new observations and did not rewrite history. Existing observation identities and revision links remained stable.

13. **Validation:** 259 Python data tests and 252 application tests pass. Production build, type-check, asset-manifest validation, and the performance budget pass.

14. **Repository boundary:** Changes are limited to the Taylor-authorized acceptance ledger, DOL deterministic repairs, exact BED rights policy, immutable accepted-history artifacts, bounded factual read models/UI, and their tests. The unrelated review-harness packages and pre-existing untracked media are excluded from this work. Human QA is the next required boundary.

Primary machine-readable evidence:

- `layoffs-accepted-history.json`
- `layoffs-history-activation-report.json`
- `layoffs-history-idempotency-report.json`
- `layoffs-acceptance-simulation.json`
