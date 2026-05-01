# AUXSAYS Status Alert Icon Update

What changed
- Added the software icon/logo to each `Status change alerts` item on the main Patch Feed page.
- Each alert now resolves its icon by:
  1. looking up the update page from `note.url`
  2. resolving the related `product_id`
  3. using that product's `logo_path`
  4. falling back to the company logo if needed
- Added layout styling so the icon, status pill, title, and message read cleanly.

Files changed
- `auxsays/_layouts/aux-updates.html`
- `auxsays/assets/css/auxsays-custom.css`
