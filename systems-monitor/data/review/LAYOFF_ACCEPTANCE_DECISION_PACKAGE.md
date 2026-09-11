# Layoffs Level-4 acceptance decision package

Prepared 2026-09-10 for Taylor. Status: **pending decision**. Authority and activation effect: **none**.

## Executive boundary

The 282-row simulation wrote zero accepted observations. Of 200 rows matching the 13 proposed exact-series scopes, 154 rows across eight exact series are mechanically decision-ready if Taylor approves. Thirty-three DOL Initial Claims rows are contingent on revision-seed migration plus source-release freshness/identity. Thirteen BED rows are blocked because `bls-bed` lacks central source and rights policy entries. Eighty-two rows are outside this proposal. Zero rows qualify for forecast-vintage use.

Taylor must decide the three authority lanes independently: routine current/future releases, descriptive current-revised backfill, and forecast-vintage eligibility.

## Exact-series matrix

`Ready` below means validation-ready after an explicit Taylor grant; it does not mean accepted. `Held` is a precondition hold, not a validation rejection.

| Exact series | Factor | Routine | Descriptive history | Forecast vintage | Simulated ready / held / rejected | Binding constraints and principal risk |
|---|---|---|---|---|---:|---|
| `JTS000000000000000LDL` | Layoffs & Discharges | Ready | 19 ready | Ineligible | 19 / 0 / 0 | BLS/JOLTS, US, monthly, SA, thousands of persons, exact LDL level; preliminary/annual revisions. |
| `JTS000000000000000LDR` | Layoffs & Discharges | Ready | 19 ready | Ineligible | 19 / 0 / 0 | Exact LDR rate; never substitute for LDL level. |
| `JTS000000000000000JOR` | Job Openings Rate | Ready | 19 ready | Ineligible | 19 / 0 / 0 | Exact JOR rate; openings stock timing must remain distinct. |
| `JTS000000000000000HIR` | Hires Rate | Ready | 19 ready | Ineligible | 19 / 0 / 0 | Exact HIR rate; preserve revisions and precision. |
| `LNS13026638` | Permanent Job Losers | Ready | 19 ready | Ineligible | 19 / 0 / 0 | BLS/CPS, US, monthly, SA, thousands; population-control/method break fails closed. |
| `LNS13023653` | Temporary Layoffs | Ready | 19 ready | Ineligible | 19 / 0 / 0 | Exact CPS temporary-layoff identity and adjustment. |
| `CES0500000002` | Average Weekly Hours | Ready | 20 ready | Ineligible | 20 / 0 / 0 | BLS/CES, US, monthly, SA, hours; exact table/series and benchmark revisions. |
| `CES6056132001` | Temporary Help Employment | Ready | 20 ready | Ineligible | 20 / 0 / 0 | BLS/CES, US, monthly, SA, thousands; detailed series lacks machine-readable vintage coverage. |
| `BDS0000000000000000110004LQ5` | Gross Job Losses | Blocked | 4 blocked | Ineligible | 0 / 4 / 0 | BLS/BED, US, quarterly, SA, thousands; central rights/source policy missing. |
| `BDS0000000000000000110005LQ5` | Establishment Contractions | Blocked | 4 blocked | Ineligible | 0 / 4 / 0 | Same rights blocker; component identity must remain separate. |
| `BDS0000000000000000110006LQ5` | Establishment Closures | Blocked | 4 blocked | Ineligible | 0 / 4 / 0 | Same rights blocker; closures are not confirmed deaths. |
| `BDS0000000000000000110008LQ5` | Establishment Deaths | Blocked | 1 blocked | Ineligible | 0 / 1 / 0 | Same rights blocker plus three-quarter lag and partial archive recovery. |
| `DOL-UI-SA-INITIAL` | Initial Claims | Contingent | 33 contingent | Ineligible | 0 / 33 / 0 | DOL UI, US, weekly, SA, claims; migrate accepted 209,000 seed, link 212,000 revision, validate official release marker and freshness. |

Every routine profile also binds publisher, program, exact series, parser and validator version, cadence, geography, unit, adjustment, rights policy, effective time, anomaly policy, and allowed revision behavior. Unknown or changed metadata fails closed to manual review.

## Simulation reconciliation

- Candidate rows: **282**.
- Exact proposed-scope matches: **200**.
- Decision-ready after Taylor: **154** across eight exact series.
- Contingent: **33** DOL rows.
- Blocked: **13** BED rows.
- Outside authority: **82** (16 BED gains/openings/expansions/births, 33 DOL continued claims, 33 DOL insured-unemployment rate).
- Invalid candidates: **0**; ambiguous matches: **0**; hard validation rejects: **0**.
- Descriptive-history candidates now: **154**; after DOL preconditions: **187**.
- Structurally comparable exact series if all blockers resolve: **12 of 13**; BED deaths currently has one row.
- Forecast-vintage eligible: **0**; accepted observations written: **0**.

The candidate collector also recorded five BLS missing cells and 57 DOL missing/future cells; these omissions were not converted into observations or counted as rejected rows.

## Source-only identity outcomes

All nine identities have an explicit non-activating disposition. The plural `business-formations` identity is superseded by the visible singular canonical factor. BED expansions, openings, and establishment-birth gains are calculation-input-only; births remain a non-additive subset of openings. BED gross job gains and Courts Chapters 7/11/12/13 are secondary context only. No node, formula, accepted input, or observation was created.

## Materiality and UI readiness

Evidence acceptance does not depend on materiality. Direction and magnitude can be computed from comparable accepted observations; materiality stays `UNKNOWN` until Taylor approves an exact governed profile; destination impact stays `UNKNOWN` until relationship/context authority exists. The replay model enforces these boundaries.

The UI can host current/prior values, absolute and percent change, direction, period, revision, freshness, and history, but no new temporal panel was wired because accepted comparable history remains zero. The TypeScript temporal view still needs an explicit `UNKNOWN` materiality state and accepted-history integration before publication.

## Decisions required from Taylor

Choose **approve, modify, or reject** for each item separately:

1. **Routine current/future authority — eight BLS exact series.** Proposed: approve the four JOLTS, two CPS, and two CES profiles exactly as listed, effective only from Taylor's approval time. Any profile mismatch fails closed.
2. **Routine current/future authority — DOL Initial Claims.** Proposed: defer until the accepted 209,000 seed is migrated, the 212,000 value is linked as a later revision, and release-marker/freshness validation is implemented and tested.
3. **Routine current/future authority — four BED series.** Proposed: reject/defer until a central `bls-bed` source and rights policy explicitly authorizes required operations.
4. **Descriptive backfill — 154 BLS rows.** Proposed: approve only as `CURRENT_REVISED_HISTORY`, within the rule-specific windows, with conservative public-time bounds and no forecast eligibility.
5. **Descriptive backfill — 33 DOL rows.** Proposed: defer until the seed/supersession precondition is satisfied; then classify as current-revised descriptive history.
6. **Descriptive backfill — 13 BED rows.** Proposed: reject/defer until rights are resolved.
7. **Forecast-vintage eligibility.** Proposed: reject any blanket grant. Later approve only row by row after exact official archived artifacts and publication times are ingested and validated. Current eligible count remains zero.
8. **Materiality authority.** Proposed: no grant in this sprint; retain `UNKNOWN`.

The machine-readable proposal is `data/config/layoffs/history_acceptance_proposal.json`; the deterministic proof is `data/review/layoffs-acceptance-simulation.json`. Approval requires a separate governed edit to the live acceptance ledger. This package cannot activate itself.
