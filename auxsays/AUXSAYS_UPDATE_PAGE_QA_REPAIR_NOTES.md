# AUXSAYS Update Page QA Repair Notes

## Scope
Focused QA repair for update pages after live review.

## Changes
- Fixed update-page title selection so `update_detail_title` / `update_feed_title` is used before reconstructing product + version.
- Hardened file-size badge checks by stripping and validating the value before rendering.
- Improved GitHub-generated release note readability by converting raw PR URLs into compact PR links.
- Rewrote existing ComfyUI generated release bodies and summaries with the improved normalizer.
- Added official patch-note CSS overrides so long GitHub release lists render as readable compact evidence cards instead of a decorative vertical timeline.
- Added a friendly noindex route for `/updates/blackmagic-design/davinci-resolve/20-2-2/` explaining that this is not a currently tracked patch record, instead of returning a generic 404.

## Notes
- File size remains hidden when not captured. This is intentional; AUXSAYS should not invent installer sizes.
- The DaVinci 20.2.2 route is not a patch record and should not appear in the Patch Feed.
