# AUXSAYS Credibility Hardening Sprint

## Scope
This build implements the first credibility-hardening pass for the Patch Feed. It does not expand product scope, add backend services, add accounts, add paid features, or activate community scraping.

## Key changes
- Patch pages now render a compact AUXSAYS verdict/evidence box near the top.
- Patch pages now classify evidence as Consensus live, Official only, Static sample, or Insufficient data.
- Empty optional fields are guarded with blank-safe Liquid checks.
- Download links, file size, checksum sections, and source links render only when real values exist.
- Added a public methodology page at `/updates/methodology/`.
- Added a visible methodology link from the Patch Feed hero and footer.
- Added a static source-health data snapshot at `_data/source_health.yml`.
- Added `scripts/source_health_snapshot.py` to regenerate the source-health snapshot from ingestion config/state.
- Updated official ingestion record writer to include evidence-state fields for future records.
- Switched the base layout to use `jekyll-seo-tag` via `{% seo %}`.

## Evidence terminology
- Consensus live: confirmed patch-specific reports are actively refreshed by a consensus pipeline.
- Official only: official source data is captured, but no confirmed patch-specific reports are counted.
- Static sample: report counts exist as manually encoded or previously captured static samples; not live telemetry.
- Insufficient data: not enough official or confirmed report evidence has been captured.

## Validation performed
- YAML data files loaded successfully.
- JSON data files loaded successfully.
- Python syntax checks passed.
- JavaScript syntax check passed.
- Consensus metadata audit passed.
- Source-health snapshot regenerated successfully.

## Known limitation
A full Jekyll build could not be run in the container because Jekyll/Bundler are not available in this environment. GitHub Actions should perform the authoritative build after push.
