# Persistent World Validation Evidence

Status: **IMPLEMENTATION VALIDATION PASS / HUMAN QA PENDING**

## Automated validation

| Check | Result |
|---|---|
| TypeScript type-check | PASS |
| UI tests | PASS — 185 / 185 |
| Data/engine Python tests | PASS — 207 / 207 |
| Persistent-world tests | PASS — 6 / 6 |
| Production UI build | PASS |
| Hashed-asset manifest | PASS — 11 assets |
| UI gzip budget | PASS — 233,241 / 368,640 bytes |
| Static-site verifier | PASS |
| Production fixture-string scan | PASS — no persistent-world fixture identifiers or labels |

The jsdom test environment logs its existing `HTMLCanvasElement.getContext`
notice because the optional native canvas package is not installed. Assertions
use the renderer's accessibility and diagnostic surface and all tests pass.

## Browser validation

Local route: `http://127.0.0.1:4174/systems-monitor/#persistent-world`

- overview reports 1,111 resident placements, 3,110 resident relationships,
  11 semantic nodes, and one stable topology/layout fingerprint;
- focus reports the same resident counts/fingerprint and 12 semantic nodes;
- Reset returns to the outcome while preserving the fingerprint;
- native full-screen enters and exits successfully;
- full-world density LOD is available only through an explicit action;
- same-page navigation into `#workstream1a` switches cleanly into the factual
  snapshot instead of retaining the synthetic fixture snapshot;
- the factual shell still displays the six accepted readings: 158,858; 4.1%;
  61.4%; 209,000; 7,359; and 5,348.

Measured local Canvas draw-work p95 was 1.400 ms overview, 0.700 ms focus, and
1.500 ms full-world density in the final clean sequence. Wheel zoom remained inside the graph (no page
scroll), and middle-button pan plus empty-space double-click Reset are covered
by the interaction regression test. See `PERSISTENT_WORLD_RENDERER_BENCHMARK.md`.

## Build-environment note

An additional local Windows `bundle exec jekyll build --trace` attempt stopped
before site generation because the existing vendor bundle lacks `tzinfo`. No
dependency was installed or changed. The repository's own production UI build,
asset composition, manifest checks, and static-site verifier all pass.

## Scope confirmation

- no BINDING contract changed;
- no dependency or workflow changed;
- no source ingestion, BEA acceptance, factual structural edge, forecast,
  public activation, deployment, or Patch Feed work occurred;
- Gate B remains OPEN;
- `HUMAN_PERSISTENT_WORLD_QA` remains PENDING.
