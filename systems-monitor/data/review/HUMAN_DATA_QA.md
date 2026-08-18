# Phase-3 factual-data human QA

`HUMAN_DATA_QA = PENDING`

This is a local review artifact. The factual candidate is not activated on
AUXSAYS.com. Taylor should compare each row with the original authority linked
below and confirm value, unit, period, timing, and revision state.

| Indicator | Displayed value | Unit | Observation period | Source | Public time | Retrieved | Accepted | Vintage/revision | Health |
|---|---:|---|---|---|---|---|---|---|---|
| Total nonfarm payroll employment | 158,858 | thousands of persons | 2026-07 | BLS CES `CES0000000001` | conservative retrieval bound: 2026-08-18 19:44:00Z | 2026-08-18 19:44:00Z | 2026-08-18 19:46:00Z | retrieval vintage / 0 | current |
| U-3 unemployment | 4.1 | percent | 2026-07 | BLS CPS `LNS14000000` | conservative retrieval bound: 2026-08-18 19:44:00Z | 2026-08-18 19:44:00Z | 2026-08-18 19:46:00Z | retrieval vintage / 0 | current |
| Labor-force participation | 61.4 | percent | 2026-07 | BLS CPS `LNS11300000` | conservative retrieval bound: 2026-08-18 19:44:00Z | 2026-08-18 19:44:00Z | 2026-08-18 19:46:00Z | retrieval vintage / 0 | current |
| Initial UI claims | 209,000 | claims | week ending 2026-08-08 | DOL Weekly Claims | 2026-08-13 12:30:00Z | 2026-08-18 19:44:22Z | 2026-08-18 19:46:00Z | advance / 0 | current |
| Job openings | 7,359 | thousands | 2026-06 | BLS JOLTS `JTS000000000000000JOL` | conservative retrieval bound: 2026-08-18 19:44:00Z | 2026-08-18 19:44:00Z | 2026-08-18 19:46:00Z | retrieval vintage / 0 | current |
| Hires | 5,348 | thousands | 2026-06 | BLS JOLTS `JTS000000000000000HIL` | conservative retrieval bound: 2026-08-18 19:44:00Z | 2026-08-18 19:44:00Z | 2026-08-18 19:46:00Z | retrieval vintage / 0 | current |

## Original evidence

- BLS API: `https://api.bls.gov/publicAPI/v2/timeseries/data/`
  - retained runtime artifact SHA-256: `cd8b57f7de01b03b4558f2f7d83fb79e2d336859e1b7a39c91c23dbd43ef98e0`
- Current DOL release: `https://www.dol.gov/ui/data.pdf`
  - retained runtime artifact SHA-256: `7f046fea52e4b60b13c45c2a868b199ff9fe448e7289add2ff9300abd9cb0fa3`

BLS's current download does not independently prove each observation's
historical release time. The candidate therefore uses retrieval time as a
conservative public-availability bound and does not backdate from the
observation month.

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

1. Run the existing app development server.
2. Run `python systems-monitor/data/scripts/print_local_ui_loader.py` from the
   repository root and paste its one-line output into browser developer tools.
3. The command reloads the page. This switch is honored only by Vite development
   mode.
4. Confirm Summary and Verified Data display six factual OBS records and
   official provenance.
5. Confirm Outlook says `Forecast unavailable / not yet supported` and shows no
   forecast, scenario, rankings, events, or synthetic claims.
6. Remove the key to restore the Phase-2 fixture:
   `localStorage.removeItem("auxsays.localFactualCandidate")`.
