# AUXSAYS Logo and Icon System

AUXSAYS uses company logos and product/software icons only for independent editorial/reference identification.
They do not imply sponsorship, endorsement, partnership, or affiliation.

## Rules

1. Do not hand-draw, AI-generate, or approximate brand marks when a real source is available.
2. Do not hotlink logo assets in `patch_companies.yml`, `patch_products.yml`, or `update_brands.yml`.
3. Every rendered logo path must resolve to a local file under:
   - `auxsays/assets/img/patch-logos/`
4. Product pages should use product icons when a verified product-specific icon is available.
5. If a verified product icon is not available, use the company logo as an explicit fallback.
6. Every company/product asset decision must have a provenance entry in:
   - `auxsays/_data/patch_logo_sources.yml`

## Data ownership

- `patch_companies.yml` owns company-level identity.
- `patch_products.yml` owns product/software-level identity.
- `update_brands.yml` mirrors product logo paths for update feed cards.
- `patch_logo_sources.yml` records provenance and fallback status.

## Validation

Run:

```bash
python auxsays/scripts/validate_logo_assets.py
```

The validator fails if:

- any company/product/update brand uses an external logo URL
- a referenced local asset does not exist
- a company/product has no provenance entry
- product company fallbacks are not explicit
- `update_brands.yml` falls out of sync with `patch_products.yml`

## Current implementation note

This sprint normalizes the system and removes remote logo dependencies from data. Some product entries intentionally use company-logo fallback until a verified official product icon is sourced and committed locally.
