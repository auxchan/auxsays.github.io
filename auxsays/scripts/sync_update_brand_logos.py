#!/usr/bin/env python3
"""Sync update_brands logo_path values from patch_products.

Purpose:
- Keep main patch feed brand tiles aligned with patch_products logo_path choices.
- Avoid one page using a repaired logo while another page still shows a placeholder.
"""
from pathlib import Path
import yaml
root = Path(__file__).resolve().parents[1]
products_path = root / '_data' / 'patch_products.yml'
brands_path = root / '_data' / 'update_brands.yml'
products = yaml.safe_load(products_path.read_text(encoding='utf-8'))
brands = yaml.safe_load(brands_path.read_text(encoding='utf-8'))
product_logo = {p['id']: p.get('logo_path', '') for p in products}
updated = 0
for source_id, meta in brands.items():
    new_logo = product_logo.get(source_id)
    if new_logo and meta.get('logo_path') != new_logo:
        meta['logo_path'] = new_logo
        updated += 1
brands_path.write_text(yaml.safe_dump(brands, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(f'Synced {updated} update_brands logo_path values from patch_products.')
