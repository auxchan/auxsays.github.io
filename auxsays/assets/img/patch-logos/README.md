# Patch Logos

Logo SVGs in this folder are generated during the GitHub Pages build.

Source files:
- `auxsays/_data/patch_logo_slugs.json`
- `auxsays/scripts/generate_patch_logos.mjs`

The build step runs `npm run generate:patch-logos` before Jekyll builds `_site`.
Do not manually commit generated Simple Icons SVGs unless you intentionally want to override a specific logo.
