# AUXSAYS Feed and Source-Health Semantics Repair

## Scope

This is a narrow cleanup package.

It addresses:

1. Duplicate `feed.xml` build output caused by explicit `jekyll-feed` usage alongside the Chirpy/theme feed path.
2. Source-health semantics for successful runs that return `0 fetched / 0 written / no error`.

## Files changed

- `auxsays/_config.yml`
- `auxsays/Gemfile`
- `auxsays/scripts/source_health_snapshot.py`
- `auxsays/updates/methodology/index.md`
- `auxsays/assets/css/auxsays-custom.css`

## Feed cleanup

Explicit `jekyll-feed` usage was removed from `_config.yml` and `Gemfile` so the build no longer has two feed sources competing for `_site/feed.xml`.

This package intentionally does not touch the Chirpy Sass `@import` warning. That warning is theme/dependency technical debt and is not currently blocking builds.

This package intentionally does not update GitHub Actions versions.

## Source-health semantics

Successful checks with no error and no eligible records now display as:

- `Idle healthy`
- `No new records`

This avoids treating a reachable source with no new update records as degraded.

## Generated-state policy

This package does not include:

- `auxsays/_data/source_health.yml`
- `auxsays/_data/patch_ingest_state.json`
- `auxsays/updates/generated/*`

`source_health.yml` should continue to be generated during the Build and Deploy workflow.
