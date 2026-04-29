# AUXSAYS Adobe Adapter Strategy Repair

## Scope
This is a surgical adapter strategy repair for Adobe ingestion reliability. It does not add products, remove Adobe from the site, add consensus scraping, add a backend, or redesign Patch Feed pages.

## Problem addressed
The Adobe HelpX sources repeatedly timed out in GitHub Actions. Longer timeouts/retries made the workflow slow without making Adobe ingestion successful.

## Changes
- Added a dedicated `adobe_release_notes` adapter.
- Kept Premiere Pro as the active Adobe ingestion test lane.
- Moved After Effects, Photoshop, Media Encoder, and Lightroom Classic to staged ingestion status while keeping their site pages/products visible.
- Reduced Adobe request timeout/retry settings to avoid 20+ minute workflow drag.
- Updated source-health snapshot behavior so staged sources do not display stale errors from older active runs.
- Updated staged-source classification so sources marked as staged render as `Staged`, not `Disabled`.

## Expected outcome
After the next ingestion run:
- Premiere Pro either succeeds through the dedicated adapter or fails quickly with a precise operational signal.
- Other Adobe products display as Staged rather than Failing.
- The workflow should not spend 20+ minutes burning through Adobe timeouts.

## Files changed
- `auxsays/scripts/adapters/adobe_release_notes.py`
- `auxsays/scripts/source_health_snapshot.py`
- `auxsays/_data/patch_ingestion_sources.yml`
- `auxsays/_data/source_health.yml`
