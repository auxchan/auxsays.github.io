#!/usr/bin/env python3
"""Deterministic route-integrity tests for qa_patch_records.scan_route_integrity.

Product landing pages under /updates/<company>/<product>/ are emitted from explicit
route-source files (updates/<company>/<product>/index.md). This guards the class of bug
where a product is activated (catalog rows + generated patch records) but its landing route
source is missing, so the page 404s in production -- exactly what happened to
adobe-acrobat-pro after PR #21.

Offline only: fixtures are built in a temp directory and injected into scan_route_integrity;
no network, no repo writes.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_route_integrity.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import qa_patch_records as qa

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {label}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"\n        {detail}"
        print(msg)
        _ERRORS.append(label)


def _catalog():
    return [
        {"product_id": "adobe-acrobat-reader", "company_id": "adobe", "product_url": "/updates/adobe/adobe-acrobat-reader/"},
        {"product_id": "adobe-acrobat-pro", "company_id": "adobe", "product_url": "/updates/adobe/adobe-acrobat-pro/"},
    ]


def _records():
    return [
        {"product_id": "adobe-acrobat-reader", "company_id": "adobe", "_path": Path("rec-reader.md")},
        {"product_id": "adobe-acrobat-pro", "company_id": "adobe", "_path": Path("rec-pro.md")},
    ]


def _write_route(updates: Path, company: str, product: str, permalink: str | None = None) -> None:
    d = updates / company / product
    d.mkdir(parents=True, exist_ok=True)
    pl = permalink or f"/updates/{company}/{product}/"
    (d / "index.md").write_text(f"---\nlayout: aux-patch-product\ncompany_id: {company}\nproduct_id: {product}\npermalink: {pl}\n---\n", encoding="utf-8")


def _codes(errors):
    return sorted({e["code"] for e in errors})


def run() -> int:
    print("=" * 60)
    print("Route-integrity tests (product landing page emission)")
    print("=" * 60)

    # --- 1) PRIOR STATE: catalog + records present, Reader route present, Pro route MISSING ---
    with tempfile.TemporaryDirectory() as d:
        upd = Path(d) / "updates"
        _write_route(upd, "adobe", "adobe-acrobat-reader")  # Reader OK; Pro deliberately absent
        errors, _ = qa.scan_route_integrity(products=_catalog(), record_fronts=_records(), updates_dir=upd)
        codes = _codes(errors)
        pro_msgs = [e for e in errors if "adobe-acrobat-pro" in e["message"]]
        reader_msgs = [e for e in errors if "adobe-acrobat-reader" in e["message"]]
        check("prior-state fixture FAILS (missing Pro route)", len(errors) > 0, str(codes))
        check("flags product_landing_route_missing for Pro", "product_landing_route_missing" in codes)
        check("flags record_parent_route_missing for Pro", "record_parent_route_missing" in codes)
        check("errors are about adobe-acrobat-pro, not Reader", len(pro_msgs) >= 2 and len(reader_msgs) == 0, f"pro={len(pro_msgs)} reader={len(reader_msgs)}")

    # --- 2) CORRECTED STATE: add the Pro route source -> passes ---
    with tempfile.TemporaryDirectory() as d:
        upd = Path(d) / "updates"
        _write_route(upd, "adobe", "adobe-acrobat-reader")
        _write_route(upd, "adobe", "adobe-acrobat-pro")  # the fix
        errors, _ = qa.scan_route_integrity(products=_catalog(), record_fronts=_records(), updates_dir=upd)
        check("corrected fixture PASSES (Pro route added)", errors == [], str(_codes(errors)))

    # --- 3) generated record for a product missing from the catalog ---
    with tempfile.TemporaryDirectory() as d:
        upd = Path(d) / "updates"
        _write_route(upd, "adobe", "adobe-acrobat-reader")
        recs = _records() + [{"product_id": "ghost-product", "company_id": "ghost", "_path": Path("rec-ghost.md")}]
        cat = [c for c in _catalog() if c["product_id"] != "adobe-acrobat-pro"]  # drop pro so only reader is catalogued
        _write_route(upd, "adobe", "adobe-acrobat-pro")  # route exists so pro doesn't error
        errors, _ = qa.scan_route_integrity(products=cat, record_fronts=[r for r in recs if r["product_id"] != "adobe-acrobat-pro"] + [{"product_id": "ghost-product", "company_id": "ghost", "_path": Path("rec-ghost.md")}], updates_dir=upd)
        check("record for uncatalogued product_id fails", "record_product_not_in_catalog" in _codes(errors), str(_codes(errors)))

    # --- 4) duplicate product_id in the catalog ---
    with tempfile.TemporaryDirectory() as d:
        upd = Path(d) / "updates"
        _write_route(upd, "adobe", "adobe-acrobat-reader")
        dup = [
            {"product_id": "adobe-acrobat-reader", "company_id": "adobe", "product_url": "/updates/adobe/adobe-acrobat-reader/"},
            {"product_id": "adobe-acrobat-reader", "company_id": "adobe", "product_url": "/updates/adobe/adobe-acrobat-reader/"},
        ]
        errors, _ = qa.scan_route_integrity(products=dup, record_fronts=[], updates_dir=upd)
        check("duplicate product_id fails", "duplicate_product_id" in _codes(errors), str(_codes(errors)))

    # --- 5) duplicate landing permalink across route sources ---
    with tempfile.TemporaryDirectory() as d:
        upd = Path(d) / "updates"
        _write_route(upd, "adobe", "adobe-acrobat-reader", permalink="/updates/adobe/dup/")
        _write_route(upd, "adobe", "adobe-acrobat-pro", permalink="/updates/adobe/dup/")  # same permalink
        errors, _ = qa.scan_route_integrity(products=_catalog(), record_fronts=[], updates_dir=upd)
        check("duplicate landing permalink fails", "duplicate_landing_permalink" in _codes(errors), str(_codes(errors)))

    # --- 6) the REAL repo now passes route integrity (Pro route created by this PR) ---
    real_errors, _ = qa.scan_route_integrity()
    check("live repo passes route integrity (adobe-acrobat-pro route present)", real_errors == [], str(real_errors[:3]))

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for error in _ERRORS:
            print(f"  - {error}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
