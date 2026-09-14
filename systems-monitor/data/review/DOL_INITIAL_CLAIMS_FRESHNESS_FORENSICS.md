# DOL Initial Claims freshness forensics

Forensic date: 2026-09-14

Status: **structured source remains stale; identity defect repaired; no value
manually injected; zero rows promoted.**

## Root cause

The collector did not truncate, misparse, paginate, filter, or misdate newer
observations. The official `r539cyNational` XML returned all 52 calendar rows,
but its populated seasonally adjusted claims data stopped at 2026-08-15.
Rows for 2026-08-22, 2026-08-29, and 2026-09-05 existed with blank/NBSP claims
cells. The parser correctly skipped those empty values.

The primary blocker is therefore a lagging/degraded official structured
endpoint. DOL's claims page also reports database technical issues. The current
DOL weekly PDF was available and reported 2026-09-05, but this repository has
no accepted deterministic standard-library parser for that PDF. The structured
XML remains the history/backfill lane until a release-artifact intake is
separately implemented and validated.

## Repo-owned defect and repair

The XML `rundate` was previously treated as a weekly release identity. A
read-only replay on 2026-09-14 returned the same 33 populated Initial Claims
weeks and the same values as the 2026-09-10 artifact; only `rundate` changed.
It is a report-execution date, not a release/vintage identity.

The parser now:

- derives a stable, content-addressed structured-snapshot identity from
  populated series/period/value tuples;
- records the report run date separately;
- prevents unchanged daily executions from manufacturing false releases or
  revisions; and
- classifies r539cy observations as `current_revised_snapshot` instead of
  falsely calling the newest populated stale row `advance`.

Freshness continues to fail closed at the governed 336-hour threshold. The
threshold was not increased.

## Retrieval result

| Item | Result |
|---|---|
| Stored XML retrieval | 2026-09-10T00:58:12.132990Z |
| Stored XML report run date | 2026-09-10 |
| Read-only replay date | 2026-09-14 |
| Stored and replayed newest populated Initial Claims period | 2026-08-15 |
| Stored and replayed newest populated value | 207,000 seasonally adjusted claims |
| Stored observation age | 624.97 hours |
| Governed stale threshold | 336 hours |
| Structured source freshness | `STALE` |
| Newest official period verified in the current DOL weekly release | 2026-09-05 |
| Newest official value verified | 206,000 seasonally adjusted claims |
| Newest acquired/promotable period | 2026-08-15 |
| Newly promoted rows | 0 |

The current official release also reports 207,000 for 2026-08-29 after revision
and 204,000 for 2026-08-22. These values are forensic cross-checks only; they
were not injected into accepted history.

## Remaining blocker

Implement a deterministic intake for the immutable DOL weekly release/archive
artifact, with an actual publication/release identity, then cross-check the
r539cy history lane and promote only through the existing Taylor-authorized
acceptance rule. Until then, the UI must continue to distinguish accepted
historical data from the stale current-source state.
