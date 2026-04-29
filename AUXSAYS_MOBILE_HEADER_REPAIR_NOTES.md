# AUXSAYS Mobile Header Repair

## Scope
CSS-only repair for the top navigation on mobile.

## Issue
The site content aligned correctly on mobile, but the header navigation buttons were pushed too far right and could be clipped off-screen.

## Fix
Added a mobile-only CSS override at the bottom of `auxsays/assets/css/auxsays-custom.css`:

- Converts the topbar inner layout to a two-row column layout on narrow screens.
- Keeps the brand block full-width.
- Removes `margin-left:auto` behavior from `.aux-nav` on mobile.
- Allows nav links to wrap inside the viewport.
- Slightly reduces nav button padding/font-size on very narrow screens.

## Files changed
- `auxsays/assets/css/auxsays-custom.css`
- `AUXSAYS_MOBILE_HEADER_REPAIR_NOTES.md`

## QA
Check on mobile widths:

- Home page
- `/updates/`
- `/updates/adobe/`

Expected: `Home`, `About Aux`, `Articles`, and `Patch Feed` remain fully visible and wrap under the logo if needed.
