# Phase-3 factual-data human QA

`HUMAN_DATA_QA ROUND 2 = CORRECTIONS APPLIED — TAYLOR RE-REVIEW REQUIRED`

This is a local review artifact. The factual candidate is not activated on
AUXSAYS.com. Taylor should compare each row with the original authority linked
below and confirm value, unit, period, timing, and revision state.

## Verdict history

- **Round 1 — FAIL.** Official series IDs were not visible; original factual
  evidence links were not reachable; factual Outlook retained a
  synthetic-fixture disclaimer; and the DOL revision proof was absent from the
  UI.
- **Round 2 — corrections applied; Taylor re-review required.** Verified Data
  now exposes per-observation series IDs, separately labeled source/data and
  methodology links, and a progressive DOL replay proof. The human evidence
  links target each exact official BLS series page while the BLS API remains
  recorded as retrieval provenance. Factual Outlook no longer reuses
  fixture-only warning content. This record does **not** claim Human Data QA
  PASS.

| Indicator | Value / unit | Period | Official source / series | Official release | AUXSAYS retrieved / accepted | Version / health |
|---|---|---|---|---|---|---|
| Total nonfarm payroll employment | 158,858 thousand persons | 2026-07 | BLS CES `CES0000000001` | 2026-08-07 12:30Z | 2026-08-18 19:44:00Z / 19:46:00Z | revision 0; current |
| U-3 unemployment | 4.1 percent | 2026-07 | BLS CPS `LNS14000000` | 2026-08-07 12:30Z | 2026-08-18 19:44:00Z / 19:46:00Z | revision 0; current |
| Labor-force participation | 61.4 percent | 2026-07 | BLS CPS `LNS11300000` | 2026-08-07 12:30Z | 2026-08-18 19:44:00Z / 19:46:00Z | revision 0; current |
| Initial UI claims | 209,000 claims | week ending 2026-08-08 | DOL `DOL-UI-SA-INITIAL` | 2026-08-13 12:30Z | 2026-08-18 19:44:22Z / 19:46:00Z | advance; observation current; XML path stale at 2026-07-18 |
| Job openings | 7,359 thousand | 2026-06 | BLS JOLTS `JTS000000000000000JOL` | 2026-08-04 14:00Z | 2026-08-18 19:44:00Z / 19:46:00Z | revision 0; current |
| Hires | 5,348 thousand | 2026-06 | BLS JOLTS `JTS000000000000000HIL` | 2026-08-04 14:00Z | 2026-08-18 19:44:00Z / 19:46:00Z | revision 0; current |

## Original evidence

- BLS retrieval API: `https://api.bls.gov/publicAPI/v2/timeseries/data/`
  - Payrolls: `https://data.bls.gov/timeseries/CES0000000001`
  - U-3 unemployment: `https://data.bls.gov/timeseries/LNS14000000`
  - Participation: `https://data.bls.gov/timeseries/LNS11300000`
  - Job openings: `https://data.bls.gov/timeseries/JTS000000000000000JOL`
  - Hires: `https://data.bls.gov/timeseries/JTS000000000000000HIL`
  - Employment Situation July 2026 schedule: `https://www.bls.gov/schedule/2026/home.htm`
  - JOLTS release schedule: `https://www.bls.gov/schedule/news_release/jolts.htm`
  - retained runtime artifact SHA-256: `cd8b57f7de01b03b4558f2f7d83fb79e2d336859e1b7a39c91c23dbd43ef98e0`
- Current DOL release: `https://www.dol.gov/ui/data.pdf`
  - retained runtime artifact SHA-256: `7f046fea52e4b60b13c45c2a868b199ff9fe448e7289add2ff9300abd9cb0fa3`

The official BLS schedules establish 08:30 ET for the July Employment
Situation and 10:00 ET for June JOLTS. These source-publication times remain
separate from AUXSAYS retrieval and acceptance.

## Factual DOL revision proof

For week ending 2024-03-02:

- Release A, 2024-03-07 08:30 ET: advance initial claims `217,000`.
  - `https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/20240471.pdf`
  - SHA-256 `2759aeb9fc6ef115d865012745d82e7ee024b5c1be0f5b73a37016fcd8d2cb5e`
- Release B, 2024-03-14 08:30 ET: revised the same week to `210,000`.
  - `https://www.dol.gov/sites/dolgov/files/OPA/newsreleases/ui-claims/20240527.pdf`
  - SHA-256 `314084cfb6bba80f30b36c9b6755563d3090e0669c94bd540f11b1ce33f517d7`

Replay expectations proven by deterministic tests:

- latest revised truth: `210,000`
- publicly available as of 2024-03-10: `217,000`
- operationally known before Release B was accepted: `217,000`

The complete normalized evidence record is
`tests/fixtures/dol_revision_pair.json`. Original PDFs are retained only under
the ignored `local/` runtime boundary.

## Local UI review

1. Open the prepared local factual-candidate preview supplied in the review
   handoff. No JSON, SQLite, console, or developer-tools inspection is required.
2. Confirm Summary and Verified Data display the six rows above with reachable
   original evidence and concise, collapsible provenance details.
3. Confirm every factual row identifies its exact official series ID and keeps
   source/data evidence distinct from methodology.
4. Expand the DOL revision/replay example and confirm both original releases,
   `217,000` as known March 10, and `210,000` as latest revised truth.
5. Confirm Outlook says `Forecast unavailable / not yet supported` and shows no
   forecast, scenario, rankings, events, or synthetic claims.

## Deferred master-system UI debt

Taylor's broader concern that the current experience feels like a factor
inspector rather than an interconnected master system is accepted but is not a
Phase-3 blocker. System-level overview, cross-system interconnectivity,
dependency navigation, cascade/propagation inspection, stronger hierarchy, and
the comprehensive UI/UX overhaul remain deferred until governed State,
Dependency, and Allocation relationship data exists. Decorative relationship
lines must not be fabricated in advance of that machinery.
