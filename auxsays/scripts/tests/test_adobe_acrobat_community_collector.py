#!/usr/bin/env python3
"""Tests for the shared Adobe Acrobat (Reader + Pro) community-evidence collector.

Offline only: canned candidate dicts are fed to the pure attribution/version/issue gates and
to row_from_candidate; no network, no repo writes. Proves fail-closed edition attribution,
exact DC-build version identity, the concrete-issue gate, URL specificity, dedup, per-method
health, and that Reader/Pro evidence never cross-contaminates.

Run with: PYTHONDONTWRITEBYTECODE=1 python auxsays/scripts/tests/test_adobe_acrobat_community_collector.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "auxsays" / "scripts"))

from patch_collectors import adobe_acrobat_community as ac
from patch_collectors.base import PatchRecord

_PASS = 0
_FAIL = 0
_ERRORS: list[str] = []

R, P = ac.READER_ID, ac.PRO_ID
VER = "26.001.21563"
REC_R = PatchRecord(R, VER, Path(f"2026-05-18-{R}-26-001-21563.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Reader")
REC_P = PatchRecord(P, VER, Path(f"2026-05-18-{P}-26-001-21563.md"), "2026-05-18T00:00:00Z", "current", "Adobe Acrobat Pro")
CAPTURED = "2026-07-17T00:00:00Z"
THREAD = "https://community.adobe.com/t5/acrobat-reader-discussions/x/td-p/12345678"
REDDIT = "https://www.reddit.com/r/Acrobat/comments/abc123/reader_crash/"


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


def cand(title, body, url=THREAD, date="2026-06-01", st=ac.ADOBE_COMMUNITY_SOURCE_TYPE):
    return {"source_type": st, "source_name": "Adobe Community", "source_url": url,
            "parent_title": title, "report_title": title, "report_text": body, "source_date": date}


def outcome(rec, pid, c):
    row = ac.row_from_candidate(pid, rec, c, CAPTURED)
    return row.get("counted"), row.get("exclusion_reason"), row.get("applicability")


def run() -> int:
    print("=" * 60)
    print("Adobe Acrobat community-evidence collector tests")
    print("=" * 60)

    # --- product attribution ------------------------------------------------
    check("Reader explicit -> accepted for Reader only",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes on launch after update."))[0] is True)
    check("Pro explicit -> accepted for Pro only",
          outcome(REC_P, P, cand("Acrobat Pro 26.001.21563", f"Adobe Acrobat Pro {VER} signing fails after update."))[0] is True)
    both = cand("Acrobat Reader and Pro 26.001.21563", f"Both Adobe Acrobat Reader and Acrobat Pro {VER} fail to install.")
    cr, _, appl_r = outcome(REC_R, R, both)
    cp, _, appl_p = outcome(REC_P, P, both)
    check("explicit Reader+Pro report applies to BOTH", cr is True and cp is True and appl_r == f"{R},{P}" and appl_p == f"{R},{P}", f"r={appl_r} p={appl_p}")
    check("bare 'Acrobat' rejected (generic_acrobat_without_edition)",
          outcome(REC_R, R, cand("Acrobat crash", f"Acrobat {VER} keeps crashing."))[1] == "generic_acrobat_without_edition")
    check("bare 'Adobe Acrobat' rejected (generic)",
          outcome(REC_P, P, cand("Adobe Acrobat crash", f"Adobe Acrobat {VER} crashes."))[1] == "generic_acrobat_without_edition")
    check("bare 'Reader' without Adobe context rejected (missing_product_attribution)",
          outcome(REC_R, R, cand("Reader crash", f"Reader {VER} keeps freezing."))[1] == "missing_product_attribution")
    check("wrong Adobe product rejected",
          outcome(REC_R, R, cand("Premiere crash", f"Adobe Premiere Pro {VER} export fails."))[1] in {"missing_product_attribution", "wrong_product"})
    check("Pro-only report on Reader instance -> wrong_product",
          outcome(REC_R, R, cand("Acrobat Pro 26.001.21563", f"Adobe Acrobat Pro {VER} crashes."))[1] == "wrong_product")
    check("Reader-only report on Pro instance -> wrong_product",
          outcome(REC_P, P, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes."))[1] == "wrong_product")

    # --- patch identity -----------------------------------------------------
    check("exact current version accepted",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."))[0] is True)
    check("earlier version rejected", outcome(REC_R, R, cand("Acrobat Reader old", "Adobe Acrobat Reader 26.001.21529 crashes."))[1] == "missing_exact_patch_version_match")
    check("later version rejected", outcome(REC_R, R, cand("Acrobat Reader new", "Adobe Acrobat Reader 26.001.99999 crashes."))[1] == "missing_exact_patch_version_match")
    check("partial version (major only) rejected", outcome(REC_R, R, cand("Acrobat Reader 26", "Adobe Acrobat Reader 26.001 crashes."))[1] == "missing_exact_patch_version_match")
    check("version only in unrelated build string rejected", outcome(REC_R, R, cand("Acrobat Reader signature", "Adobe Acrobat Reader crashes. My build is 26.001.215639 nightly."))[1] == "missing_exact_patch_version_match")
    check("report before release date rejected", outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.", date="2026-05-01"))[1] == "source_date_before_or_unverified_against_release")

    # --- issue attribution --------------------------------------------------
    for label, body, want in (
        ("crash accepted", f"Adobe Acrobat Reader {VER} crashes on launch after update.", True),
        ("install failure accepted", f"Adobe Acrobat Reader {VER} failed to install.", True),
        ("printing regression accepted", f"Adobe Acrobat Reader {VER} printing regression after update.", True),
        ("signing failure accepted", f"Adobe Acrobat Reader {VER} signing fails after update.", True),
        ("generic question rejected", f"How do I use Adobe Acrobat Reader {VER} to sign a form?", False),
        ("feature request rejected", f"Please add dark mode to Adobe Acrobat Reader {VER}.", False),
        ("pricing complaint rejected", f"Adobe Acrobat Reader {VER} subscription cost is too expensive.", False),
        ("announcement rejected", f"Adobe Acrobat Reader {VER} release notes and what's new.", False),
    ):
        counted, reason, _ = outcome(REC_R, R, cand("t", body))
        check(f"issue: {label}", (counted is True) == want, f"counted={counted} reason={reason}")

    # --- URL specificity ----------------------------------------------------
    check("Adobe board/search URL rejected (not specific)",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.", url="https://community.adobe.com/t5/acrobat-reader-discussions/bd-p/x"))[1] == "source_url_not_specific_report")
    check("Reddit /comments/ thread accepted",
          outcome(REC_R, R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update.", url=REDDIT, st=ac.REDDIT_SOURCE_TYPE))[0] is True)
    check("acrobat_url_is_specific: td-p thread true", ac.acrobat_url_is_specific(THREAD) is True)
    check("acrobat_url_is_specific: announcements false", ac.acrobat_url_is_specific("https://community.adobe.com/t5/announcements/x/td-p/9") is False)

    # --- structured evidence / official-only invariants ---------------------
    row = ac.row_from_candidate(R, REC_R, cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."), CAPTURED)
    check("accepted row carries product_id=reader, exact matched_version, applicability, weight 1",
          row["product_id"] == R and row["matched_version"] == VER and row["applicability"] == R and row["source_weight"] == 1,
          str({k: row.get(k) for k in ("product_id", "matched_version", "applicability", "source_weight")}))
    check("accepted row is a community source, not an official release note", row["source_type"] in {ac.ADOBE_COMMUNITY_SOURCE_TYPE, ac.REDDIT_SOURCE_TYPE})
    check("matched_product_alias recorded", row["matched_product_alias"] == "acrobat reader")

    # --- dedup / no cross-contamination -------------------------------------
    dup = [cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes after update."),
           cand("Acrobat Reader 26.001.21563 (repost)", f"Adobe Acrobat Reader {VER} crashes after update.")]  # same URL
    acc, rej = ac.evaluate_candidates(R, REC_R, dup, CAPTURED)
    check("duplicate URL counted once within a method", len(acc) == 1, f"accepted={len(acc)}")
    # Reader evidence row never carries Pro product_id (edition isolation at the row level).
    check("Reader rows are product_id=reader only", all(r["product_id"] == R for r in acc))
    accp, _ = ac.evaluate_candidates(P, REC_P, [cand("Acrobat Reader 26.001.21563", f"Adobe Acrobat Reader {VER} crashes.")], CAPTURED)
    check("a Reader-only report yields NO Pro rows (no cross-contamination)", len(accp) == 0, f"pro_accepted={len(accp)}")

    # --- method health ------------------------------------------------------
    check("method_status: accepted -> success", ac._method_status([1], [1], [], []) == "success")
    check("method_status: candidates only -> no_results", ac._method_status([1], [], [1], []) == "no_results")
    check("method_status: accepted + errors -> partial", ac._method_status([1], [1], [], [{"reason": "x"}]) == "partial")
    check("method_status: blocked error -> blocked", ac._method_status([], [], [], [{"reason": "adobe_community_search_fetch_failed:rate_limited"}]) == "blocked")
    check("method_status: non-blocked error -> broken", ac._method_status([], [], [], [{"reason": "network_TimeoutError"}]) == "broken")
    check("method_status: nothing -> no_results", ac._method_status([], [], [], []) == "no_results")

    # --- collect_for_record emits one health row per method (offline, no candidates) ----
    class _NoNet:
        max_pages = 1
        since = None
        target_versions = None
    coll = ac.AdobeAcrobatCollector(R)
    # monkeypatch the two discovery methods to return [] (no network)
    orig_adobe = ac.adobe_community_search_candidates
    orig_reddit = ac.reddit_search_candidates
    try:
        ac.adobe_community_search_candidates = lambda *a, **k: []
        ac.reddit_search_candidates = lambda *a, **k: []
        accepted, rejected, health = coll.collect_for_record(REC_R, _NoNet(), CAPTURED)
        method_ids = sorted(h["method_id"] for h in health)
        check("collect_for_record emits health for BOTH methods", method_ids == ["adobe_community_search", "reddit_search"], str(method_ids))
        check("zero candidates -> zero accepted, honest no_results health", accepted == [] and all(h["status"] == "no_results" for h in health))
        check("health rows carry the collector product_id", all(h["product_id"] == R for h in health))
    finally:
        ac.adobe_community_search_candidates = orig_adobe
        ac.reddit_search_candidates = orig_reddit

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
