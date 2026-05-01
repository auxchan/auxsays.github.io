import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / 'assets' / 'img' / 'patch-logos'
ALLOWED_EXTENSIONS = {'.svg', '.webp', '.png', '.jpg', '.jpeg'}

def load_yaml(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def validate_entries(label, entries, key_name):
    errors = []
    warnings = []
    for entry in entries:
        entry_id = entry.get(key_name) or entry.get('id') or '<unknown>'
        logo_path = entry.get('logo_path')
        if not logo_path:
            errors.append(f"{label}:{entry_id}: missing logo_path")
            continue
        if '://' in str(logo_path):
            errors.append(f"{label}:{entry_id}: external logo_path not allowed: {logo_path}")
            continue
        asset_path = logo_path.split('?', 1)[0]
        if not asset_path.startswith('/assets/img/patch-logos/'):
            errors.append(f"{label}:{entry_id}: logo_path must point to /assets/img/patch-logos/: {logo_path}")
            continue
        ext = Path(asset_path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"{label}:{entry_id}: unsupported logo extension {ext}")
            continue
        file_path = ROOT / asset_path.lstrip('/')
        if not file_path.exists():
            errors.append(f"{label}:{entry_id}: missing logo asset file: {asset_path}")
    return errors, warnings

def main():
    companies = load_yaml(ROOT / '_data' / 'patch_companies.yml') or []
    products = load_yaml(ROOT / '_data' / 'patch_products.yml') or []

    errors = []
    warnings = []
    e, w = validate_entries('company', companies, 'id')
    errors += e
    warnings += w
    e, w = validate_entries('product', products, 'product_id')
    errors += e
    warnings += w

    print(f"Validated {len(companies)} companies and {len(products)} products for local logo assets.")
    if warnings:
        print(f"Warnings: {len(warnings)}")
        for item in warnings:
            print(f"WARNING: {item}")
    if errors:
        print(f"Errors: {len(errors)}", file=sys.stderr)
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        sys.exit(1)
    print('Logo asset validation passed.')

if __name__ == '__main__':
    main()
