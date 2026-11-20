# Layoffs Level-4 Classification Complete

Status: **COMPLETE REVIEW CANDIDATE — NO DATA OR RELATIONSHIP PROMOTION**

All 64 canonical Layoffs Level-4 factors are now explicitly classified:

| Claim class | Count |
|---|---:|
| A — direct official observation | 38 |
| B — deterministic AUXSAYS calculation | 12 |
| C — event or structural factor | 5 |
| D — taxonomy or source problem | 9 |
| Unclassified | 0 |

The authoritative row-level registry is `data/config/layoffs/level4_claim_classes.json`. The generated canonical/source reconciliation, including placement paths and source state, is `data/config/layoffs/level4_source_profile_roles.json`.

## Decisions on known problem families

- **Productivity / Automation — D.** Official productivity observations do not measure automation. The identity must be split before sourcing.
- **Industry Credit Conditions — D.** Aggregate SLOOS evidence does not support an industry-granular title.
- **Sales / Revenue — D.** M3 shipments and MARTS retail sales have incompatible scopes; neither is a universal sales/revenue series.
- **Consumer Demand — D.** Demand is a latent concept and cannot be silently equated with PCE or retail sales.
- **Consumer Spending — A.** BEA PCE is a direct official observation after exact table/line/price-basis selection.
- **Corporate Profitability — B.** Profitability is a governed ratio; it is not synonymous with corporate profits.
- **Corporate Profits — A.** BEA publishes the level directly after exact NIPA selection.
- **Energy / Input Shock — B.** “Shock” requires a baseline and threshold applied to an accepted underlying series.
- **Disaster / Weather / Operational Shock — C.** FEMA/NOAA provide event records; economic exposure requires a governed geographic and temporal join.
- **Import / Trade Pressure — B.** Pressure requires a defined denominator, product scope, crosswalk, and deterministic formula.
- **Trade / External Shock — C.** This is an event/structural concept, not a universal scalar observation.
- **Input Costs and Producer Input Costs — D.** Both are under-scoped and conflate price indexes with realized cost. Producer Input Prices remains the neutral Class-A candidate.
- **Inventory / Sales Imbalance — D.** It duplicates the neutral balance/ratio concepts while embedding an unsupported adverse interpretation.

## Classification is not acceptance

Class A means an official authority publishes the measurement directly. It does not mean:

- the exact selector is accepted;
- rights are accepted;
- an observation or history is accepted;
- a current value can be shown;
- hierarchy implies influence;
- materiality or destination impact is governed.

`observationPromotionAuthority` and `relationshipPromotionAuthority` remain `NONE`. Human Level-4 QA remains pending.
