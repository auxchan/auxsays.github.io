# AUXSAYS Core Reliability Sprint 1 Notes

## Scope
This build hardens the official-source ingestion reliability layer. It does not add new products, user accounts, paid features, backend services, API features, or live community consensus scraping.

## What changed
- Ingestion now updates per-source operational state after each run.
- Each source tracks last checked, last success, last error, consecutive failures, records fetched/written/skipped, adapter, duration, and status.
- Source-health snapshot now derives status labels such as Healthy, Degraded, Failing, Staged, Manual watch, and Disabled.
- Source-health snapshot now includes adapter capability data derived from `extractable_fields`.
- The Methodology page now presents source health as an operational audit surface instead of a raw config dump.
- The source-health table is more readable and shows records, capabilities, failure counts, and friendlier error messages.
- Official patch-note bullet styling keeps the AUXSAYS blue circuit-node aesthetic while improving scanability.

## Important limitation
This does not make consensus live. It prepares the official ingestion system to become accountable enough to support later consensus work.

## Files changed
- `.github/workflows/patch-ingest.yml` was not changed; it already runs `source_health_snapshot.py` after ingestion.
- `auxsays/scripts/lib/state.py`
- `auxsays/scripts/patch_ingest.py`
- `auxsays/scripts/source_health_snapshot.py`
- `auxsays/_data/source_health.yml`
- `auxsays/updates/methodology/index.md`
- `auxsays/assets/css/auxsays-custom.css`

## Validation performed
- Python syntax checks passed.
- JavaScript syntax check passed.
- YAML and JSON data files loaded successfully.
- Source-health snapshot regenerated successfully.
