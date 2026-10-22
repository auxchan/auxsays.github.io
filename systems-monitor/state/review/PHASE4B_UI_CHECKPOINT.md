# Phase-4B Local UI Checkpoint

Status: **HUMAN_PHASE4B_UI_CHECK = PENDING**

Scope: **LOCAL REVIEW ONLY — NOT PUBLICLY ACTIVATED**

Gate B: **OPEN**

Phase 5: **LOCKED**

## What this redesign shows

- A scan-first Summary that leads with three official measurements and visual
  signal identities instead of record-type jargon or a wall of provenance.
- Selectable signal cards that reveal one focused evidence layer at a time.
- A truthful structural-model empty state: three inputs are ready, while zero
  relationships and zero structural calculations mean no arrows or system
  result are drawn.
- A progressive Evidence Room where exact source, series, methodology, machine
  acquisition provenance, earlier Gate-A evidence, and source health remain
  available on demand.
- A visually distinct Outlook boundary that keeps forecasting locked without
  filling the screen with repeated warnings.
- No forecasts, scenarios, accepted structural paths, or invented analytical
  results.

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

1. Do the three current measurements make sense within a few seconds?
2. Can I select a signal and understand its value, period, and publisher?
3. Does “Peel back details” make deeper evidence easy to reach?
4. Is it obvious that the structural model has inputs but no accepted
   connections or system result yet?
5. Does the page avoid repeated `OBS` / `CALC` jargon in the primary journey?
6. Can I expand an Evidence Room card and reach original evidence,
   methodology, and machine-acquisition provenance?
7. Are earlier Gate-A records and technical source health available without
   dominating the page?
8. Does the experience remain usable on a narrow screen without horizontal
   overflow?
9. Does Outlook avoid fake forecasting and explain the lock only on demand?
10. Does anything imply structural proof that does not exist?

## Deliberate boundaries

- The redesign uses the current governed Phase-4B read model; it does not add
  or hard-code analytical facts.
- The structural canvas remains an empty-state scaffold. It can become an
  interactive dependency/cascade experience only after real accepted
  relationships exist.
- Compact “Gate B open” and local-review status remain visible because this is
  a review candidate, while detailed technical state stays collapsed.
- The earlier labor evidence remains available as a secondary archive rather
  than competing with the current Phase-4B journey.
- This is a local candidate only. It does not authorize public activation,
  deployment, Gate-B closure, or Phase-5 forecasting.

Taylor must record PASS or corrections. This file does not promote Gate B.
