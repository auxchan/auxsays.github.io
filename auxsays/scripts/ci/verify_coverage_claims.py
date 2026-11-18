#!/usr/bin/env python3
"""Refuse to publish a coverage claim the coverage projection does not support (AUX-102).

WHY. Catalog inclusion was never coupled to collection. A product entered `patch_products.yml` with
a hand-written "Monitoring active", its company page said it "is tracked by AUXSAYS", its product page
said it "is tracked for ... public release signals", and none of that was true for 30 of 47 products
(NVIDIA among them). The pills had already been fixed (AUX-039); nothing stopped the prose, the
catalog fields or the next new product from saying it again.

WHAT IT CHECKS. ERROR blocks the deploy; WARN is printed and never blocks.
  CATALOG    ERROR  `patch_products.yml` / `patch_companies.yml` carry none of the retired static
                    coverage fields (coverage_state, coverage_status_label, ingestion_status,
                    current_status_label, ingestion_active, dossier_note): coverage is derived, never
                    written by hand.
  DEBT       ERROR  `_data/coverage_debt.yml` is well formed and names catalog products only.
             ERROR  a Core product whose official lane is switched off by CONFIGURATION (no source, a
                    disabled source, a manual-only source) has a debt entry. Existing gaps are listed
                    there, so this refuses only a NEW one. A lane that is enabled and failing at
                    runtime is never refused: impairment changes the label, it does not stop a deploy.
             WARN   a debt entry for a product whose lane now operates (close it).
  PROJECTION ERROR  the deploy-time `_data/coverage_state.yml` exists, has one row per catalog product
                    and company, and every state and label is a member of the closed vocabulary.
  PILLS      ERROR  every coverage pill on the built site (an element carrying data-coverage-product or
                    data-coverage-company) shows exactly the state and label the projection gives that
                    product or company; every product page carries its own pill; and no page shows the
                    "Coverage status unknown" fallback, which only a render without the projection
                    produces.
  PROSE      ERROR  a product or company page whose coverage is not operating, and the Patch Feed hub,
                    carry none of the retired claim phrases ("is tracked by AUXSAYS", "is tracked for",
                    "Monitoring active", "official source mapped", ...).

Run:  python auxsays/scripts/ci/verify_coverage_claims.py --site auxsays/_site [--source auxsays]
Exit: 0 clean (warnings allowed), 1 an error, 2 the site directory is unusable.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

import build_coverage_projection as cov  # noqa: E402

FORBIDDEN_CATALOG_KEYS = ("coverage_state", "coverage_status_label", "ingestion_status",
                          "current_status_label", "ingestion_active", "dossier_note")
# Claim phrases retired by AUX-102. Case-sensitive on purpose: the per-patch monitoring card's own
# status vocabulary is upper case ("MONITORING ACTIVE") and describes community collection for one
# patch, which is a different, correctly derived claim.
CLAIM_PHRASES = ("is tracked by AUXSAYS", "is tracked for", "is tracked because", "tracking focuses on",
                 "Monitoring active", "official source mapped", "Source map staged", "not yet monitoring",
                 "OFFICIAL SOURCE ACTIVE")
HUB_PHRASES = ("is tracked by AUXSAYS", "is tracked because", "tracking focuses on", "Monitoring active",
               "tracked companies", "tracked software")
NOT_OPERATING = ("impaired", "planned", "not_monitored")

_PILL = re.compile(r"<span\b([^>]*\bdata-coverage-(product|company)=\"([^\"]*)\"[^>]*)>([^<]*)</span>", re.I)
_STATE_CLASS = re.compile(r"patch-coverage-pill--coverage-([a-z_]+)")
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def page_text(text: str) -> str:
    """Visible-ish text: scripts and styles dropped, tags removed, entities decoded, space collapsed."""
    return " ".join(html.unescape(_TAG.sub(" ", _SCRIPT.sub(" ", text))).split())


def url_to_file(site: Path, url: str) -> Path:
    rel = str(url or "").strip().lstrip("/")
    return site / rel / "index.html" if not rel.endswith(".html") else site / rel


def load_projection(path: Path) -> tuple[dict, dict] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    products = {str(r.get("product_id")): r for r in data.get("products") or [] if isinstance(r, dict)}
    companies = {str(r.get("company_id")): r for r in data.get("companies") or [] if isinstance(r, dict)}
    return products, companies


def check_data(source: Path, products_proj: dict | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    data = source / "_data"
    catalog = [p for p in (yaml.safe_load((data / "patch_products.yml").read_text(encoding="utf-8")) or [])
               if isinstance(p, dict)]
    companies = [c for c in (yaml.safe_load((data / "patch_companies.yml").read_text(encoding="utf-8")) or [])
                 if isinstance(c, dict)]
    for kind, rows, key in (("product", catalog, "id"), ("company", companies, "id")):
        for row in rows:
            found = [k for k in FORBIDDEN_CATALOG_KEYS if k in row]
            if found:
                errors.append(f"CATALOG {kind} {row.get(key)} carries a static coverage field {found}: "
                              f"coverage is derived by build_coverage_projection.py, never written by hand")
    try:
        debt = cov.load_debt(data / "coverage_debt.yml")
    except (ValueError, yaml.YAMLError) as exc:
        errors.append(f"DEBT the coverage debt file is unreadable: {exc}")
        debt = []
    ids = {cov.product_id_of(p) for p in catalog}
    errors += [f"DEBT {e}" for e in cov.debt_errors(debt, ids)]
    debt_ids = {str(e.get("product_id")) for e in debt}
    if products_proj is not None:
        for product in catalog:
            pid = cov.product_id_of(product)
            row = products_proj.get(pid) or {}
            if product.get("priority") == "Core" and row.get("official") in cov.OFFICIAL_OFF \
                    and pid not in debt_ids:
                errors.append(f"DEBT Core product {pid} has no operating official lane (official "
                              f"{row.get('official')}) and no entry in _data/coverage_debt.yml")
            if pid in debt_ids and row.get("state") in cov.OPERATING_STATES:
                warnings.append(f"DEBT {pid} now reads {row.get('state')}; close its coverage debt entry")
    return errors, warnings


def check_projection(catalog_ids: set[str], company_ids: set[str], products: dict,
                     companies: dict) -> list[str]:
    errors = []
    for pid in sorted(catalog_ids - set(products)):
        errors.append(f"PROJECTION no coverage row for catalog product {pid}")
    for cid in sorted(company_ids - set(companies)):
        errors.append(f"PROJECTION no coverage row for company {cid}")
    for pid, row in sorted(products.items()):
        state = row.get("state")
        if state not in cov.COVERAGE_STATES or row.get("label") != cov.COVERAGE_LABELS.get(state):
            errors.append(f"PROJECTION product {pid}: state {state!r} / label {row.get('label')!r} "
                          f"is not a vocabulary pair")
    for cid, row in sorted(companies.items()):
        if row.get("state") not in cov.COMPANY_STATES or not str(row.get("label") or "").strip():
            errors.append(f"PROJECTION company {cid}: state {row.get('state')!r} is not in the vocabulary")
    return errors


def check_site(site: Path, catalog: list[dict], companies_cat: list[dict], products: dict,
               companies: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    stats = {"pages": 0, "pills": 0, "product_pages": 0, "company_pages": 0}
    product_pages: dict[Path, str] = {}
    company_pages: dict[Path, str] = {}
    for product in catalog:
        product_pages[url_to_file(site, product.get("product_url"))] = cov.product_id_of(product)
    for company in companies_cat:
        company_pages[url_to_file(site, company.get("company_url"))] = str(company.get("id"))
    hub = site / "updates" / "index.html"

    for path in sorted(site.rglob("*.html")):
        stats["pages"] += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(site).as_posix()
        if cov.UNKNOWN_LABEL in text or "patch-coverage-pill--coverage-unknown" in text:
            errors.append(f"PILLS {rel} shows the '{cov.UNKNOWN_LABEL}' fallback: the coverage "
                          f"projection was missing or incomplete when it was built")
        for attrs, kind, ident, label in _PILL.findall(text):
            stats["pills"] += 1
            want = (products if kind.lower() == "product" else companies).get(ident)
            m = _STATE_CLASS.search(attrs)
            got_state, got_label = (m.group(1) if m else ""), " ".join(html.unescape(label).split())
            if want is None:
                errors.append(f"PILLS {rel}: a pill names {kind} {ident!r}, which has no projection row")
            elif (got_state, got_label) != (want.get("state"), want.get("label")):
                errors.append(f"PILLS {rel}: {kind} {ident} shows ({got_state!r}, {got_label!r}); the "
                              f"projection says ({want.get('state')!r}, {want.get('label')!r})")
        pid = product_pages.get(path)
        if pid is not None:
            stats["product_pages"] += 1
            if f'data-coverage-product="{pid}"' not in text:
                errors.append(f"PILLS {rel}: the product page for {pid} carries no coverage pill of its own")
            state = (products.get(pid) or {}).get("state")
            if state in NOT_OPERATING:
                visible = page_text(text)
                for phrase in CLAIM_PHRASES:
                    if phrase in visible:
                        errors.append(f"PROSE {rel}: {pid} is {state} but the page says {phrase!r}")
        cid = company_pages.get(path)
        if cid is not None:
            stats["company_pages"] += 1
            state = (companies.get(cid) or {}).get("state")
            if state in NOT_OPERATING:
                visible = page_text(text)
                for phrase in CLAIM_PHRASES:
                    if phrase in visible:
                        errors.append(f"PROSE {rel}: company {cid} is {state} but the page says {phrase!r}")
        if path == hub:
            visible = page_text(text)
            for phrase in HUB_PHRASES:
                if phrase in visible:
                    errors.append(f"PROSE {rel}: the Patch Feed hub says {phrase!r}")
    for path, pid in sorted(product_pages.items()):
        if not path.is_file():
            errors.append(f"PILLS no built product page for {pid} at {path.relative_to(site).as_posix()}")
    return errors, stats


def verify(site: Path, source: Path, projection_path: Path | None = None) -> tuple[list[str], list[str], dict]:
    projection_path = projection_path or source / "_data" / cov.OUTPUT_PATH.name
    loaded = load_projection(projection_path)
    errors: list[str] = []
    if loaded is None:
        errors.append(f"PROJECTION {projection_path} is missing or unreadable: the deploy must build it "
                      f"before jekyll build")
        products, companies = {}, {}
    else:
        products, companies = loaded
    data_errors, warnings = check_data(source, products if loaded is not None else None)
    errors += data_errors
    data = source / "_data"
    catalog = [p for p in yaml.safe_load((data / "patch_products.yml").read_text(encoding="utf-8")) or []
               if isinstance(p, dict)]
    companies_cat = [c for c in yaml.safe_load((data / "patch_companies.yml").read_text(encoding="utf-8")) or []
                     if isinstance(c, dict)]
    stats: dict[str, Any] = {}
    if loaded is not None:
        errors += check_projection({cov.product_id_of(p) for p in catalog},
                                   {str(c.get("id")) for c in companies_cat}, products, companies)
        site_errors, stats = check_site(site, catalog, companies_cat, products, companies)
        errors += site_errors
    return errors, warnings, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--site", required=True, type=Path, help="the built site directory")
    ap.add_argument("--source", type=Path, default=None, help="the Jekyll source (default: the site's parent)")
    ap.add_argument("--projection", type=Path, default=None,
                    help="the coverage projection (default: <source>/_data/coverage_state.yml)")
    args = ap.parse_args(argv)
    if not (args.site / "index.html").is_file():
        print(f"verify_coverage_claims: {args.site} has no index.html", file=sys.stderr)
        return 2
    source = args.source if args.source is not None else args.site.resolve().parent
    if not (source / "_data" / "patch_products.yml").is_file():
        print(f"verify_coverage_claims: {source} is not the Jekyll source", file=sys.stderr)
        return 2
    errors, warnings, stats = verify(args.site, source, args.projection)
    if stats:
        print(f"pages {stats['pages']}; coverage pills {stats['pills']}; product pages "
              f"{stats['product_pages']}; company pages {stats['company_pages']}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        print(f"verify_coverage_claims: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"verify_coverage_claims: clean ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
