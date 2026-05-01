#!/usr/bin/env python3
"""Validate AUXSAYS patch logo/icon identity system.

Checks:
- company/product/update_brand logo paths are local, not hotlinked
- referenced files exist
- company/product entries have explicit asset metadata
- every company/product asset behavior has provenance
- update_brands logo_path values remain synced with patch_products
- duplicate asset IDs and local path collisions are surfaced
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "assets" / "img" / "patch-logos"
ALLOWED_EXTENSIONS = {".svg", ".webp", ".png", ".jpg", ".jpeg"}
DATA_DIR = ROOT / "_data"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_external(value: str) -> bool:
    return "://" in value or value.startswith("//")


def normalized_asset_path(logo_path: str) -> str:
    return logo_path.split("?", 1)[0].strip()


def validate_logo_path(kind: str, entry_id: str, logo_path: str | None, errors: list[str]) -> str | None:
    if not logo_path:
        errors.append(f"{kind}:{entry_id}: missing logo_path")
        return None
    if is_external(str(logo_path)):
        errors.append(f"{kind}:{entry_id}: external logo_path not allowed: {logo_path}")
        return None
    asset_path = normalized_asset_path(str(logo_path))
    if not asset_path.startswith("/assets/img/patch-logos/"):
        errors.append(f"{kind}:{entry_id}: logo_path must point to /assets/img/patch-logos/: {logo_path}")
        return None
    ext = Path(asset_path).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"{kind}:{entry_id}: unsupported logo extension {ext}")
        return None
    file_path = ROOT / asset_path.lstrip("/")
    if not file_path.exists():
        errors.append(f"{kind}:{entry_id}: missing logo asset file: {asset_path}")
    return asset_path




def provenance_key(kind: str, entry_id: str) -> str:
    prefix = "company" if kind == "company" else "product"
    return f"{prefix}:{entry_id}"

def main() -> int:
    companies = load_yaml(DATA_DIR / "patch_companies.yml") or []
    products = load_yaml(DATA_DIR / "patch_products.yml") or []
    update_brands = load_yaml(DATA_DIR / "update_brands.yml") or {}
    logo_sources = load_yaml(DATA_DIR / "patch_logo_sources.yml") or {}
    provenance_entries = logo_sources.get("assets", [])

    errors: list[str] = []
    warnings: list[str] = []

    provenance_by_id: dict[str, dict[str, Any]] = {}
    provenance_ids = []
    for entry in provenance_entries:
        asset_id = entry.get("asset_id")
        if not asset_id:
            errors.append("provenance:<unknown>: missing asset_id")
            continue
        provenance_ids.append(asset_id)
        provenance_by_id[asset_id] = entry
        local_path = entry.get("local_path")
        validate_logo_path("provenance", asset_id, local_path, errors)
        if entry.get("source_type") not in set(logo_sources.get("allowed_source_types", [])):
            errors.append(f"provenance:{asset_id}: unsupported source_type {entry.get('source_type')}")
        if entry.get("attribution_required") is None:
            errors.append(f"provenance:{asset_id}: attribution_required must be true/false")
        if not entry.get("last_verified_at"):
            errors.append(f"provenance:{asset_id}: missing last_verified_at")

    for asset_id, count in Counter(provenance_ids).items():
        if count > 1:
            errors.append(f"provenance:{asset_id}: duplicate asset_id appears {count} times")

    company_ids = set()
    company_local_paths = defaultdict(list)
    for company in companies:
        cid = company.get("id")
        company_ids.add(cid)
        if not company.get("name") and not company.get("company_name"):
            errors.append(f"company:{cid}: missing name/company_name")
        if company.get("asset_type") != "company_logo":
            errors.append(f"company:{cid}: asset_type must be company_logo")
        asset_path = validate_logo_path("company", cid, company.get("logo_path"), errors)
        if asset_path:
            company_local_paths[asset_path].append(cid)
        ckey = provenance_key("company", cid)
        if ckey not in provenance_by_id:
            errors.append(f"company:{cid}: missing provenance entry in patch_logo_sources.yml")
        else:
            prov = provenance_by_id[ckey]
            if prov.get("kind") != "company_logo":
                errors.append(f"company:{cid}: provenance kind must be company_logo")
            if normalized_asset_path(str(company.get("logo_path"))) != normalized_asset_path(str(prov.get("local_path"))):
                errors.append(f"company:{cid}: logo_path does not match provenance local_path")

    products_by_id = {p.get("id"): p for p in products}
    for product in products:
        pid = product.get("id")
        if not product.get("product_id"):
            errors.append(f"product:{pid}: missing product_id")
        if not product.get("name") and not product.get("product_name"):
            errors.append(f"product:{pid}: missing name/product_name")
        cid = product.get("company_id")
        if cid not in company_ids:
            errors.append(f"product:{pid}: company_id {cid} not found in patch_companies.yml")
        asset_type = product.get("asset_type")
        if asset_type not in {"product_icon", "company_fallback"}:
            errors.append(f"product:{pid}: asset_type must be product_icon or company_fallback")
        asset_path = validate_logo_path("product", pid, product.get("logo_path"), errors)
        pkey = provenance_key("product", pid)
        if pkey not in provenance_by_id:
            errors.append(f"product:{pid}: missing provenance entry in patch_logo_sources.yml")
        else:
            prov = provenance_by_id[pkey]
            expected_kind = "product_icon" if asset_type == "product_icon" else "company_fallback"
            if prov.get("kind") != expected_kind:
                errors.append(f"product:{pid}: provenance kind must be {expected_kind}")
            if normalized_asset_path(str(product.get("logo_path"))) != normalized_asset_path(str(prov.get("local_path"))):
                errors.append(f"product:{pid}: logo_path does not match provenance local_path")
        if asset_type == "company_fallback":
            if product.get("fallback_to_company_logo") is not True:
                errors.append(f"product:{pid}: company_fallback requires fallback_to_company_logo: true")
            expected_company_logo = next((c.get("logo_path") for c in companies if c.get("id") == cid), None)
            if expected_company_logo and normalized_asset_path(str(product.get("logo_path"))) != normalized_asset_path(str(expected_company_logo)):
                errors.append(f"product:{pid}: company_fallback logo_path must equal parent company logo_path")
        elif product.get("fallback_to_company_logo") not in {False, None}:
            errors.append(f"product:{pid}: product_icon must not set fallback_to_company_logo true")

    # update_brands must stay synced where source_id/id maps to patch_products.
    for brand_id, brand in update_brands.items():
        logo_path = brand.get("logo_path")
        validate_logo_path("update_brand", brand_id, logo_path, errors)
        product = products_by_id.get(brand_id)
        if product:
            if normalized_asset_path(str(logo_path)) != normalized_asset_path(str(product.get("logo_path"))):
                errors.append(f"update_brand:{brand_id}: logo_path is not synced with patch_products.yml")

    # Local asset files should not have duplicate basenames under the patch-logo root.
    asset_files = [p.name for p in ASSET_ROOT.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS]
    for name, count in Counter(asset_files).items():
        if count > 1:
            errors.append(f"asset-file:{name}: duplicate filename collision")

    # Warn, don't fail, for unused local assets. They may be staging/legacy assets.
    referenced_paths = set()
    for dataset in (companies, products, update_brands.values()):
        for entry in dataset:
            lp = entry.get("logo_path") if isinstance(entry, dict) else None
            if lp and not is_external(str(lp)):
                referenced_paths.add(normalized_asset_path(str(lp)))
    for file_path in ASSET_ROOT.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in ALLOWED_EXTENSIONS:
            site_path = "/" + str(file_path.relative_to(ROOT)).replace("\\", "/")
            if site_path not in referenced_paths:
                warnings.append(f"asset-file:{file_path.name}: local asset exists but is not referenced by current company/product/update_brand data")

    print(f"Validated {len(companies)} companies, {len(products)} products, {len(update_brands)} update brand records, and {len(provenance_entries)} provenance entries.")
    if warnings:
        print(f"Warnings: {len(warnings)}")
        for item in warnings:
            print(f"WARNING: {item}")
    if errors:
        print(f"Errors: {len(errors)}", file=sys.stderr)
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print("Logo asset validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
