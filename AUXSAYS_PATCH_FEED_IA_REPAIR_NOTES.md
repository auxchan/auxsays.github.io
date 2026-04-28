# AUXSAYS Patch Feed IA Repair Notes

## Scope
This repair addresses the main Patch Feed information architecture and Adobe card backdrop tuning only. It does not add new ingestion sources.

## Main Patch Feed changes
- Replaced the conflated `Source` dropdown with two separate hierarchy dropdowns:
  - `Company`
  - `Software`
- Removed the main-page `Consensus` filter row.
- Renamed `Lane` to `Select Type`.
- Changed the Company Radar to render from `_data/patch_companies.yml` instead of `_data/patch_sources.yml` so the hierarchy is now:
  - Company
    - Software
      - Patches/Updates
- Company Radar now reports:
  - tracked companies
  - tracked software
  - company → software → patches hierarchy
- Company Radar cards are sorted alphabetically by company name by default.
- Software dropdown is sorted alphabetically by software/product name.
- Patch cards now carry `data-company-id` and `data-product-id` so the new dropdowns can filter correctly.

## Adobe hierarchy correction
Adobe is treated as a single company with software beneath it:
- Premiere Pro
- After Effects
- Lightroom Classic
- Media Encoder
- Photoshop

The main Patch Feed should no longer present Adobe as a Creative Cloud / Firefly grouping unless those products are intentionally added as Adobe software targets later.

## Backdrop tuning
- Adjusted Adobe software-card backdrop CSS to reduce aggressive background cropping.
- Background images now use `background-size: contain` with a right-side masked placement.
- This keeps more of the UI visible and should reduce the over-cropped/low-resolution feel.

## Validation performed
- YAML data files loaded successfully with Python.
- JavaScript syntax passed `node -c`.
- Local Jekyll build could not be run in this environment because `bundle` is not installed.

## QA checklist after deploy
1. Visit `/updates/`.
2. Confirm top controls are more compact.
3. Confirm Company and Software are separate dropdowns.
4. Confirm Consensus row is gone.
5. Confirm `Select Type` replaced `Lane`.
6. Confirm Company Radar shows one Adobe company card, not separate Adobe software cards.
7. Confirm Adobe card links to `/updates/adobe/`.
8. Confirm selecting Company = Adobe filters to Adobe-related cards/records.
9. Confirm selecting Software = Premiere Pro filters to Adobe/Premiere Pro context.
10. Visit `/updates/adobe/` and confirm UI backgrounds are less aggressively cropped.
