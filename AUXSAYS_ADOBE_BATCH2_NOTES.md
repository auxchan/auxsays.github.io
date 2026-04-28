# AUXSAYS Adobe Batch 2 Build

## Scope

This build expands Adobe tracking from Premiere Pro into four additional Adobe software targets while keeping the previous card UI repair intact.

## Added software targets

- After Effects
- Photoshop
- Media Encoder
- Lightroom Classic

## Premiere Pro cleanup

Premiere Pro now explicitly identifies the product as a non-linear editor / NLE in its description, impact copy, watch reason, and signal notes.

## Source behavior

The four new Adobe products are configured as enabled `html_changelog` ingestion sources using Adobe HelpX release-note pages. They share the generalized Adobe release-note parser profile family in `auxsays/scripts/adapters/html_changelog.py`.

## Important validation step

After pushing, run dry-run workflow checks first:

- `adobe-after-effects`
- `adobe-photoshop`
- `adobe-media-encoder`
- `adobe-lightroom-classic`

Then run real ingestion only after dry-run output shows `errors: []`.
