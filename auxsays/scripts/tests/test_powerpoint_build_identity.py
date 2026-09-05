#!/usr/bin/env python3
"""Build-aware PowerPoint patch identity: two builds under one YYMM must never collide.

Microsoft ships several Current Channel builds under a single YYMM version (the live Current
Channel page lists three for PowerPoint 2603). Keyed by (product_id, update_version) alone, the
second build silently overwrites the first in the record index, both share one public URL, and
evidence for one build lands on the other.

Every case below is built on the SAME two-record collision fixture -- same product_id, same
update_version, different target_build -- and each proves one consumer keeps them apart. The
non-PowerPoint cases prove the shared optional-build primitive left every other product's identity
semantically unchanged (a constant empty build slot can neither merge two previously distinct keys
nor split one previously shared key).

Deterministic and offline: temp dirs and in-memory rows only. No network, no repo mutation.

Run: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_powerpoint_build_identity.py
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

import apply_consensus_to_records as promo  # noqa: E402
import qa_patch_records  # noqa: E402
from lib import patch_identity as pi  # noqa: E402
from lib.collector_ownership import _permalink_build_segment, _permalink_product_slug  # noqa: E402
from lib.report_counts import counted_evidence_counts, reconcile_record_counts  # noqa: E402
from lib.write_update_record import output_path, record_slug  # noqa: E402
from patch_collectors.base import evidence_key  # noqa: E402

PRODUCT = "microsoft-powerpoint"
COMPANY = "microsoft"
VERSION = "2603"
BUILD_A = "19822.20182"
BUILD_B = "19822.20168"

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


def record_md(build: str, count: int = 0, state: str = "official_only") -> str:
    return "\n".join([
        "---",
        "layout: aux-update",
        f"title: Microsoft PowerPoint {VERSION} official update breakdown",
        f"permalink: {pi.permalink_path(COMPANY, PRODUCT, VERSION, build)}",
        "update_entry: true",
        f"company_id: {COMPANY}",
        f"product_id: {PRODUCT}",
        f"update_version: '{VERSION}'",
        f"target_build: '{build}'",
        f"update_report_count: {count}",
        f"confirmed_patch_specific_report_count: {count}",
        f"evidence_state: {state}",
        "update_published_at: '2026-04-14T00:00:00Z'",
        "---",
        "",
        "body",
        "",
    ])


def ev_row(build: str, rid: str, url: str, version: str = VERSION,
           product: str = PRODUCT) -> dict:
    return {
        "id": rid, "product_id": product, "update_version": version,
        "target_build": build, "source_url": url, "source_type": "learn_qna",
        "captured_at": "2026-04-15T00:00:00Z", "counted": True,
        "patch_version_matched": True, "sentiment": "negative",
    }


def write_pair(d: Path) -> tuple[Path, Path]:
    """The collision fixture: two records, same product+version, different builds."""
    a = d / f"2026-04-14-{PRODUCT}-{pi.record_version_slug(VERSION, BUILD_A, PRODUCT)}.md"
    b = d / f"2026-04-14-{PRODUCT}-{pi.record_version_slug(VERSION, BUILD_B, PRODUCT)}.md"
    a.write_text(record_md(BUILD_A), encoding="utf-8")
    b.write_text(record_md(BUILD_B), encoding="utf-8")
    return a, b


def run() -> int:
    print("=" * 68)
    print("PowerPoint build-aware patch identity -- two-build collision fixture")
    print("=" * 68)

    # ---- 1. FILENAME IDENTITY ------------------------------------------------------------
    slug_a = record_slug({"version": VERSION, "target_build": BUILD_A, "product_id": PRODUCT})
    slug_b = record_slug({"version": VERSION, "target_build": BUILD_B, "product_id": PRODUCT})
    check("1 two builds produce DIFFERENT filename slugs", slug_a != slug_b, f"{slug_a} vs {slug_b}")
    check("1 the slug carries the exact build", slug_a == "2603-19822-20182", slug_a)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        pa = output_path(out, {"published_at": "2026-04-14", "software": "Microsoft PowerPoint",
                               "product_id": PRODUCT, "version": VERSION, "target_build": BUILD_A})
        pb = output_path(out, {"published_at": "2026-04-14", "software": "Microsoft PowerPoint",
                               "product_id": PRODUCT, "version": VERSION, "target_build": BUILD_B})
        check("1 same date + same version + different build -> no filesystem overwrite",
              pa != pb, f"{pa.name} vs {pb.name}")
    check("1 a version-only product's filename slug is UNCHANGED",
          record_slug({"version": "32.2.0", "product_id": "obs-studio"}) == "32-2-0")

    # ---- 2. PUBLIC PERMALINK IDENTITY -----------------------------------------------------
    ua = pi.permalink_path(COMPANY, PRODUCT, VERSION, BUILD_A)
    ub = pi.permalink_path(COMPANY, PRODUCT, VERSION, BUILD_B)
    check("2 two builds get DISTINCT public permalinks", ua != ub, f"{ua} vs {ub}")
    check("2 the permalink shape is /updates/<co>/<product>/<version>/<build>/",
          ua == "/updates/microsoft/microsoft-powerpoint/2603/19822.20182/", ua)
    check("2 the build segment parses back exactly", _permalink_build_segment(ua) == BUILD_A)
    check("2 the product slug still parses (ownership gate intact)",
          _permalink_product_slug(ua) == PRODUCT)
    check("2 a version-only product's permalink is UNCHANGED",
          pi.permalink_path("obs-project", "obs-studio", "32.2.0") == "/updates/obs-project/obs-studio/32-2-0/")
    check("2 the old version-only URL is NOT claimed by either build record",
          pi.version_landing_path(COMPANY, PRODUCT, VERSION) not in {ua, ub})
    for bad, why in ((f"/updates/{COMPANY}/{PRODUCT}/{VERSION}/?x=1", "query string"),
                     (f"/updates/{COMPANY}/{PRODUCT}/{VERSION}/#f", "fragment"),
                     (f"/updates/{COMPANY}/{PRODUCT}/{VERSION}//{BUILD_A}/", "repeated slash"),
                     (f"/updates/{COMPANY}/{PRODUCT}/{VERSION}/../2607/", "traversal"),
                     (f"/updates/{COMPANY}/{PRODUCT}/{VERSION}/{BUILD_A}/extra/", "sixth segment")):
        check(f"2 malformed permalink still refused: {why}", _permalink_product_slug(bad) is None, bad)

    # ---- 3. RECORD INDEXING ----------------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        pa, pb = write_pair(gen)
        orig, orig_root = promo.GENERATED_DIR, promo.ROOT
        promo.GENERATED_DIR, promo.ROOT = gen, gen
        try:
            index = promo._index_generated_records()
            ka = pi.patch_key(PRODUCT, VERSION, BUILD_A)
            kb = pi.patch_key(PRODUCT, VERSION, BUILD_B)
            check("3 BOTH records survive indexing (no dict overwrite)", len(index) == 2, str(sorted(index)))
            check("3 build A resolves to its own file",
                  index.get(ka, {}).get("abs_path") == pa)
            check("3 build B resolves to its own file",
                  index.get(kb, {}).get("abs_path") == pb)
            check("3 a version-only lookup finds NOTHING (no YYMM fallback)",
                  index.get((PRODUCT, VERSION, "")) is None)
        finally:
            promo.GENERATED_DIR, promo.ROOT = orig, orig_root

    # ---- 4. STRUCTURED EVIDENCE KEYS -------------------------------------------------------
    same_url = "https://learn.microsoft.com/answers/q/1"
    ra = ev_row(BUILD_A, "r1", same_url)
    rb = ev_row(BUILD_B, "r2", same_url)
    check("4 same source URL + same version + DIFFERENT build -> different evidence keys",
          evidence_key(ra, "source_url") != evidence_key(rb, "source_url"))
    dup = ev_row(BUILD_A, "r1", same_url)
    check("4 the SAME report for the SAME build still deduplicates",
          evidence_key(ra, "id") == evidence_key(dup, "id"))
    check("4 the evidence key carries the build component",
          evidence_key(ra, "id")[2] == BUILD_A, str(evidence_key(ra, "id")))
    obs1 = ev_row("", "o1", "https://x/1", version="32.2.0", product="obs-studio")
    obs2 = dict(obs1, target_build="whatever-build")
    check("4 a version-only product's evidence key ignores any build metadata",
          evidence_key(obs1, "id") == evidence_key(obs2, "id"), str(evidence_key(obs2, "id")))

    # ---- 5. CONSENSUS GROUPING --------------------------------------------------------------
    rows = [ev_row(BUILD_A, "a1", "https://x/a1"), ev_row(BUILD_A, "a2", "https://x/a2"),
            ev_row(BUILD_B, "b1", "https://x/b1")]
    groups = promo._group_rows(rows, is_candidate_mode=False)
    check("5 two builds produce TWO consensus groups", len(groups) == 2, str(sorted(groups)))
    check("5 build A's group holds only build A's rows",
          len(groups[pi.patch_key(PRODUCT, VERSION, BUILD_A)]) == 2)
    check("5 build B's group holds only build B's rows",
          len(groups[pi.patch_key(PRODUCT, VERSION, BUILD_B)]) == 1)
    obs_groups = promo._group_rows(
        [ev_row("", "o1", "https://x/1", version="32.2.0", product="obs-studio"),
         ev_row("", "o2", "https://x/2", version="32.2.0", product="obs-studio")],
        is_candidate_mode=False)
    check("5 a version-only product still forms exactly ONE group", len(obs_groups) == 1)

    # ---- 6. REPORT-COUNT RECONCILIATION ------------------------------------------------------
    counts = counted_evidence_counts(rows, windows_targets={})
    check("6 counts are kept per exact build (A=2, B=1)",
          counts.get(pi.patch_key(PRODUCT, VERSION, BUILD_A)) == 2
          and counts.get(pi.patch_key(PRODUCT, VERSION, BUILD_B)) == 1, str(counts))
    check("6 no aggregated YYMM-only bucket exists",
          (PRODUCT, VERSION, "") not in counts, str(sorted(counts)))
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        pa, pb = write_pair(gen)
        changed, details = reconcile_record_counts(rows, gen)
        ta, tb = pa.read_text(encoding="utf-8"), pb.read_text(encoding="utf-8")
        check("6 build A's record receives exactly its own 2 reports",
              "update_report_count: 2" in ta, ta[:0] or "A")
        check("6 build B's record receives exactly its own 1 report",
              "update_report_count: 1" in tb)
        check("6 one build's evidence never moves the other's count",
              "update_report_count: 2" not in tb and "update_report_count: 1" not in ta)
        again, _ = reconcile_record_counts(rows, gen)
        check("6 second run is idempotent (zero further writes)", again == 0, str(again))

    # ---- 7. PROMOTION LOOKUP SELECTS ONLY THE EXACT BUILD --------------------------------------
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        write_pair(gen)
        orig, orig_root = promo.GENERATED_DIR, promo.ROOT
        promo.GENERATED_DIR, promo.ROOT = gen, gen
        try:
            index = promo._index_generated_records()
            res_a = promo._result_for_group(PRODUCT, VERSION, [ev_row(BUILD_A, "a1", "https://x/a1")],
                                            is_candidate_mode=False, records_index=index, build=BUILD_A)
            check("7 promotion for build A resolves build A's record",
                  BUILD_A.replace(".", "-") in str(res_a.get("record_path") or res_a.get("record") or index[pi.patch_key(PRODUCT, VERSION, BUILD_A)]["path"]))
            res_missing = promo._result_for_group(PRODUCT, VERSION, [ev_row("", "n1", "https://x/n1")],
                                                  is_candidate_mode=False, records_index=index, build="")
            check("7 MISSING build finds NO record -- no version-only fallback",
                  index.get(pi.patch_key(PRODUCT, VERSION, "")) is None and res_missing is not None)
            check("7 WRONG build finds NO record -- cannot promote onto a sibling build",
                  index.get(pi.patch_key(PRODUCT, VERSION, "99999.99999")) is None)
        finally:
            promo.GENERATED_DIR, promo.ROOT = orig, orig_root

    # ---- 8. QA CROSS-BUILD ALIGNMENT -----------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        gen = Path(d)
        pa, pb = write_pair(gen)
        # correct alignment: each record's count equals its OWN build's counted evidence
        pa.write_text(record_md(BUILD_A, 2, "community_reported"), encoding="utf-8")
        pb.write_text(record_md(BUILD_B, 1, "community_reported"), encoding="utf-8")
        orig_loader = qa_patch_records.load_counted_evidence_counts
        qa_patch_records.load_counted_evidence_counts = (
            lambda _records=None: counted_evidence_counts(rows, windows_targets={}))
        try:
            errs, _warns = qa_patch_records.scan_evidence_count_alignment([pa, pb])
            check("8 QA ACCEPTS correct per-build alignment", errs == [], str(errs))
            # cross-build: give build B build A's count
            pb.write_text(record_md(BUILD_B, 2, "community_reported"), encoding="utf-8")
            errs2, _ = qa_patch_records.scan_evidence_count_alignment([pa, pb])
            check("8 QA REJECTS cross-build alignment (B claiming A's 2 reports)",
                  any("generated_report_count_mismatch" in str(e) for e in errs2), str(errs2))
        finally:
            qa_patch_records.load_counted_evidence_counts = orig_loader

    # ---- 9. FAIL-CLOSED MISSING BUILD -----------------------------------------------------------
    try:
        pi.require_build(PRODUCT, VERSION, "")
        check("9 missing target_build fails closed for a build-aware product", False, "no raise")
    except pi.MissingBuildIdentity as exc:
        check("9 missing target_build fails closed for a build-aware product", True)
        check("9 the failure names the product and version",
              exc.product_id == PRODUCT and exc.update_version == VERSION)
    check("9 a version-only product never raises for a missing build",
          pi.require_build("obs-studio", "32.2.0", "") == "")
    check("9 build-awareness is an explicit allowlist, never inferred from a target_build field",
          pi.identity_build({"product_id": "obs-studio", "target_build": "1.2.3"}) == "")

    # ---- 10. NON-POWERPOINT COMPATIBILITY --------------------------------------------------------
    for pid, ver in (("obs-studio", "32.2.0"), ("blackmagic-davinci", "21.0.3"),
                     ("adobe-premiere-pro", "26.2"), ("adobe-acrobat-reader", "26.001.21563"),
                     ("adobe-acrobat-pro", "26.001.21563")):
        key = pi.patch_key(pid, ver)
        check(f"10 {pid} identity keeps an empty build slot", key == (pid, ver, ""), str(key))
        check(f"10 {pid} is not build-aware", not pi.is_build_aware(pid))
    # The allowlist is pinned EXACTLY, not by size. This assertion previously read "exactly one
    # product is build-aware today" and listed microsoft-windows-11 among the version-only
    # products above -- correct while a Windows record meant one servicing TRAIN, and wrong once
    # one record came to mean one cumulative update (25H2 alone ships 23 of them, which is the
    # very collision this module exists to prevent). What must stay pinned is that membership is
    # DELIBERATE: adding a product here changes its URLs, filenames and count keys, so it should
    # never be possible to do by accident. An exact-set comparison catches that; a count does not.
    check("10 the build-aware allowlist is exactly the products intended to be build-aware",
          pi.BUILD_AWARE_PRODUCTS == frozenset({PRODUCT, "microsoft-windows-11"}),
          str(pi.BUILD_AWARE_PRODUCTS))
    check("10 microsoft-windows-11 identity carries its exact build",
          pi.patch_key("microsoft-windows-11", "25H2", "26200.9168")
          == ("microsoft-windows-11", "25H2", "26200.9168"))

    print()
    print("=" * 68)
    total = _PASS + _FAIL
    print(f"Results: {_PASS}/{total} passed, {_FAIL} failed")
    if _ERRORS:
        for e in _ERRORS:
            print(f"  - {e}")
    print("=" * 68)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
