# Phase-4A Human QA

`HUMAN_PHASE4A_QA = PENDING`

Coverage: **LIMITED_ENGINE_PROOF**

> This does not model the full economy and is not Gate-B evidence.

## Factual OBS inputs

| Observation | Value | Period | Series | Human evidence | Freshness / retrieval path |
|---|---:|---|---|---|---|
| Total nonfarm payroll employment | 158,858 thousand persons | 2026-07 | CES0000000001 | `data.bls.gov/timeseries/CES0000000001` | current / current |
| U-3 unemployment rate | 4.1% | 2026-07 | LNS14000000 | `data.bls.gov/timeseries/LNS14000000` | current / current |
| Labor-force participation rate | 61.4% | 2026-07 | LNS11300000 | `data.bls.gov/timeseries/LNS11300000` | current / current |
| Initial unemployment-insurance claims | 209,000 claims | week ending 2026-08-08 | DOL-UI-SA-INITIAL | `dol.gov/ui/data.pdf` | current / stale XML path |
| Job openings | 7,359 thousand | 2026-06 | JTS000000000000000JOL | `data.bls.gov/timeseries/JTS000000000000000JOL` | current / current |
| Hires | 5,348 thousand | 2026-06 | JTS000000000000000HIL | `data.bls.gov/timeseries/JTS000000000000000HIL` | current / current |

For all six: `stateType = OBS`; `AUXSAYS calculation = NONE`.

## Direct CALC state outputs

These CALCs are transparent identity mappings from one official OBS into one
named current-state component. They do not add a coefficient, direction,
forecast, or causal claim. Baseline is `NOT_APPLICABLE_DIRECT_STATE_MAPPING`.

| CALC | Input → method → output | Evidence | Derivation ID |
|---|---|---|---|
| Employment Level | Payrolls 158858 → DIRECT_IDENTITY_V1 → 158858 thousand persons | direct semantic mapping | `derivation:0c6f56516d80f270be759f862b84fc11baf49c4aab10160f865498d7a5ac4413` |
| Unemployment Rate | U-3 4.1 → DIRECT_IDENTITY_V1 → 4.1% | direct semantic mapping | `derivation:744561fca2520ef7f2b3cc05e45caa7c1d03f289847997a01fae6d2270e03553` |
| Participation Rate | Participation 61.4 → DIRECT_IDENTITY_V1 → 61.4% | direct semantic mapping | `derivation:135ecbf9e0b60b0cf50a6f0165cbd4542727267ffcaaa6bc07ef95152b1015ec` |
| Claims Separation Signal | Claims 209000 → DIRECT_IDENTITY_V1 → 209000 claims | direct semantic mapping; not causality | `derivation:d832cfa7eff23161d8169b45c53a97b359f2b7558bbe10e9e701fa9302110569` |
| Labor Demand Openings Signal | Openings 7359 → DIRECT_IDENTITY_V1 → 7359 thousand | direct semantic mapping | `derivation:210d5c52a181565a936c550fc14ac599d7a57e810575df076ab3dba64a213931` |
| Realized Hiring Flow | Hires 5348 → DIRECT_IDENTITY_V1 → 5348 thousand | direct semantic mapping | `derivation:18e6aa9f1ec68bbe74b9b53a5c267270db237f3cc87be94ce4cdce9c9aa87505` |

## Accepted proof relationships

`P4A-REL-001` through `P4A-REL-006` are the six OBS-to-state mappings above.
Each is `DIRECT`, `ACCEPTED`, U.S.-national, version 1.0.0, and accepted by the
repository-owned `P4A-DIRECT-MAPPING-RULE-1.0.0`. None links one labor indicator
to another or asserts causality.

## ENGINE MECHANICS TEST — NOT REAL ECONOMIC EVIDENCE

Synthetic input 10 units, synthetic buffer absorbs 4 units:

`10 input = 4 absorbed + 6 transmitted`

This fixture proves typed `PARTIALLY_ABSORBED` handling only. It is not a claim
about labor, a company, an industry, or the U.S. economy.

## Taylor check

1. Confirm the six OBS values/periods/series above match the accepted Phase-3 evidence.
2. Confirm each BLS human-evidence URL ends in its exact series ID, not the generic API endpoint.
3. Confirm acquisition provenance and methodology remain separately available for all six OBS.
4. Confirm every CALC says exactly which OBS it maps and that the value/unit did not change.
5. Confirm the DOL observation remains current while the XML retrieval path remains visibly stale.
6. Confirm no relationship claims one labor indicator caused another.
7. Confirm coverage says `LIMITED_ENGINE_PROOF`, Gate B OPEN, and no FCST/SCEN.

Review candidate: `phase4a-read-model-candidate.json`.
