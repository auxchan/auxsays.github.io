# AUXSAYS Adobe Ingestion Reliability Repair

Surgical repair package focused on Adobe HelpX timeout behavior and source-health accuracy.

## Changed files

- `auxsays/scripts/lib/http.py`
- `auxsays/scripts/adapters/html_changelog.py`
- `auxsays/scripts/source_health_snapshot.py`
- `auxsays/_data/patch_ingestion_sources.yml`

## Behavior changes

- Adds retry/backoff support to HTTP fetches.
- Uses a browser-like, still-identifiable AUXSAYS User-Agent.
- Supports per-source request config: timeout, retries, backoff, max read bytes, and headers.
- Applies Adobe-specific request settings for HelpX release-note pages.
- Lets HTML changelog adapters pass source request settings into fetch calls.
- Treats enabled sources with errors and no previous success as `Failing`, not merely `Degraded`.

## Validation

- Python syntax check passed for changed scripts.
- YAML and JSON data loaded successfully.

## Next test

After pushing, manually run `AUXSAYS Patch Ingestion` from GitHub Actions, then check `/updates/methodology/`.
