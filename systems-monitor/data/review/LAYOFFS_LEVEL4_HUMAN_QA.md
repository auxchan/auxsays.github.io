# Layoffs Level-4 Human QA

Status: `HUMAN_LEVEL4_LAYOFFS_QA = PENDING`

Local review URL:

`http://127.0.0.1:4173/systems-monitor/__local-review/layoffs-level4`

Start the loopback-only review server from `systems-monitor/app` with:

`npm run dev:layoffs-qa`

## Review boundary

This is a Human-QA package, not an approval. The surface is built from the 188
Taylor-accepted immutable observations and exposes eight canonical factors and
nine governed exact series. It contains factual comparisons only. Node titles
remain identity-only. Forecast-vintage observations and accepted structural
relationships remain zero.

The Initial Claims section deliberately labels 207,000 for 2026-08-15 as
**accepted historical data**, not the current national reading. The current
structured DOL source is stale even though the accepted history remains valid.

## Eight-factor temporal state

| Canonical factor | Exact series | Accepted current | Previous comparable | Factual direction / delta | History/source state |
|---|---|---:|---:|---|---|
| Layoffs and Discharges | `JTS000000000000000LDL` | 1,666 thousand persons, 2026-07 | 1,785, 2026-06 | ↓ −119 | Accepted descriptive history |
| Layoffs and Discharges | `JTS000000000000000LDR` | 1.0%, 2026-07 | 1.1%, 2026-06 | ↓ −0.1 percentage point | Accepted descriptive history |
| Job Openings Rate | `JTS000000000000000JOR` | 4.4%, 2026-07 | 4.3%, 2026-06 | ↑ +0.1 percentage point | Accepted descriptive history |
| Hires Rate | `JTS000000000000000HIR` | 3.2%, 2026-07 | 3.4%, 2026-06 | ↓ −0.2 percentage point | Accepted descriptive history |
| Permanent Job Losers | `LNS13026638` | 1,777 thousand persons, 2026-08 | 1,715, 2026-07 | ↑ +62 | Accepted descriptive history |
| Temporary Layoffs | `LNS13023653` | 839 thousand persons, 2026-08 | 921, 2026-07 | ↓ −82 | Accepted descriptive history |
| Average Weekly Hours | `CES0500000002` | 34.4 hours, 2026-08 | 34.3, 2026-07 | ↑ +0.1 hour | Accepted descriptive history |
| Temporary Help Employment | `CES6056132001` | 2,519.5 thousand persons, 2026-08 | 2,512.7, 2026-07 | ↑ +6.8 | Accepted descriptive history |
| Initial Claims | `DOL-UI-SA-INITIAL` | 207,000 claims, 2026-08-15 | 212,000, 2026-08-08 | ↓ −5,000 | Accepted history; current structured source `STALE` |

Initial Claims also exposes the accepted 2026-08-08 revision chain:
209,000 revision 0 → 212,000 revision 1.

## Taylor checklist

For each factor, verify without self-marking PASS:

- Is the canonical factor identity clear?
- Does the accepted value match its official evidence?
- Is the previous observation comparable by cadence, unit, geography, source,
  and seasonal-adjustment state?
- Is the factual arrow correct?
- Is the arithmetic delta correct?
- Is the represented period understandable?
- Is accepted history kept distinct from current source freshness?
- Are revisions clear without overwhelming the primary reading?
- Are source provenance and evidence status discoverable?
- Does the map keep hierarchy lines from becoming analytical claims?
- Is the inspector concise?
- Do the expanded history and methodology sections contain enough technical
  evidence?

For Initial Claims, additionally verify that the stale warning prevents the
2026-08-15 accepted value from being read as the current national value.
