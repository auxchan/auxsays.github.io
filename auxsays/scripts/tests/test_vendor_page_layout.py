#!/usr/bin/env python3
"""Static structural tests for the unified vendor patch-history presentation.

No Jekyll engine is available offline, so these assert the SOURCE of the vendor layout and the
SHARED includes it reuses (the same patch-history / patch-table-head / patch-table-row / sort
module used by the product page), locking the consistency the unification sprint introduced:

  - vendor tables use the shared Date / Product / Version / Verdict / Reports / Evidence / Details
    contract (never the legacy Software / Patch / Consensus / Confirmed reports grid);
  - vendor and product pages derive verdict + evidence from the SAME shared row include;
  - a compact "Latest patch signals" summary shows one latest record per product;
  - a Product column appears only when the vendor tracks more than one product;
  - the Recent/Older cutoff + archive come from the shared patch-history include;
  - Details is never sortable; every record link is server-rendered; honest empty states.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_vendor_page_layout.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

VENDOR = (_AUX / "_layouts" / "aux-patch-company.html").read_text(encoding="utf-8")
PRODUCT = (_AUX / "_layouts" / "aux-patch-product.html").read_text(encoding="utf-8")
HISTORY = (_AUX / "_includes" / "patch-history.html").read_text(encoding="utf-8")
HEAD = (_AUX / "_includes" / "patch-table-head.html").read_text(encoding="utf-8")
ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
LATEST = (_AUX / "_includes" / "patch-latest-signals.html").read_text(encoding="utf-8")
JS = (_AUX / "assets" / "js" / "patch-table-sort.mjs").read_text(encoding="utf-8")

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
        print(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))
        _ERRORS.append(label)


def run() -> int:
    print("=" * 60)
    print("Vendor patch-history unification tests")
    print("=" * 60)

    # 1. legacy vendor grid removed (no Software/Patch/Consensus/Confirmed reports table)
    check("legacy documented-updates grid removed from vendor layout",
          "patch-version-row--head" not in VENDOR
          and "<span>Consensus</span>" not in VENDOR
          and "Confirmed reports" not in VENDOR)

    # 2. vendor history uses the SHARED patch-history include (not a second implementation)
    check("vendor layout renders history via the shared patch-history include",
          "{% include patch-history.html updates=company_updates show_product=vendor_multi %}" in VENDOR)
    # 3. product page uses the SAME shared include -> identical verdict/evidence derivation
    check("product page uses the same shared patch-history include",
          "patch-history.html" in PRODUCT)
    check("verdict/evidence derivation lives ONCE in the shared row include (not copied per layout)",
          "item.update_decision_label" in ROW
          and "item.update_decision_label" not in VENDOR
          and "item.update_decision_label" not in PRODUCT
          and "update_consensus_label" not in ROW)

    # 4/5. Latest patch signals: one latest record per product, newest first
    check("vendor page includes the 'Latest patch signals' summary",
          "patch-latest-signals.html" in VENDOR and "Latest patch signals" in LATEST)
    check("latest summary selects one record per product (dedup by product_id, source is date-desc)",
          "latest_seen" in LATEST and "item.product_id" in LATEST and "update_published_at" in LATEST)
    check("latest summary reuses the shared row (no duplicated verdict logic)",
          "patch-table-row.html" in LATEST)

    # 6/7. Product column only for multi-product vendors; single-product is deterministic
    check("multi-product flag derives from products.size > 1",
          "{% if products.size > 1 %}{% assign vendor_multi = true %}" in VENDOR)
    check("vendor history + summary pass show_product=vendor_multi",
          "show_product=vendor_multi" in VENDOR)
    check("single-product vendor gets a prominent full-history CTA",
          "vendor_multi == false" in VENDOR and "View full" in VENDOR and "single_product.product_url" in VENDOR)
    check("head include adds the Product column only when show_product",
          "{% if include.show_product %}" in HEAD and 'data-sort-key="product"' in HEAD and 'data-sort-type="text"' in HEAD)
    check("row include adds the Product cell + data-product only when show_product",
          "{% if include.show_product %}" in ROW and 'data-product="{{ product_name | escape }}"' in ROW)

    # 8/9/10. Recent cutoff is the SHARED contract (build year + prior December, numeric YYYYMM)
    check("recent cutoff = build year + prior December via numeric YYYYMM (shared include)",
          "| minus: 1 | times: 100 | plus: 12" in HISTORY and "date: '%Y%m' | plus: 0" in HISTORY)
    check("recent uses iym >= boundary, older uses iym < boundary (Dec prior-year Recent, Nov Older)",
          "iym >= recent_boundary" in HISTORY and "iym < recent_boundary" in HISTORY)

    # 11. archive grouping + counts + collapsed + anchors + undated (shared)
    check("archive is year-grouped, newest-first, collapsed, #patches-YYYY, counted, with undated group",
          'group_by_exp: "u", "u.update_published_at | date' in HISTORY
          and '| sort: "name" | reverse' in HISTORY
          and 'id="patches-{{ yg.name }}"' in HISTORY
          and "patch-archive-count" in HISTORY
          and 'id="patches-undated"' in HISTORY
          and " open>" not in HISTORY)

    # 12. sorting contract matches the shared product table + adds Product (text)
    check("sort module supports natural-text Product sorting and derives columns from headers",
          "type === 'text'" in JS and "thead [data-sort-key]" in JS)
    check("Product column sorts as natural text; Version/Verdict/Reports/Evidence unchanged",
          'data-sort-key="product" data-sort-type="text"' in HEAD
          and 'data-sort-key="version" data-sort-type="version"' in HEAD
          and 'data-sort-key="verdict-rank" data-sort-type="num"' in HEAD)

    # 13. Details never sortable
    check("Details column has no sort key (not sortable)",
          'patch-col-details">Details' in HEAD and 'data-sort-key="details"' not in HEAD)

    # 14. every record link server-rendered
    check("row emits a server-rendered Details anchor + a Product->product-page link",
          '<a class="patch-details-link" href="{{ item.url | relative_url }}"' in ROW
          and "patch-cell-product" in ROW)
    check("latest-summary staged products still link to full history (server-rendered)",
          "patch-latest-staged__link" in LATEST and "product.product_url" in LATEST)

    # 16. honest empty/disabled states from STRUCTURED product/source state (not label strings)
    check("no-record state derives from the ingestion SOURCE enabled flag + coverage_state (structured)",
          "site.data.patch_ingestion_sources | where: \"product_id\", product.id" in LATEST
          and "src.enabled == true" in LATEST
          and "product.coverage_state" in LATEST)
    check("no-record state does NOT decide from human-readable coverage_status_label strings",
          "staged_lower" not in LATEST
          and "downcase" not in LATEST
          and "coverage_status_label | downcase" not in LATEST)
    check("disabled source -> 'Source disabled'/'staged' wording, never 'Monitoring active'",
          "Source disabled" in LATEST and "Monitoring active" in LATEST and "No configured ingestion source" in LATEST)
    check("unknown state fails closed to restrained neutral wording",
          "No patch records yet" in LATEST)

    # 17. routes: vendor layout does not alter permalinks; uses item.url; loads the shared module
    check("vendor layout preserves record URLs (uses item.url) and loads the shared sort module",
          "item.url" in ROW and "assets/js/patch-table-sort.mjs" in VENDOR and 'type="module"' in VENDOR)

    # shared-source existence
    check("shared includes + sort module exist",
          (_AUX / "_includes" / "patch-history.html").exists()
          and (_AUX / "_includes" / "patch-latest-signals.html").exists()
          and (_AUX / "assets" / "js" / "patch-table-sort.mjs").exists())

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        print("Failed tests:")
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
