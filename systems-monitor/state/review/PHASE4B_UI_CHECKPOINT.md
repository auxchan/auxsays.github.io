# Phase-4B Local UI Checkpoint

Status: **HUMAN_PHASE4B_UI_CHECK = PENDING**

Scope: **LOCAL REVIEW ONLY — NOT PUBLICLY ACTIVATED**

Gate B: **OPEN**

Phase 5: **LOCKED**

## What this checkpoint shows

- Three official `OBS` records: EIA commercial crude excluding SPR, EIA
  refinery utilization, and BLS truck-transportation employment.
- Zero accepted factual structural relationships in the current non-live
  candidate.
- Zero Phase-4B structural `CALC` records.
- `BLOCKED_LIVE_BEA_CREDENTIAL` as an analytical source-acceptance state, not
  an application error.
- Bounded energy/refining/utilities/transport work in progress, explicitly not
  whole-economy structural proof.
- No forecasts or scenarios.

## Local review

From `systems-monitor/app`:

```text
npm run dev:phase4b
```

Open `http://127.0.0.1:4174/systems-monitor/__local-review/phase4b` once. The
loopback-only development loader reads the governed review artifacts, stores
them only for this local origin, and redirects to
`http://127.0.0.1:4174/systems-monitor/?view=summary`. No other setup is
required. Hot reload is active while the Vite development server is running.

The console loader from `data/scripts/print_local_ui_loader.py` remains an
equivalent manual fallback. Neither loader is included in the production build.

## Human visual QA checklist

1. Can I identify the current `OBS` immediately?
2. Is it obvious AUXSAYS has not produced a structural `CALC`?
3. Is the blocked BEA state understandable?
4. Can I reach exact evidence without cluttering the main view?
5. Is bounded coverage obvious?
6. Does the page still feel like isolated metric cards?
7. Is there a believable future home for dependency/cascade visualization?
8. Is visible text concise?
9. Does Outlook avoid fake forecasting?
10. Does anything imply structural proof that does not exist?

## Deferred UI critique

- The current shell still inherits a generic dashboard/card vocabulary. The
  new structural area gives dependencies a clear future home, but no arrows are
  drawn until accepted factual paths exist.
- The navigation rail remains anchored to the earlier labor-factor hierarchy,
  so the overall product can still feel like an isolated factor inspector.
- Summary is now scan-first, but the global candidate notice, breadcrumbs,
  heartbeat, rail, and view header still create more vertical chrome than the
  mature structural product should need.
- Evidence access is strong and progressively disclosed in Verified Data; its
  tables are information-dense and will need a better small-screen pattern in
  the deferred major redesign.
- `OBS` versus `CALC`, source acceptance, coverage, and Outlook unavailability
  are now explicit. Source-health detail is intentionally behind disclosure.
- The three-stage structural frame is only a truthful empty-state scaffold. It
  should become an interactive dependency/cascade canvas only after real
  accepted relationships exist.

Taylor must record PASS or corrections. This file does not promote Gate B.
