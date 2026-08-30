#!/usr/bin/env python3
"""Static lock tests for the shared per-patch MONITORING STATUS field.

The monitoring status is a SINGLE-SOURCE-OF-TRUTH include (_includes/monitoring-status.html) that
derives an evidence/collection status for one exact patch ONLY from structured method-health
telemetry (_data/evidence_method_health.yml), joined on (product_id, update_version). It is kept
strictly separate from the AUXSAYS verdict, uses NO manual product allowlist, and FAILS CLOSED on
any missing / ambiguous / stale / future / disabled / blocked / broken / partial / low-confidence /
manual-review telemetry. Raw blocked_reason is never emitted publicly.

These assert the SOURCE of the include + its wiring (no Jekyll engine offline). The exhaustive
per-mapping behaviour is locked separately by the deterministic fixture render
(test_monitoring_status_render.py) and by the real full-site build.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_monitoring_status.py
"""
from __future__ import annotations

import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_AUX = _REPO / "auxsays"

INCLUDE = (_AUX / "_includes" / "monitoring-status.html").read_text(encoding="utf-8")
ROW = (_AUX / "_includes" / "patch-table-row.html").read_text(encoding="utf-8")
HEAD = (_AUX / "_includes" / "patch-table-head.html").read_text(encoding="utf-8")
DETAIL = (_AUX / "_layouts" / "aux-update.html").read_text(encoding="utf-8")
FEED = (_AUX / "_layouts" / "aux-updates.html").read_text(encoding="utf-8")
CONFIG = (_AUX / "_config.yml").read_text(encoding="utf-8")

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
    print("Monitoring-status include tests")
    print("=" * 60)

    # --- Derived ONLY from EMH; no manual allowlist -----------------------------
    check("derives from site.data.evidence_method_health (structured per-patch telemetry)",
          "site.data.evidence_method_health" in INCLUDE)
    check("uses NO manual product allowlist (monitored == EMH rows exist)",
          "monitored_products" not in INCLUDE)
    check("joins on exact (product_id, update_version)",
          "where: 'product_id', include.product_id" in INCLUDE and "m.update_version" in INCLUDE)

    # --- Join keys are string-normalized (numeric YAML versions still match) -----
    check("version join keys string-normalized (numeric 2607 matches '2607')",
          "include.version | append: ''" in INCLUDE and "m.update_version | append: ''" in INCLUDE)

    # --- Config knobs (correct names; NOT the old *_success_* name) ---------------
    check("config declares monitoring_min_healthy_methods + monitoring_max_age_days",
          "monitoring_min_healthy_methods:" in CONFIG and "monitoring_max_age_days:" in CONFIG)
    check("include reads both tunables from site config",
          "site.monitoring_min_healthy_methods" in INCLUDE and "site.monitoring_max_age_days" in INCLUDE)
    check("no stale monitoring_min_success_methods naming remains",
          "monitoring_min_success_methods" not in INCLUDE and "monitoring_min_success_methods" not in CONFIG)

    # --- Healthy set = fresh post-release success/no_results ONLY -----------------
    check("healthy method requires status success OR no_results (nothing else counts)",
          "m_status == 'success' or m_status == 'no_results'" in INCLUDE)
    check("healthy requires post-release (last_run >= published) AND within max age",
          "m_run_s >= mon_pub_s" in INCLUDE and "m_age_s <= mon_max_age_s" in INCLUDE)

    # --- Fail-closed timestamp handling: future/invalid never valid/fresh/latest --
    check("future timestamps excluded from valid (last_run must be <= site.time)",
          "m_run_s <= mon_now_s" in INCLUDE)
    check("usable row with missing/future timestamp flags invalid telemetry (fail closed)",
          "mon_has_invalid_ts_usable = true" in INCLUDE)
    check("latest evidence run tracked only inside the valid-timestamp branch",
          "mon_latest_raw = m.last_run" in INCLUDE and "mon_latest_s = m_run_s" in INCLUDE)

    # --- degraded_present covers every degraded signal ---------------------------
    for tok in ["partial", "blocked", "broken", "stale", "low_confidence", "manual_review_needed"]:
        check(f"degraded status detection includes '{tok}'",
              f"m_status == '{tok}'" in INCLUDE)
    check("partial-disabled coverage fails closed (0 < disabled < total -> degraded)",
          "mon_disabled > 0 and mon_disabled < mon_total" in INCLUDE)
    check("degraded_present = bad status OR partial-disabled OR invalid timestamp",
          "mon_has_degraded_status or mon_partial_disabled or mon_has_invalid_ts_usable" in INCLUDE)

    # --- All eight status strings present ----------------------------------------
    for status in ["OFFICIAL SOURCE ONLY", "NOT YET MONITORED", "COLLECTION STALE",
                   "COLLECTION BLOCKED", "MONITORING DEGRADED", "INSUFFICIENT COVERAGE",
                   "MONITORING ACTIVE", "NO ACCEPTED PATCH-SPECIFIC REPORTS"]:
        check(f"emits status '{status}'", f"'{status}'" in INCLUDE)

    # --- Ladder ORDER is exactly the approved sequence (monotonic positions) -----
    ladder = [
        ("mon_total == 0", "1 no rows -> OFFICIAL SOURCE ONLY"),
        ("mon_disabled == mon_total", "2 every row disabled -> OFFICIAL SOURCE ONLY"),
        ("mon_has_valid_usable_ts == false", "3 no valid non-future ts -> COLLECTION STALE"),
        ("mon_has_post_release_valid == false", "4 none post-release -> NOT YET MONITORED"),
        ("mon_fresh_usable == 0", "5 none fresh -> COLLECTION STALE"),
        ("mon_healthy == 0 and mon_has_blocked_broken", "6 zero healthy + blocked -> COLLECTION BLOCKED"),
        ("mon_degraded_present", "7 degraded -> MONITORING DEGRADED"),
        ("mon_healthy < mon_min_healthy", "8 below minimum -> INSUFFICIENT COVERAGE"),
        ("mon_reports > 0", "9 accepted reports -> MONITORING ACTIVE"),
    ]
    positions = [INCLUDE.find(cond + " -%}") for cond, _ in ladder]
    check("every ladder branch is present", all(p != -1 for p in positions),
          str({ladder[i][1]: positions[i] for i in range(len(positions))}))
    check("ladder branches appear in the exact approved order",
          positions == sorted(positions), str(positions))

    # --- Raw blocked_reason is NEVER emitted publicly ----------------------------
    check("include never accesses/emits the raw blocked_reason field (normalized explanations only)",
          ".blocked_reason" not in INCLUDE)
    check("public method explanations are normalized, status-derived strings",
          "Source request was blocked" in INCLUDE and "Source returned an error" in INCLUDE
          and "Source requires manual review" in INCLUDE)
    # The method identity now renders as a PUBLIC SOURCE FAMILY (several methods deliberately read
    # the same community by different routes, and three raw ids made one community look like
    # three). The invariant is unchanged and is asserted on the property rather than on a variable
    # name: whatever carries that identity into the page is escaped, and the raw field is never
    # emitted unescaped.
    check("the rendered method identity is HTML-escaped",
          "m_family | escape" in INCLUDE or "m.method_id | escape" in INCLUDE)
    check("the family label is derived from the method id, not invented",
          "assign m_family = m.method_id" in INCLUDE)
    check("the raw method_id is never emitted unescaped",
          "{{ m.method_id }}" not in INCLUDE)
    check("routes over one community are labelled as that community",
          INCLUDE.count("Microsoft Q&A (") >= 2,
          "three Q&A routes must not read as three independent sources")
    # The coverage floor exists to require more than one COMMUNITY. Counting method rows let two
    # routes over the same community satisfy it, which is the same conflation one layer down from
    # the labels: measured live, two Q&A rows took 20228.20158 from healthy=1 to healthy=2 without
    # any new source being read.
    check("healthy coverage is counted per source family, not per method row",
          "mon_healthy_seen" in INCLUDE and "m.source_type" in INCLUDE)
    check("the family key is the evidence source_type, matching the ownership manifest",
          "assign m_fam = m.source_type" in INCLUDE)
    check("a family already counted cannot be counted twice",
          "unless mon_healthy_seen contains m_fam_key" in INCLUDE)
    check("the public fact is labelled sources, not methods",
          "<dt>Healthy sources</dt>" in INCLUDE and "<dt>Healthy methods</dt>" not in INCLUDE)

    # --- Verdict and Monitoring kept structurally separate on every surface -------
    check("detail page renders the full monitoring card (mode='full'), separate from #verdict",
          "monitoring-status.html mode='full'" in DETAIL)
    check("product/vendor rows render a separate, non-sortable Monitoring column",
          'patch-col-monitoring">Monitoring' in HEAD
          and 'data-label="Monitoring"' in ROW
          and "monitoring-status.html mode='cell'" in ROW
          and 'data-sort-key="monitoring' not in HEAD)
    check("monitoring status is NOT placed inside the Verdict cell",
          "monitoring-status.html" not in ROW.split('data-label="Verdict"')[1].split("</td>")[0])
    check("feed renders a separately labelled monitoring field in BOTH card loops",
          FEED.count("monitoring-status.html mode='feed'") == 2)

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
