# Layoffs Class-A History Activation

Status: **LIVE CANDIDATE HISTORY ACQUIRED; ACCEPTANCE BLOCKED BY GOVERNANCE**

Run time: `2026-09-10T00:58:12.166444Z` (UTC)

The existing bounded collector retrieved official BLS and DOL history into the gitignored local runtime. Raw evidence is content-addressed and the candidate batch is explicitly non-publishable.

## Retrieval result

| Result | Count |
|---|---:|
| Candidate observations | 282 |
| Source series | 19 |
| Existing Class-A factors covered | 12 |
| Candidate observations for those 12 factors | 200 |
| Newly accepted observations | 0 |
| Factors with accepted comparable history | 0 |

Raw artifacts:

| Source | Content type | Bytes | SHA-256 |
|---|---|---:|---|
| BLS combined Public Data API response | `application/json` | 21,157 | `4201b82a3e69ec36d022f8f01fef26addc754272b9d0d2d4c86399ea89873882` |
| DOL national UI claims XML | `text/xml` | 18,766 | `40710934ba4bae3b132e99c15fd092e4f7e5eab0840f330f630b03272be91f6c` |

The raw bodies and batch remain under `systems-monitor/data/local/layoffs-runtime/`, which is intentionally gitignored. They contain no credentials.

For this live batch, the collectors conservatively use retrieval time as the public-availability bound when an exact per-release publication timestamp is not joined into the candidate. Historical acceptance and replay must not claim that an observation was available earlier than that bound unless a governed official release-calendar mapping is added.

## Class-A coverage acquired

| Canonical factor | Exact series | Native cadence | Candidate periods | Candidate rows |
|---|---|---|---|---:|
| Average Weekly Hours | `CES0500000002` | Monthly | 2025-01 → 2026-08 | 20 |
| Establishment Closures | `BDS0000000000000000110006LQ5` | Quarterly | 2025-Q1 → 2025-Q4 | 4 |
| Establishment Contractions | `BDS0000000000000000110005LQ5` | Quarterly | 2025-Q1 → 2025-Q4 | 4 |
| Establishment Deaths | `BDS0000000000000000110008LQ5` | Quarterly | 2025-Q1 only | 1 |
| Gross Job Losses | `BDS0000000000000000110004LQ5` | Quarterly | 2025-Q1 → 2025-Q4 | 4 |
| Hires Rate | `JTS000000000000000HIR` | Monthly | 2025-01 → 2026-07 | 19 |
| Initial Claims | `DOL-UI-SA-INITIAL` | Weekly | 2026-01-03 → 2026-08-15 | 33 |
| Job Openings Rate | `JTS000000000000000JOR` | Monthly | 2025-01 → 2026-07 | 19 |
| Layoffs & Discharges | `JTS000000000000000LDL`, `JTS000000000000000LDR` | Monthly | 2025-01 → 2026-07 | 38 |
| Permanent Job Losers | `LNS13026638` | Monthly | 2025-01 → 2026-08 | 19 |
| Temporary Help Employment | `CES6056132001` | Monthly | 2025-01 → 2026-08 | 20 |
| Temporary Layoffs | `LNS13023653` | Monthly | 2025-01 → 2026-08 | 19 |

The remaining 82 candidate rows are DOL continued-claims/IUR context and BED gain/opening inputs. They are not silently treated as the 12 Class-A Level-4 histories.

## Implemented historical backbone

`layoffs_history.py` now provides:

- canonical alias normalization before acceptance;
- fail-closed, explicitly listed acceptance rules;
- immutable observation identities and object hashes;
- release/vintage preservation and revision supersession;
- public-availability, AUXSAYS-operational-knowledge, and latest-revised replay modes;
- native-cadence comparable pairs with strict unit/geography/adjustment/source compatibility;
- factual absolute and percent deltas and direction only when two accepted compatible periods exist;
- materiality `UNKNOWN` until an authorized threshold profile exists;
- deterministic, non-causal interpretation sections;
- atomic accepted-history artifacts.

## Exact blocker

The production acceptance ledger is intentionally closed:

- `authority: NONE`
- `defaultDecision: REJECT_UNLESS_EXPLICITLY_LISTED`
- zero acceptance rules
- routine auto-promotion disabled

The prior Initial Claims acceptance covers one 2026-08-08 observation only and explicitly does not authorize historical backfill or later releases. The live 282-row batch therefore remains candidate evidence. Showing it as accepted would violate the current BINDING governance and the source registry’s acceptance scope.

The smallest next approval is an initial-calibration acceptance decision for the 13 exact series serving these 12 factors, including rights, unit, geography, seasonal adjustment, cadence, effective date, and routine-release policy. After that one governed decision, the repo-owned collector and history runner can operate without weekly/monthly manual value entry.
