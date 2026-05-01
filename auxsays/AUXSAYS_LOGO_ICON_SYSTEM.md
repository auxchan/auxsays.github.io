# AUXSAYS Logo and Icon System

AUXSAYS uses company logos and software/product icons only for editorial identification and navigation. These assets do not imply sponsorship, endorsement, affiliation, or partnership.

## Rules

1. Do not hand-generate approximations when a real brand-identifying source is available.
2. Do not use runtime logo hotlinks in `logo_path`.
3. `patch_companies.yml`, `patch_products.yml`, and `update_brands.yml` must resolve to local files under `/assets/img/patch-logos/`.
4. Product records use `asset_type: product_icon` when there is a product-specific icon.
5. Product records use `asset_type: company_fallback` when no validated product icon is available.
6. Every company and product must have a provenance entry in `_data/patch_logo_sources.yml`.

## Validation

Run:

```bash
python auxsays/scripts/validate_logo_assets.py
```

The validator checks local paths, file existence, external URL bans, provenance entries, explicit product fallbacks, and `update_brands` synchronization.

## Current repair note

OBS Studio and AMD now use local Simple Icons-derived SVG paths. DaVinci Resolve uses a local product-icon SVG. Blackmagic Design avoids the old `BI` placeholder and is marked for future replacement with a verified official company vector.
