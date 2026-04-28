# AUXSAYS Patch Feed Control Repair

This repair targets the issues observed after the Patch Feed hierarchy update.

## Fixed
- Adobe company card now uses a dedicated Adobe company logo instead of the Premiere Pro product logo.
- Native dropdown option text is forced to a readable foreground/background so Company and Software dropdown menus are not visually blank.
- Company radar cards now carry computed update-count/date metadata for sorting.
- Sort controls now explicitly reassign card order when visible cards are sorted.
- Company radar data-priority is now consistently `company`, with the legacy/core priority retained separately as `data-watch-priority` for risk-style sorting.

## Not changed
- No ingestion expansion.
- No additional Adobe software.
- No generated patch records changed.
