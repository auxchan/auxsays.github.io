# AUXSAYS Premiere Pro Data Completeness Sprint

Scope kept surgical. No generated source-health state, no ingestion state, no broad repo overwrite.

Files included:

- `auxsays/_layouts/aux-update.html`
- `auxsays/scripts/adapters/adobe_release_notes.py`
- `auxsays/scripts/lib/write_update_record.py`
- `auxsays/updates/generated/2026-04-30-premiere-pro-26-2.md`
- `auxsays/assets/css/auxsays-custom.css`

## Changes

1. Empty file-size badges now render an explicit field state instead of a blank value.
2. Premiere Pro 26.2 now shows `File size: Not provided by source` with the Adobe source limitation preserved as tooltip text.
3. The Adobe release-notes adapter now cleans Adobe Community announcement bodies instead of ingesting JavaScript/forum shell text.
4. `write_update_record.py` now preserves consensus/report metadata supplied by adapters instead of forcing all generated records to official-only / 0 reports.
5. Premiere Pro 26.2 now has an initial static AUXSAYS consensus seed:
   - 7 confirmed patch-specific Adobe Community report sources
   - Moderate label
   - Low confidence
   - Known issues present = Yes
   - Static sample evidence state
6. The existing Premiere Pro 26.2 generated page is updated directly so the live page improves immediately after deploy.

## Notes

This is not live consensus scraping. It is a static seed for the first Premiere Pro 26.2 data-completeness pass. Live consensus refresh remains the next larger subsystem.
