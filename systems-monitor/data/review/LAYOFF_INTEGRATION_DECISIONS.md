# Layoffs Live Branch — Integration Decisions

Status: implementation working record; Human QA remains pending.

| Decision area | Integration decision | Boundary / unresolved blocker |
| --- | --- | --- |
| Exact source adapters | Reuse the accepted Phase-3 labor snapshot for previously accepted observations. Add bounded adapters for BLS JOLTS/CPS/BED/CES/Productivity/PPI, DOL UI claims, Census BDS/BFS/economic indicators, BEA NIPA, Federal Reserve G.17/H.15/SLOOS, and U.S. Courts F-2. | A dataset remains `SOURCE_IDENTIFIED` or `BLOCKED` until its exact identifier, parser, rights, and acceptance path are verified. |
| Existing adapters | Preserve the central six-indicator Phase-3 pipeline. The Layoffs program uses separate registries/adapters so it cannot weaken the exact-eight/exact-six Gate-A contracts. | New retrievals never inherit acceptance merely because an older observation from the same publisher was accepted. |
| Canonical deduplication | Store one canonical factor identity and attach multiple hierarchy placements to it. The frozen 100 placements resolve to 64 canonical factors. | Hierarchy placement cannot clone values, provenance, health, or freshness. |
| Relationship classification | Hierarchy tethers are navigation only. Claims are measurement context. Bankruptcy is a leading/stress signal. Pressure channels remain `CANDIDATE`. BED contractions and closings may become accounting components only through the governed acceptance rule. | No prompt-defined pressure relationship is auto-promoted. Gross losses never stand in for net employment change. |
| Credentials | Use `AUXSAYS_CENSUS_API_KEY` and `AUXSAYS_BEA_USER_ID` from the environment or GitHub secrets only. | Missing credentials produce a redacted `BLOCKED` health state, never a crash, URL leak, or fabricated value. |
| Cadence / scheduler | A maximum four-hour evaluation heartbeat performs source-specific due checks, native-cadence freshness, retry/backoff, content-hash unchanged detection, and last-valid-snapshot retention. | The heartbeat is not a universal four-hour download cadence. |
| Read model | Publish one immutable local-review snapshot family with snapshot-owned publication class and additive Layoffs extensions for factor, placement, source, health, relationship, and coverage state. | No item may override snapshot publication class; failed candidates leave the last valid snapshot active. |
| UI integration | Keep the premium persistent-world renderer and its camera, node, connector, label-lane, reduced-motion, and accessibility baseline. Replace only the Layoffs branch's synthetic identities and inspector data. | A value renders only from an accepted observation. Candidate relationships cannot use accepted visual semantics. |
| Workflow / deploy | A data-changing scheduled run must explicitly dispatch the Pages workflow after a successful bot writeback; unchanged runs do not churn snapshots or deploy. | A bot commit is not assumed to trigger downstream workflows automatically. |
| Current blockers | Census and BEA credentials; unverified EIA route/rights; several industry crosswalks; industry-granular credit; an exact automation measure; and scope distinctions among bankruptcy, firm death, establishment death, closure, and job loss. | Blockers remain visible in source health and the UI. They do not become zero, neutral, or synthetic fallback values. |

## Expected implementation files

- `data/config/layoffs/`: taxonomy, source, relationship, scheduler, and read-model registries.
- `data/src/systems_monitor_data/`: source adapters, orchestrator, relationship validation, and snapshot publication.
- `data/tests/` and `app/tests/`: deterministic source, governance, leakage, snapshot, workflow, and UI tests.
- `app/src/data/` and `app/src/views/persistent/`: Layoffs read-model binding and premium persistent-world integration.
- `.github/workflows/`: one narrow scheduled evaluation/writeback/rebuild workflow if required.
- `data/review/`: acquisition audit, relationship report, integration summary, and QA evidence.

Contracts, Patch Feed, Phase 5, unrelated pages, and public activation remain out of scope.
