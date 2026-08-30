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

import re
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

LAYOUT = (_AUX / "_layouts" / "aux-patch-product.html").read_text(encoding="utf-8")
HEAD = (_AUX / "_includes" / "patch-table-head.html").read_text(encoding="utf-8")
ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
JS = (_AUX / "assets" / "js" / "patch-table-sort.mjs").read_text(encoding="utf-8")
# The Recent/Older orchestration was extracted into the shared patch-history include (used by both
# the product and vendor layouts). Assertions about that orchestration read it there.
HISTORY = (_AUX / "_includes" / "patch-history.html").read_text(encoding="utf-8")
LH = LAYOUT + "\n" + HISTORY  # "in the product page as rendered" = layout + its shared history include

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

    # --- Monitoring column: a SEPARATE, non-sortable axis (never inside the Verdict cell) ------
    check("Monitoring is a separate, non-sortable column (own <th>, no sort button/key)",
          'patch-col-monitoring">Monitoring' in HEAD and 'data-sort-key="monitoring' not in HEAD)
    check("row renders the shared monitoring-status include in its own Monitoring cell",
          'data-label="Monitoring"' in ROW and "include monitoring-status.html mode='cell'" in ROW)
    check("Verdict cell holds only the verdict badge (monitoring status is NOT placed in it)",
          '<td data-label="Verdict"><span class="patch-verdict' in ROW
          and "monitoring-status.html" not in ROW.split('data-label="Verdict"')[1].split("</td>")[0])

    check("product layout delegates the history to the shared patch-history include",
          "patch-history.html" in LAYOUT and "show_product=false" in LAYOUT)

    # --- Recent window: numeric YYYYMM cutoff (build year + prior December) ---
    check("build year derives from site.time deterministically",
          "site.time | date: '%Y' | plus: 0" in HISTORY)
    check("recent boundary is numeric YYYYMM = prior-year December (not a string compare)",
          "| minus: 1 | times: 100 | plus: 12" in HISTORY)
    check("row month key is numeric YYYYMM (date '%Y%m' | plus: 0)",
          "date: '%Y%m' | plus: 0" in HISTORY)
    check("recent = iym >= recent_boundary; older = iym < recent_boundary",
          "iym >= recent_boundary" in HISTORY and "iym < recent_boundary" in HISTORY)
    check("no ISO-string >= date comparison is used for the split (constraint 1)",
          "update_published_at >= " not in HISTORY.replace("u.update_published_at", "u_field"))

    # --- Archive: year-grouped, newest-first, collapsed, anchored, hides empty --
    check("older records grouped by calendar year via group_by_exp date '%Y'",
          'group_by_exp: "u", "u.update_published_at | date' in HISTORY)
    check("year groups ordered newest to oldest", '| sort: "name" | reverse' in HISTORY)
    check("each archived year is a collapsed <details> with a stable #patches-<year> anchor",
          '<details class="aux-collapsible-card patch-archive-year" id="patches-{{ yg.name }}">' in HISTORY)
    check("archive year groups are collapsed by default (no 'open' attribute)",
          'patch-archive-year" id="patches-{{ yg.name }}"> ' not in HISTORY
          and 'patch-archive-year"' in HISTORY and " open>" not in HISTORY)
    check("each year group shows its record count", "patch-archive-count" in HISTORY and "yr_count" in HISTORY)
    check("archive section is hidden entirely when there are no older records",
          "{% if has_older %}" in HISTORY)
    check("undated records are surfaced in an explicit group, never silently dropped",
          'id="patches-undated"' in HISTORY
          and 'where_exp: "u", "u.update_published_at == nil"' in HISTORY)

    # --- Recent section: title + restrained empty state -----------------------
    check("recent section titled 'Recent patches'", "Recent patches" in HISTORY)
    check("older section titled 'Older patches'", "Older patches" in HISTORY)
    check("restrained 'No recent patches' state when the recent window is empty",
          "No recent patches" in HISTORY and "{% if recent_count > 0 %}" in HISTORY)

    # --- Verdict column derived from the real AUXSAYS decision (not consensus) --
    # Intent, not spelling: the chain must READ all three fields, in that order. Each may be
    # normalised through a `default`-ed local first -- it now has to be, because the old
    # `decision_label == blank` test could never be true (Liquid resolves the `blank` literal to
    # MethodLiteral(:blank?) and nothing here defines String#blank?), which made every fallback
    # branch unreachable and left 35 Verdict cells blank on one live product page.
    # A field may now be read into a `default`-ed local at the top of the include, so first-mention
    # order no longer encodes priority. Assert the BRANCH order instead: whichever locals carry the
    # consensus summary and the quick verdict, the summary must be split before the verdict is,
    # and INSUFFICIENT DATA must come last.
    def local_for(field: str) -> str:
        m = re.search(r"assign\s+(\w+)\s*=\s*item\." + field + r"\b", ROW)
        return m.group(1) if m else "item." + field
    summary_split = ROW.find(f"= {local_for('update_consensus_summary')} | split")
    verdict_split = ROW.find(f"= {local_for('quick_verdict')} | split")
    last_resort = ROW.find("'INSUFFICIENT DATA'")
    reads = [ROW.find(f) for f in ("item.update_decision_label", "item.update_consensus_summary",
                                  "item.quick_verdict")]
    check("verdict uses update_decision_label with the detail-page fallback chain",
          all(i != -1 for i in reads) and "contains ':'" in ROW
          and -1 < summary_split < verdict_split < last_resort,
          f"reads={reads} summary={summary_split} verdict={verdict_split} last={last_resort}")
    check("the verdict fallback is reachable -- guarded on emptiness, not on `blank`",
          re.search(r"decision_label\s*==\s*(?:''|\"\")", ROW) is not None
          and re.search(r"decision_label\s*(?:==|!=)\s*blank\b", ROW) is None)
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
