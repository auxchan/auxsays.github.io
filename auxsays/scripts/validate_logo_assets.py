import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / 'assets' / 'img' / 'patch-logos'
ALLOWED_EXTENSIONS = {'.svg', '.webp', '.png', '.jpg', '.jpeg'}

def load_yaml(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def local_asset_path(logo_path):
    if not logo_path:
        return None
    if '://' in str(logo_path):
        return None
    return str(logo_path).split('?', 1)[0]

def validate_local_logo(label, entry, entry_id, errors):
    logo_path = entry.get('logo_path')
    asset_path = local_asset_path(logo_path)
    if not logo_path:
        errors.append(f"{label}:{entry_id}: missing logo_path")
        return
    if asset_path is None:
        errors.append(f"{label}:{entry_id}: external logo_path not allowed: {logo_path}")
        return
    if not asset_path.startswith('/assets/img/patch-logos/'):
        errors.append(f"{label}:{entry_id}: logo_path must point to /assets/img/patch-logos/: {logo_path}")
        return
    ext = Path(asset_path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"{label}:{entry_id}: unsupported logo extension {ext}")
        return
    file_path = ROOT / asset_path.lstrip('/')
    if not file_path.exists():
        errors.append(f"{label}:{entry_id}: missing logo asset file: {asset_path}")

def main():
    companies = load_yaml(ROOT / '_data' / 'patch_companies.yml') or []
    products = load_yaml(ROOT / '_data' / 'patch_products.yml') or []
    update_brands = load_yaml(ROOT / '_data' / 'update_brands.yml') or {}
    provenance_doc = load_yaml(ROOT / '_data' / 'patch_logo_sources.yml') or {}
    provenance_entries = provenance_doc.get('assets', []) if isinstance(provenance_doc, dict) else []
    provenance = {item.get('asset_id'): item for item in provenance_entries}
    errors = []

    company_ids = set()
    for company in companies:
        cid = company.get('id')
        company_ids.add(cid)
        validate_local_logo('company', company, cid, errors)
        if company.get('asset_type') != 'company_logo':
            errors.append(f"company:{cid}: asset_type must be company_logo")
        if cid not in provenance:
            errors.append(f"company:{cid}: missing provenance entry")

    product_logo = {}
    for product in products:
        pid = product.get('id') or product.get('product_id')
        product_logo[pid] = product.get('logo_path')
        validate_local_logo('product', product, pid, errors)
        if product.get('company_id') not in company_ids:
            errors.append(f"product:{pid}: unknown company_id {product.get('company_id')}")
        if product.get('asset_type') not in {'product_icon', 'company_fallback'}:
            errors.append(f"product:{pid}: asset_type must be product_icon or company_fallback")
        if product.get('asset_type') == 'company_fallback':
            company = next((c for c in companies if c.get('id') == product.get('company_id')), None)
            if company and product.get('logo_path') != company.get('logo_path'):
                errors.append(f"product:{pid}: company_fallback logo_path must equal parent company logo_path")
        if pid not in provenance:
            errors.append(f"product:{pid}: missing provenance entry")

    seen_paths = {}
    for item in provenance_entries:
        aid = item.get('asset_id')
        local_path = item.get('local_path')
        if not aid:
            errors.append('provenance:<missing>: asset_id is required')
        if not local_path:
            errors.append(f"provenance:{aid}: local_path is required")
        elif '://' in str(local_path):
            errors.append(f"provenance:{aid}: local_path cannot be external")
        elif not (ROOT / str(local_path).lstrip('/')).exists():
            errors.append(f"provenance:{aid}: local_path file missing: {local_path}")
        if aid in seen_paths and seen_paths[aid] != local_path:
            errors.append(f"provenance:{aid}: duplicate asset_id with conflicting local_path")
        seen_paths[aid] = local_path

    for source_id, meta in update_brands.items():
        expected = product_logo.get(source_id)
        if expected and meta.get('logo_path') != expected:
            errors.append(f"update_brands:{source_id}: logo_path out of sync with patch_products")
        validate_local_logo('update_brand', meta, source_id, errors)

    print(f"Validated {len(companies)} companies, {len(products)} products, {len(update_brands)} update brand records, and {len(provenance_entries)} provenance entries.")
    if errors:
        print(f"Errors: {len(errors)}", file=sys.stderr)
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        sys.exit(1)
    print('Logo asset validation passed.')

if __name__ == '__main__':
    main()
