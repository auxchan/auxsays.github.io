# AUXSAYS Home Patch Signals Repair

## Scope

This update changes the homepage patch module from a broad mirror of the global Patch Feed into a curated Patch Signals module.

## Files changed

- `auxsays/_layouts/aux-home.html`
- `auxsays/assets/css/auxsays-custom.css`
- `AUXSAYS_HOME_PATCH_SIGNALS_REPAIR_NOTES.md`

## Behavior

The homepage now promotes only update records with actionable signal:

- `homepage_featured: true`
- confirmed reports greater than zero
- known issues present
- pilot/static sample evidence
- consensus-live evidence
- pilot intelligence stage

Official-only records with zero reports and no known issue signal remain available in the full Patch Feed, but they are no longer promoted on the homepage.

## Sort strategy

The homepage module buckets records by signal priority, then by date inside each bucket:

1. Manually featured
2. Negative consensus with signal
3. Moderate consensus with signal
4. Positive consensus with signal
5. Remaining pilot/live/known-issue records

The module caps output at 8 records.

## UX copy

The module title is now `Patch Signals` with the description:

> Updates with confirmed reports, known issues, or notable workflow impact.

The bottom link remains:

> View full Patch Feed →

## Validation notes

- Jekyll build was not run locally because `bundle` is not installed in this container.
- No generated state files were modified.
- No Patch Feed records were removed.
- Full Patch Feed inventory remains accessible at `/updates/`.
