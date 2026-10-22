# Phase-4B Gate-B Evidence

Status: **LIVE RUNNER READY / EXECUTION BLOCKED — BEA CREDENTIAL REQUIRED**
Human QA: **PENDING**  
Gate B: **OPEN**  
Activation: **LOCAL REVIEW ONLY**

## What is implemented and verified

| Surface | Result | Evidence |
|---|---|---|
| BEA metadata method | PASS | `InputOutput` uses `GetParameterValues` for `TableID` and `Year`; no production TableID is hard-coded |
| Live orchestration | PASS | `data/run_phase4b_live.py` wires metadata → resolved products → bounded data → sanitized immutable capture → parser → generation → promotion → review artifacts |
| BEA secret handling | PASS | External 36-character `AUXSAYS_BEA_USER_ID`; URL redaction and malformed-key tests |
| BEA parser | PASS | Strict bounded JSON envelope, table/year/unit identity, COMMODITY/INDUSTRY namespaces, duplicate rejection, missing-is-not-zero |
| Direct vs. total | PASS | `CxIDRAR` topology; `IxCTRAR` non-recursive benchmark only; double-count configuration fails |
| BEA concordance | PASS | Official 2017-NAICS workbook; SHA-256 `6E25267FF60CCEDC0808C14153B0CDEB566A7F5E9097536C70C2B9694EF5FF47`; 61,081 bytes; no macros, formulas, or external links executed |
| 484 bridge | PASS | Versioned 2017 NAICS 484 → 2022 NAICS 484 unchanged aggregate; exact BLS endpoint `CES4348400001` |
| BLS 484 current OBS | PASS | July 2026 `1465.1` thousand, seasonally adjusted, preliminary; exact series page retained separately from API acquisition |
| EIA inventory OBS | PASS | Week ending 2026-08-14, U.S. commercial crude excluding SPR `428.815` million barrels; `BUFFER_AVAILABLE` relative to prior week |
| EIA capacity OBS | PASS | Week ending 2026-08-14, U.S. refinery utilization `97.2%`; configured ordinal assessment `HEADROOM_CONSTRAINED` |
| Replay selector | PASS | Separate public-release and operationally-known cutoffs; current artifact cannot leak into an earlier cutoff |
| Read model | PASS, blocked candidate | Bounded coverage warning, three OBS, no accepted relationship or CALC invented, `FCST`/`SCEN` absent |
| Recurring cost | PASS | `$0` |

## Immutable retained source evidence

| Artifact | SHA-256 | Bytes | Source |
|---|---:|---:|---|
| BEA Industry and Commodity Codes and NAICS Concordance | `6E25267FF60CCEDC0808C14153B0CDEB566A7F5E9097536C70C2B9694EF5FF47` | 61,081 | BEA |
| BLS `CES4348400001` API response | `4D64C6EB7E1D0E764812002EFB2301B980D2B249159D7099AEBF573B497D28FE` | 807 | BLS |
| EIA WPSR table 2 | `304FCB173D22E9AF933295D716D3CFC07B7EB475995A8C8A5C1F7628B6A0AFB7` | 8,367 | EIA |
| EIA WPSR table 4 | `9A6F6A3D12FB4A844271B7566E4C714E34BC9BFE7041DD287BFD5236CDF94341` | 2,324 | EIA |

Total retained source bytes: **72,579**.

## Rights

- BEA API retrieval: `ALLOW`.
- BEA immutable retention: `ALLOW_WITH_ATTRIBUTION_AND_TERMS_FINGERPRINT`.
- BEA transformation and clear AUXSAYS-derived relationship publication:
  `ALLOW` with attribution.
- Raw BEA bulk redistribution: `DENY_NOT_REQUIRED`.
- Interactive BEA application scraping: `DENY`; scheduled retrieval is API-only.
- EIA and BLS retained government evidence remains attributed and source-linked.

BEA attribution: “This product uses the Bureau of Economic Analysis (BEA) Data
API but is not endorsed or certified by BEA.”

## Current structural acceptance result

`AUXSAYS_BEA_USER_ID` was not present. Therefore:

- current live `CxIDRAR` and `IxCTRAR` TableIDs were **not discovered**;
- no live BEA matrix was retrieved;
- no test-fixture TableID or coefficient was promoted;
- accepted structural relationship count is **0**;
- factual common-cause topology result is **not yet available**;
- downstream structural employment-exposure CALC is **not yet available**;
- lag remains `UNKNOWN_NOT_ZERO_PENDING_ACCEPTED_STRUCTURAL_RUN`;
- substitution remains `NO_PROVEN_SUBSTITUTE`; no numeric attenuation is used.

This is the required fail-closed behavior, not a Gate-B pass.

The executable invocation is:

```text
python systems-monitor/data/run_phase4b_live.py --data-root systems-monitor/data --review-root systems-monitor/state/review
```

The real no-credential invocation returned `BLOCKED_LIVE_BEA_CREDENTIAL` with
exit code 2. It made no BEA request and created no live evidence or candidate.
On a credentialed run, BEA response envelopes are canonicalized with echoed
UserID fields redacted before immutable persistence; the secret-bearing wire
response exists only inside the request boundary.

## Tests and performance

- Python data/state suite: **205 passed**.
- UI regression suite: **76 passed**.
- Candidate build: approximately **139 ms** local wall time.
- Read-model candidate: **4,682 bytes**.
- Live BEA requests: **0**.
- Retained bounded source requests/artifacts: BEA concordance 1, EIA 2, BLS 1.

## Required closure action

Supply the BEA UserID only through `AUXSAYS_BEA_USER_ID`, then execute the
implemented bounded live metadata/retrieval acceptance path. External review
must verify the exact live TableIDs, 2024 availability, accepted 12–40 direct
relationships, factual
484 convergence/common-cause behavior, and the resulting ordinal current
employment-exposure CALC. Taylor must then perform Human Phase-4B QA. Gate B
must remain open until both steps pass.
