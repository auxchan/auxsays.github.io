#!/usr/bin/env python3
"""Static structural tests for the product-page patch-history layout.

No Jekyll engine is available offline, so these assert the SOURCE of the product-history
templates (the layout + its two table includes + the sort module). They lock the behaviour
the presentation sprint introduced:

  - a numeric-YYYYMM Recent (build year + prior December) vs year-grouped Older split;
  - a collapsed, year-anchored archive that hides when empty and never drops undated records;
  - the exact new column labels (Date / Version / Verdict / Reports / Evidence / Details);
  - a Verdict column derived from the real AUXSAYS decision (update_decision_label -> quick_verdict
    fallback, the patch-detail contract) -- never the community-consensus label -- with a fixed
    risk-rank order emitted server-side;
  - sortable, aria-sort headers with a non-sortable Details action column;
  - every record link preserved as a server-rendered crawlable anchor (routes unchanged).

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_product_page_layout.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

LAYOUT = (_AUX / "_layouts" / "aux-patch-product.html").read_text(encoding="utf-8")
HEAD = (_AUX / "_includes" / "patch-table-head.html").read_text(encoding="utf-8")
ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
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
    print("Product-page patch-history layout tests")
    print("=" * 60)

    # --- Column labels (exact) ------------------------------------------------
    for col, sort_key in [("Date", "date"), ("Version", "version"), ("Verdict", "verdict-rank"),
                          ("Reports", "reports"), ("Evidence", "evidence-rank")]:
        check(f"sortable column '{col}' present with data-sort-key='{sort_key}'",
              f'data-sort-key="{sort_key}"' in HEAD and f">{col}<" in HEAD, sort_key)
    check("Details is an action column, NOT sortable (no sort button/key)",
          'patch-col-details">Details' in HEAD and 'data-sort-key="details"' not in HEAD)
    check("old grid/labels removed (no 'Patch'/'Consensus'/'Confirmed community reports' headers)",
          "patch-version-row--head" not in LAYOUT and "<span>Consensus</span>" not in LAYOUT)

    # --- Recent window: numeric YYYYMM cutoff (build year + prior December) ---
    check("build year derives from site.time deterministically",
          "site.time | date: '%Y' | plus: 0" in LAYOUT)
    check("recent boundary is numeric YYYYMM = prior-year December (not a string compare)",
          "| minus: 1 | times: 100 | plus: 12" in LAYOUT)
    check("row month key is numeric YYYYMM (date '%Y%m' | plus: 0)",
          "date: '%Y%m' | plus: 0" in LAYOUT)
    check("recent = iym >= recent_boundary; older = iym < recent_boundary",
          "iym >= recent_boundary" in LAYOUT and "iym < recent_boundary" in LAYOUT)
    check("no ISO-string >= date comparison is used for the split (constraint 1)",
          "update_published_at >= " not in LAYOUT.replace("u.update_published_at", "u_field"))

    # --- Archive: year-grouped, newest-first, collapsed, anchored, hides empty --
    check("older records grouped by calendar year via group_by_exp date '%Y'",
          'group_by_exp: "u", "u.update_published_at | date' in LAYOUT)
    check("year groups ordered newest to oldest", '| sort: "name" | reverse' in LAYOUT)
    check("each archived year is a collapsed <details> with a stable #patches-<year> anchor",
          '<details class="aux-collapsible-card patch-archive-year" id="patches-{{ yg.name }}">' in LAYOUT)
    check("archive year groups are collapsed by default (no 'open' attribute)",
          'patch-archive-year" id="patches-{{ yg.name }}"> ' not in LAYOUT
          and 'patch-archive-year"' in LAYOUT and " open>" not in LAYOUT)
    check("each year group shows its record count", "patch-archive-count" in LAYOUT and "yr_count" in LAYOUT)
    check("archive section is hidden entirely when there are no older records",
          "{% if has_older %}" in LAYOUT)
    check("undated records are surfaced in an explicit group, never silently dropped",
          'id="patches-undated"' in LAYOUT
          and 'where_exp: "u", "u.update_published_at == nil"' in LAYOUT)

    # --- Recent section: title + restrained empty state -----------------------
    check("recent section titled 'Recent patches'", "Recent patches" in LAYOUT)
    check("older section titled 'Older patches'", "Older patches" in LAYOUT)
    check("restrained 'No recent patches' state when the recent window is empty",
          "No recent patches" in LAYOUT and "{% if recent_count > 0 %}" in LAYOUT)

    # --- Verdict column derived from the real AUXSAYS decision (not consensus) --
    check("verdict uses update_decision_label with the detail-page fallback chain",
          "item.update_decision_label" in ROW
          and "item.update_consensus_summary contains ':'" in ROW
          and "item.quick_verdict" in ROW)
    check("verdict falls back to INSUFFICIENT DATA, and official-only + 0 reports resolves to it",
          "'INSUFFICIENT DATA'" in ROW and "is_official_only and report_count_num == 0" in ROW)
    check("verdict column never substitutes the community-consensus label",
          "update_consensus_label" not in ROW)
    # explicit risk order AVOID(0) .. MANUAL WATCH(7), unknown(99, still visible)
    order = [("AVOID", 0), ("WAIT", 1), ("TEST FIRST", 2), ("SECURITY UPDATE", 3),
             ("SAFE ENOUGH", 4), ("OFFICIAL ONLY", 5), ("INSUFFICIENT DATA", 6), ("MANUAL WATCH", 7)]
    for cat, rank in order:
        check(f"verdict rank: '{cat}' -> {rank}",
              (f"vkey contains '{cat}' %}}{{% assign verdict_rank = {rank} %}}" in ROW))
    check("unknown/malformed verdict sorts last (rank 99) but stays visible",
          "{% assign verdict_rank = 99 %}" in ROW and "{{ decision_label }}" in ROW)

    # --- Sort keys emitted server-side; JS only orders them -------------------
    for attr in ["data-date=", "data-version=", "data-verdict-rank=", "data-reports=", "data-evidence-rank="]:
        check(f"row emits {attr} sort key", attr in ROW)
    check("date sort key is the normalized ISO published_at",
          'data-date="{{ item.update_published_at }}"' in ROW)
    check("JS sorts the emitted numeric verdict rank, never reinterprets verdict text at runtime",
          'data-sort-key="verdict-rank"' in HEAD and "dataset[camel]" in JS)

    # --- Routes/links preserved (SEO) ----------------------------------------
    check("every row keeps a crawlable server-rendered Details anchor to the record permalink",
          '<a class="patch-details-link" href="{{ item.url | relative_url }}"' in ROW)
    check("record collection is unchanged (same product_updates query)",
          'site.pages | where: "update_entry", true | where: "product_id", page.product_id | sort: "update_published_at" | reverse' in LAYOUT)
    check("full-set count displays are unchanged (product_updates.size)",
          "{{ product_updates.size }}" in LAYOUT)

    # --- Accessibility + JS wiring -------------------------------------------
    check("headers carry aria-sort and use real <button> controls",
          "aria-sort=" in HEAD and 'class="patch-sort-btn"' in HEAD)
    check("JS updates aria-sort and provides a consistent mobile Sort control",
          "aria-sort" in JS and "patch-sort-mobile" in JS)
    check("layout loads the sort module as an ES module (progressive enhancement)",
          "assets/js/patch-table-sort.mjs" in LAYOUT and 'type="module"' in LAYOUT)
    check("sort module + its node test exist",
          (_AUX / "assets" / "js" / "patch-table-sort.mjs").exists()
          and (_AUX / "assets" / "js" / "patch-table-sort.test.mjs").exists())

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
