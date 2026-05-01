# AUXSAYS Sitewide Logo Hotfix

What changed
- Replaced sitewide product logo references that were still using low-quality placeholder/local monogram SVGs.
- For products without a strong product-specific icon already in the repo, the site now uses the parent company logo path.
- Kept the stronger Adobe app-specific badges already present in the repo.
- Synced `update_brands.yml` so the main patch feed uses the same repaired logo choices.
- Added layout fallbacks so company/product/update pages can fall back to the company logo if a product logo is blank.

Files touched
- `auxsays/_data/patch_products.yml`
- `auxsays/_data/update_brands.yml`
- `auxsays/_layouts/aux-patch-company.html`
- `auxsays/_layouts/aux-update.html`
- `auxsays/_layouts/aux-updates.html`
- `auxsays/scripts/sync_update_brand_logos.py`

Important limitation
- This is a sitewide **hotfix** focused on eliminating the bad placeholder icons immediately.
- It does **not** yet build a fully local cached logo asset library for every software product.
- Products without a dedicated verified product icon now intentionally use the parent company logo instead of a fake/generated placeholder.
