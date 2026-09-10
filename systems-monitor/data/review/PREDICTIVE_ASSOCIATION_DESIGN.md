# Predictive-Association Design

Status: **DESIGN ONLY — PHASE 5 REMAINS LOCKED**

## Four relationship meanings remain separate

| Kind | Meaning | Traversable for structural propagation? | Accepted in this sprint? |
|---|---|---|---|
| Hierarchy | Organized under / drill into | No | Existing navigation only |
| Structural relationship | Versioned authoritative dependency or exposure | Only after acceptance | No |
| Accounting relationship | Deterministic identity or reconciliation | Only under its own accepted rule | No |
| Predictive association | Historically useful for a defined target without implying causation | No | No |

The current structural relationship schema must not be stretched to accept predictive associations. It lacks target/horizon contracts, vintage-aware training cutoffs, lag-search controls, baseline comparison, out-of-sample skill, calibration, and regime-stability evidence.

## Future sibling schema

A predictive association should have a separate registry and lifecycle with at least:

- stable association ID and version;
- feature factor/series identities;
- target contract and horizon;
- geography, population, units, and cadence;
- feature availability lag and target realization lag;
- training, validation, and test cutoffs by knowledge time;
- exact vintage snapshot IDs;
- missing-data and revision policy;
- lag-search and multiple-testing controls;
- naive baseline IDs and scores;
- out-of-sample skill and calibration metrics;
- regime/stability checks;
- limitations and prohibited causal wording;
- acceptance authority and lifecycle;
- `structuralPropagationEligible: false`.

## Candidate future targets

- **Industry employment contraction — 3 months:** probability that the accepted industry employment level is lower three native monthly observations after the forecast origin.
- **Industry employment contraction — 6 months:** the same target at six months.
- **Employment growth — 3/6/12 months:** continuous percent change in a definition-compatible accepted employment series.
- **Hiring weakness regime:** a governed classification built from accepted hiring, openings, and employment observations with an explicitly versioned threshold rule.

All targets must use the vintage that was publicly or operationally available at forecast origin. Revised future values cannot leak into historical features.

## Required naive baselines

Every later model must beat appropriate simple baselines before it can be considered useful:

1. historical base rate;
2. persistence/no-change;
3. recent native-cadence trend;
4. moving average;
5. simple autoregression.

No production model, probability, Outlook state, career recommendation, or public forecast is created by this sprint.
