#!/usr/bin/env python3
"""Static tests for the positive verdict state (CLEAR) + honest OFFICIAL ONLY read.

A zero-report official record no longer collapses to a bare "Insufficient data" shrug. It is
resolved from STRUCTURED state so it reads identically on the product page, vendor page, and
patch-detail page:

  - community-monitored product (site.monitored_products) + >= site.clear_min_days of field time
    + zero accepted reports  -> CLEAR (blue, never green; body says "not a safety guarantee")
  - not monitored            -> OFFICIAL ONLY (honest: no community watch, absence != stability)
  - monitored but too soon   -> INSUFFICIENT DATA

The claim's confidence is exposure-based (elapsed time under active monitoring), never a report
count -- CLEAR is an absence-of-problems statement, so it never says "safe".

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_positive_verdict_state.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
DETAIL = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
CONFIG = (_AUX / "_config.yml").read_text(encoding="utf-8")
JS = (_AUX / "assets" / "js" / "patch-table-sort.mjs").read_text(encoding="utf-8")
CSS = (_AUX / "assets" / "css" / "auxsays-custom.css").read_text(encoding="utf-8")

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
    print("Positive verdict state (CLEAR / OFFICIAL ONLY) tests")
    print("=" * 60)

    # --- config: monitored allowlist + tunable window ---------------------------
    check("config declares a community-monitored product allowlist",
          "monitored_products:" in CONFIG and "obs-studio" in CONFIG)
    check("config exposes a tunable clear_min_days window", "clear_min_days:" in CONFIG)

    # --- monitoring is decided from the allowlist (not inferred from a record field) --
    for src, name in ((ROW, "shared row include"), (DETAIL, "patch-detail page")):
        check(f"{name}: monitoring decided from site.monitored_products (structured, not label text)",
              "site.monitored_products contains" in src)
        check(f"{name}: elapsed field time gated by site.clear_min_days",
              "site.clear_min_days" in src and "86400" in src)
        check(f"{name}: emits CLEAR / OFFICIAL ONLY / INSUFFICIENT DATA branches",
              "'CLEAR'" in src and "'OFFICIAL ONLY'" in src and "'INSUFFICIENT DATA'" in src)
        check(f"{name}: CLEAR requires monitored AND >= clear_days (never on an unmonitored record)",
              "is_monitored and monitored_days >= clear_days" in src)

    # --- parity: same derivation inputs on both surfaces ------------------------
    check("product/vendor rows and the detail page share the same CLEAR gate (monitored + days)",
          "monitored_days >= clear_days" in ROW and "monitored_days >= clear_days" in DETAIL)

    # --- risk order: CLEAR is a distinct rank, mirrored in Liquid + JS ----------
    check("row emits data-verdict-rank 8 for CLEAR",
          "vkey contains 'CLEAR' %}{% assign verdict_rank = 8" in ROW)
    check("JS VERDICT_ORDER includes CLEAR (mirrors the Liquid rank)",
          "'CLEAR'" in JS and "VERDICT_ORDER" in JS)

    # --- never overclaims 'safe' ------------------------------------------------
    check("CLEAR is styled a calm blue, explicitly NOT green (no safety guarantee)",
          "patch-verdict--rank8" in CSS and ("not green" in CSS.lower() or "no safety" in CSS.lower()))
    check("detail-page CLEAR copy states it is NOT a safety guarantee, never says 'safe to install'",
          "not a safety guarantee" in DETAIL and "safe to install" not in DETAIL.lower())
    check("OFFICIAL ONLY copy is honest that absence of reports != stability",
          "not evidence of stability" in DETAIL)

    # --- a real report still yields an instant WAIT/AVOID (positive gate only on 0 reports) --
    check("positive states only apply when report_count is zero (a confirmed report -> instant verdict)",
          "report_count_num == 0" in ROW and "report_count == 0" in DETAIL)

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
